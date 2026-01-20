from __future__ import annotations

import datetime
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Optional

from aiohttp import web

from homeassistant.core import HomeAssistant
from homeassistant.components.http import HomeAssistantView

from ..const import DOMAIN, TRAINING_ROOT_DIRNAME
from .websocket_impl import publish_gallery_update

_LOGGER = logging.getLogger(__name__)

# Training cache is stored under /config/<TRAINING_ROOT_DIRNAME>/training_cache
# (this is NOT under /config/www, and is not exposed to the frontend).
CACHE_ROOT = Path(f"/config/{TRAINING_ROOT_DIRNAME}/training_cache")


def _utc_iso_now() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _safe_folder_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return "Unknown"
    name = re.sub(r"[^0-9A-Za-z _-]+", "_", name)
    name = name.strip().strip(".")
    return name or "Unknown"


def _resolve_entry_and_processor(hass: HomeAssistant, entry_id: Optional[str]):
    data = hass.data.get(DOMAIN, {})
    if entry_id:
        proc = (data.get("processors") or {}).get(entry_id)
        client = (data.get("clients") or {}).get(entry_id)
        return client, proc
    return data.get("rekognition_client"), data.get("processor")


def _get_collection_id_from_entry(hass: HomeAssistant, entry_id: Optional[str]) -> Optional[str]:
    if entry_id:
        entry = hass.config_entries.async_get_entry(entry_id)
        if not entry:
            return None
        cid = (entry.data.get("collection_id") or "").strip()
        return cid or None

    entries = [e for e in hass.config_entries.async_entries(DOMAIN)]
    if not entries:
        return None
    cid = (entries[0].data.get("collection_id") or "").strip()
    return cid or None


def _find_gallery_record(gallery: dict, image_id: str) -> Optional[dict]:
    persons = (gallery or {}).get("persons") or {}
    for _name, items in persons.items():
        if not isinstance(items, list):
            continue
        for it in items:
            if isinstance(it, dict) and it.get("image_id") == image_id:
                return it
    return None


def _remove_gallery_record(gallery: dict, image_id: str) -> Optional[dict]:
    persons = (gallery or {}).get("persons") or {}
    for name, items in list(persons.items()):
        if not isinstance(items, list):
            continue
        for i, it in enumerate(list(items)):
            if isinstance(it, dict) and it.get("image_id") == image_id:
                removed = items.pop(i)
                if not items:
                    persons.pop(name, None)
                return removed
    return None


def _collect_face_ids_for_name(gallery: dict, name: str) -> list[str]:
    persons = (gallery or {}).get("persons") or {}
    items = persons.get(name) or []
    if not isinstance(items, list):
        return []
    out = []
    for it in items:
        if isinstance(it, dict) and it.get("face_id"):
            out.append(it["face_id"])
    return out


def _delete_local_files_for_name(gallery: dict, name: str) -> None:
    persons = (gallery or {}).get("persons") or {}
    items = persons.get(name) or []
    if not isinstance(items, list):
        return
    for it in items:
        try:
            p = Path(it.get("file") or "")
            if p.exists():
                p.unlink(missing_ok=True)
        except Exception:
            pass


class AFRGalleryUploadView(HomeAssistantView):
    url = "/api/amazon_face_recognition/gallery/upload"
    name = "api:amazon_face_recognition:gallery_upload"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        user = request.get("hass_user")
        if not user or not user.is_admin:
            raise web.HTTPForbidden(text="Admin required")

        form = await request.post()
        name = (form.get("name") or "").strip()
        entry_id = (form.get("entry_id") or "").strip() or None
        file_field = form.get("file")

        if not name:
            raise web.HTTPBadRequest(text="Missing field: name")
        if not file_field or not hasattr(file_field, "file"):
            raise web.HTTPBadRequest(text="Missing field: file")

        filename = getattr(file_field, "filename", "") or "upload.jpg"
        ext = os.path.splitext(filename)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png"):
            raise web.HTTPBadRequest(text="Unsupported format (jpg/jpeg/png)")

        image_id = uuid.uuid4().hex[:10]
        folder = CACHE_ROOT / _safe_folder_name(name)
        folder.mkdir(parents=True, exist_ok=True)
        out_path = folder / f"{image_id}{ext}"

        def _write_file():
            with out_path.open("wb") as f:
                f.write(file_field.file.read())

        await hass.async_add_executor_job(_write_file)

        def _read_bytes() -> bytes:
            with out_path.open("rb") as f:
                return f.read()

        image_bytes = await hass.async_add_executor_job(_read_bytes)

        client, processor = _resolve_entry_and_processor(hass, entry_id)
        if not client:
            raise web.HTTPInternalServerError(text="Rekognition client missing")

        collection_id = _get_collection_id_from_entry(hass, entry_id)
        if not collection_id:
            raise web.HTTPInternalServerError(text="collection_id missing")

        def _index():
            return client.index_faces(
                CollectionId=collection_id,
                Image={"Bytes": image_bytes},
                ExternalImageId=name,
                DetectionAttributes=["ALL"],
            )

        try:
            resp = await hass.async_add_executor_job(_index)
        except Exception as e:
            try:
                out_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise web.HTTPBadRequest(text=f"AWS index_faces failed: {e}")

        face_records = resp.get("FaceRecords") or []
        if not face_records:
            try:
                out_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise web.HTTPBadRequest(text="No faces indexed from this image")

        face_id = (face_records[0].get("Face") or {}).get("FaceId")
        if not face_id:
            raise web.HTTPBadRequest(text="FaceId missing in AWS response")

        if processor:
            try:
                await processor.async_refresh_faces_index()
            except Exception:
                pass

        data = hass.data.setdefault(DOMAIN, {})
        gallery_store = data.get("gallery_store")
        gallery = data.get("gallery") or {"updated_at": None, "persons": {}}
        persons = gallery.setdefault("persons", {})
        items = persons.setdefault(name, [])
        if not isinstance(items, list):
            items = []
            persons[name] = items

        items.append(
            {
                "image_id": image_id,
                "face_id": face_id,
                "name": name,
                "file": str(out_path),
                "created_at": _utc_iso_now(),
            }
        )
        gallery["updated_at"] = _utc_iso_now()

        if gallery_store:
            try:
                await gallery_store.async_save(gallery)
            except Exception as e:
                _LOGGER.warning("Gallery store save failed: %s", e)

        publish_gallery_update(hass, gallery)

        # Mirror face gallery to S3 (training_cache + gallery store) if configured.
        try:
            from ..sync.face_gallery_s3_impl import async_face_gallery_push_to_s3

            await async_face_gallery_push_to_s3(hass, entry_id=entry_id)
        except Exception:
            pass
        return web.json_response({"ok": True, "image_id": image_id, "face_id": face_id, "name": name})


class AFRGalleryImageView(HomeAssistantView):
    url = r"/api/amazon_face_recognition/gallery/image/{image_id}"
    name = "api:amazon_face_recognition:gallery_image"
    requires_auth = True

    async def get(self, request: web.Request, image_id: str) -> web.StreamResponse:
        hass: HomeAssistant = request.app["hass"]
        user = request.get("hass_user")
        if not user or not user.is_admin:
            raise web.HTTPForbidden(text="Admin required")

        data = hass.data.get(DOMAIN, {})
        gallery = data.get("gallery") or {"persons": {}}
        rec = _find_gallery_record(gallery, image_id)
        if not rec:
            raise web.HTTPNotFound(text="image_id not found")

        p = Path(rec.get("file") or "")
        if not p.exists() or not p.is_file():
            raise web.HTTPNotFound(text="file missing")

        return web.FileResponse(path=str(p))

    async def delete(self, request: web.Request, image_id: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        user = request.get("hass_user")
        if not user or not user.is_admin:
            raise web.HTTPForbidden(text="Admin required")

        data = hass.data.setdefault(DOMAIN, {})
        gallery_store = data.get("gallery_store")
        gallery = data.get("gallery") or {"updated_at": None, "persons": {}}

        removed = _remove_gallery_record(gallery, image_id)
        if not removed:
            raise web.HTTPNotFound(text="image_id not found")

        try:
            p = Path(removed.get("file") or "")
            if p.exists():
                p.unlink(missing_ok=True)
        except Exception:
            pass

        face_id = removed.get("face_id")
        entry_id = (request.query.get("entry_id") or "").strip() or None
        client, processor = _resolve_entry_and_processor(hass, entry_id)
        collection_id = _get_collection_id_from_entry(hass, entry_id)

        if client and collection_id and face_id:
            def _del():
                return client.delete_faces(CollectionId=collection_id, FaceIds=[face_id])

            try:
                await hass.async_add_executor_job(_del)
            except Exception as e:
                _LOGGER.warning("DeleteFaces failed for %s: %s", face_id, e)

        if processor:
            try:
                await processor.async_refresh_faces_index()
            except Exception:
                pass

        gallery["updated_at"] = _utc_iso_now()

        if gallery_store:
            try:
                await gallery_store.async_save(gallery)
            except Exception as e:
                _LOGGER.warning("Gallery store save failed: %s", e)

        publish_gallery_update(hass, gallery)

        # Mirror deletion to S3 (best effort)
        try:
            from ..sync.face_gallery_s3_impl import async_face_gallery_push_to_s3

            await async_face_gallery_push_to_s3(hass, entry_id=entry_id)
        except Exception:
            pass
        return web.json_response({"ok": True, "deleted": image_id})


class AFRGalleryManageView(HomeAssistantView):
    url = r"/api/amazon_face_recognition/gallery/manage"
    name = "api:amazon_face_recognition:gallery_manage"
    requires_auth = True

    async def delete(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        user = request.get("hass_user")
        if not user or not user.is_admin:
            raise web.HTTPForbidden(text="Admin required")

        mode = (request.query.get("mode") or "").strip()
        name = (request.query.get("name") or "").strip()
        entry_id = (request.query.get("entry_id") or "").strip() or None

        data = hass.data.setdefault(DOMAIN, {})
        gallery_store = data.get("gallery_store")
        gallery = data.get("gallery") or {"updated_at": None, "persons": {}}
        persons = gallery.setdefault("persons", {})

        client, processor = _resolve_entry_and_processor(hass, entry_id)
        collection_id = _get_collection_id_from_entry(hass, entry_id)

        if mode == "name":
            if not name:
                raise web.HTTPBadRequest(text="Missing query: name")

            face_ids = _collect_face_ids_for_name(gallery, name)
            if client and collection_id and face_ids:
                def _del():
                    return client.delete_faces(CollectionId=collection_id, FaceIds=face_ids)

                try:
                    await hass.async_add_executor_job(_del)
                except Exception as e:
                    _LOGGER.warning("DeleteFaces failed for name=%s: %s", name, e)

            _delete_local_files_for_name(gallery, name)
            persons.pop(name, None)

            if processor:
                try:
                    await processor.async_refresh_faces_index()
                except Exception:
                    pass

            gallery["updated_at"] = _utc_iso_now()
            if gallery_store:
                try:
                    await gallery_store.async_save(gallery)
                except Exception as e:
                    _LOGGER.warning("Gallery store save failed: %s", e)

            publish_gallery_update(hass, gallery)

            try:
                from ..sync.face_gallery_s3_impl import async_face_gallery_push_to_s3

                await async_face_gallery_push_to_s3(hass, entry_id=entry_id)
            except Exception:
                pass
            return web.json_response({"ok": True, "deleted_name": name, "deleted_faces": len(face_ids)})

        if mode == "all":
            all_face_ids: list[str] = []
            for n in list(persons.keys()):
                all_face_ids.extend(_collect_face_ids_for_name(gallery, n))
                _delete_local_files_for_name(gallery, n)

            if client and collection_id and all_face_ids:
                def _del():
                    out = []
                    for i in range(0, len(all_face_ids), 1000):
                        out.append(client.delete_faces(CollectionId=collection_id, FaceIds=all_face_ids[i:i+1000]))
                    return out

                try:
                    await hass.async_add_executor_job(_del)
                except Exception as e:
                    _LOGGER.warning("DeleteFaces failed for all: %s", e)

            persons.clear()

            if processor:
                try:
                    await processor.async_refresh_faces_index()
                except Exception:
                    pass

            gallery["updated_at"] = _utc_iso_now()
            if gallery_store:
                try:
                    await gallery_store.async_save(gallery)
                except Exception as e:
                    _LOGGER.warning("Gallery store save failed: %s", e)

            publish_gallery_update(hass, gallery)

            try:
                from ..sync.face_gallery_s3_impl import async_face_gallery_push_to_s3

                await async_face_gallery_push_to_s3(hass, entry_id=entry_id)
            except Exception:
                pass
            return web.json_response({"ok": True, "deleted_all": True, "deleted_faces": len(all_face_ids)})

        raise web.HTTPBadRequest(text="Invalid mode. Use mode=name&name=... or mode=all")
