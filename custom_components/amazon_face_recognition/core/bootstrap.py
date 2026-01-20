"""Integration bootstrap.

This file owns HA lifecycle hooks (async_setup / async_setup_entry / unload).
All side-effecty registrations live here.

The rest of the integration should avoid writing ad-hoc keys into hass.data;
use core.runtime.get_domain_data() instead.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple

import boto3
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.components.camera import async_get_image
from homeassistant.components.http import StaticPathConfig
import homeassistant.helpers.config_validation as cv
from homeassistant.components import panel_custom
from homeassistant.helpers.event import async_call_later

from ..const import (
    DOMAIN,
    CONF_AWS_ACCESS_KEY_ID,
    CONF_AWS_SECRET_ACCESS_KEY,
    CONF_REGION_NAME,
    CONF_COLLECTION_ID,
    CONF_S3_BUCKET,
    CONF_CLOUD_GALLERY_ENABLED,
    CONF_CLOUD_GALLERY_PREFIX,
    CONF_CLOUD_GALLERY_SYNC_ON_STARTUP,
    CONF_CLOUD_SCAN_UPLOAD_ENABLED,
    AFR_SCAN_DIRNAME,
    TRAINING_ROOT_DIRNAME,
)

from ..core.runtime import get_domain_data
from ..core.options import get_entry_options, merge_defaults
from ..processing.processor_impl import AFRProcessor
from ..api.websocket_impl import async_register_websockets
from ..api.gallery_http_impl import (
    AFRGalleryUploadView,
    AFRGalleryImageView,
    AFRGalleryManageView,
)
from ..stores.gallery_store_impl import AFRGalleryStore
from ..stores.plates_store_impl import AFRPlatesStore
from ..sync.face_gallery_s3_impl import async_face_gallery_sync_from_s3
from ..services.rekognition_services_impl import (
    svc_index_face,
    svc_delete_face_by_id,
    svc_delete_faces_by_name,
    svc_delete_all_faces,
)

try:
    from ..stores.usage_store_impl import AFRUsageStore
except Exception:  # pragma: no cover
    AFRUsageStore = None  # type: ignore


_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def _mount_static(hass: HomeAssistant) -> None:
    frontend_dir = Path(__file__).parent.parent / "frontend"
    if not frontend_dir.exists():
        _LOGGER.warning("AFR frontend directory not found: %s", frontend_dir)
        return

    try:
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    url_path="/amazon_face_recognition/frontend",
                    path=str(frontend_dir),
                    cache_headers=False,
                )
            ]
        )
    except Exception as e:
        _LOGGER.error("AFR frontend mount failed: %s", e)


def _register_views_once(hass: HomeAssistant) -> None:
    data = get_domain_data(hass)
    if data.get("_views_registered"):
        return

    hass.http.register_view(AFRGalleryUploadView)
    hass.http.register_view(AFRGalleryImageView)
    hass.http.register_view(AFRGalleryManageView)

    data["_views_registered"] = True


def _register_ws_once(hass: HomeAssistant) -> None:
    data = get_domain_data(hass)
    if data.get("_ws_registered"):
        return
    async_register_websockets(hass)
    data["_ws_registered"] = True


def _ensure_usage_store(hass: HomeAssistant) -> None:
    data = get_domain_data(hass)
    if data.get("usage_store") is not None:
        return

    if AFRUsageStore is None:
        data["usage_store"] = None
        return

    data["usage_store"] = AFRUsageStore(hass)


async def _load_usage_once(hass: HomeAssistant) -> None:
    data = get_domain_data(hass)
    if data.get("_usage_loaded"):
        return

    store = data.get("usage_store")
    if store is None:
        data["_usage_loaded"] = True
        return

    try:
        usage = await store.async_load()
        if isinstance(usage, dict):
            data["usage"] = usage
    except Exception as e:
        _LOGGER.warning("AFR: usage load failed: %s", e)

    data["_usage_loaded"] = True


def _ensure_gallery_store(hass: HomeAssistant) -> None:
    data = get_domain_data(hass)
    if data.get("gallery_store") is not None:
        return
    data["gallery_store"] = AFRGalleryStore(hass)


async def _load_gallery_once(hass: HomeAssistant) -> None:
    data = get_domain_data(hass)
    if data.get("_gallery_loaded"):
        return

    store = data.get("gallery_store")
    if store is None:
        data["_gallery_loaded"] = True
        return

    try:
        gallery = await store.async_load()
        if isinstance(gallery, dict):
            data["gallery"] = gallery
    except Exception as e:
        _LOGGER.warning("AFR: gallery load failed: %s", e)

    data["_gallery_loaded"] = True


def _ensure_plates_store(hass: HomeAssistant) -> None:
    data = get_domain_data(hass)
    if data.get("plates_store") is not None:
        return
    data["plates_store"] = AFRPlatesStore(hass)


async def _load_plates_once(hass: HomeAssistant) -> None:
    data = get_domain_data(hass)
    if data.get("_plates_loaded"):
        return

    store = data.get("plates_store")
    if store is None:
        data["_plates_loaded"] = True
        return

    try:
        plates = await store.async_load()
        if isinstance(plates, dict):
            data["plates"] = plates
    except Exception as e:
        _LOGGER.warning("AFR: plates load failed: %s", e)

    data["_plates_loaded"] = True


async def _register_panel_once(hass: HomeAssistant) -> None:
    data = get_domain_data(hass)
    if data.get("_panel_registered"):
        return

    await _mount_static(hass)

    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="afr-panel",
        frontend_url_path="afr",
        module_url="/amazon_face_recognition/frontend/afr-panel.js?v=3",
        sidebar_title="Recognition Center",
        sidebar_icon="mdi:face-recognition",
        require_admin=True,
    )

    data["_panel_registered"] = True


def _get_options(entry: ConfigEntry) -> dict:
    # Merge defaults so behavior matches UI defaults right after initial install.
    return get_entry_options(entry)


def _resolve_entry_and_processor(
    hass: HomeAssistant, call: ServiceCall
) -> Tuple[Optional[ConfigEntry], Optional[AFRProcessor]]:
    entry_id = (call.data.get("entry_id") or "").strip()
    data = get_domain_data(hass)

    if entry_id:
        entry = hass.config_entries.async_get_entry(entry_id)
        proc = data.get("processors", {}).get(entry_id)
        return entry, proc

    processors = data.get("processors", {})
    if not processors:
        return None, None

    first_entry_id = next(iter(processors.keys()))
    entry = hass.config_entries.async_get_entry(first_entry_id)
    return entry, processors.get(first_entry_id)


def _register_services_once(hass: HomeAssistant) -> None:
    data = get_domain_data(hass)
    if data.get("_services_registered"):
        return

    async def _persist_usage_if_possible() -> None:
        store = get_domain_data(hass).get("usage_store")
        if store is not None:
            try:
                store.schedule_save()
            except Exception:
                pass

    async def _svc_scan(call: ServiceCall) -> None:
        entry2, processor2 = _resolve_entry_and_processor(hass, call)
        if processor2 is None or entry2 is None:
            _LOGGER.error(
                "%s: scan: unable to resolve entry/processor (pass entry_id if multiple entries).",
                DOMAIN,
            )
            return

        entity_id = call.data["entity_id"]
        img = await async_get_image(hass, entity_id)
        if img is None:
            _LOGGER.error("%s: scan: unable to get image from %s", DOMAIN, entity_id)
            return

        processor2.update_options(_get_options(entry2))
        await processor2.async_process_camera_image(entity_id, img.content)
        await _persist_usage_if_possible()

    async def _svc_refresh_faces_index(call: ServiceCall) -> None:
        entry2, processor2 = _resolve_entry_and_processor(hass, call)
        if processor2 is None or entry2 is None:
            _LOGGER.error(
                "%s: refresh_faces_index: unable to resolve entry/processor (pass entry_id if multiple entries).",
                DOMAIN,
            )
            return

        processor2.update_options(_get_options(entry2))
        await processor2.async_refresh_faces_index()

    async def _svc_index_face(call: ServiceCall) -> None:
        entry2, _ = _resolve_entry_and_processor(hass, call)
        if entry2 is None:
            _LOGGER.error(
                "%s: index_face: unable to resolve entry (pass entry_id if multiple entries).",
                DOMAIN,
            )
            return
        await svc_index_face(hass, entry2, call)

    async def _svc_delete_face_by_id(call: ServiceCall) -> None:
        entry2, _ = _resolve_entry_and_processor(hass, call)
        if entry2 is None:
            _LOGGER.error(
                "%s: delete_face_by_id: unable to resolve entry (pass entry_id if multiple entries).",
                DOMAIN,
            )
            return
        await svc_delete_face_by_id(hass, entry2, call)

    async def _svc_delete_faces_by_name(call: ServiceCall) -> None:
        entry2, _ = _resolve_entry_and_processor(hass, call)
        if entry2 is None:
            _LOGGER.error(
                "%s: delete_faces_by_name: unable to resolve entry (pass entry_id if multiple entries).",
                DOMAIN,
            )
            return
        await svc_delete_faces_by_name(hass, entry2, call)

    async def _svc_delete_all_faces(call: ServiceCall) -> None:
        entry2, _ = _resolve_entry_and_processor(hass, call)
        if entry2 is None:
            _LOGGER.error(
                "%s: delete_all_faces: unable to resolve entry (pass entry_id if multiple entries).",
                DOMAIN,
            )
            return
        await svc_delete_all_faces(hass, entry2, call)

    hass.services.async_register(
        DOMAIN,
        "scan",
        _svc_scan,
        vol.Schema(
            {
                vol.Required("entity_id"): cv.entity_id,
                vol.Optional("entry_id"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        "refresh_faces_index",
        _svc_refresh_faces_index,
        vol.Schema({vol.Optional("entry_id"): cv.string}),
    )

    hass.services.async_register(
        DOMAIN,
        "delete_all_faces",
        _svc_delete_all_faces,
        vol.Schema({vol.Optional("entry_id"): cv.string}),
    )

    data["_services_registered"] = True


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    get_domain_data(hass)

    await _mount_static(hass)

    # auto-load card JS (do NOT change as requested)
    url = "/amazon_face_recognition/frontend/aws-face-recognition-card.js?v=1"
    try:
        hass.data.setdefault("frontend_extra_module_url", set()).add(url)
    except Exception as e:
        _LOGGER.error("AFR auto-load card failed: %s", e)

    _register_ws_once(hass)

    _ensure_usage_store(hass)
    await _load_usage_once(hass)

    _register_services_once(hass)
    await _register_panel_once(hass)

    _register_views_once(hass)

    _ensure_gallery_store(hass)
    await _load_gallery_once(hass)

    _ensure_plates_store(hass)
    await _load_plates_once(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = get_domain_data(hass)

    _register_ws_once(hass)
    _ensure_usage_store(hass)
    await _load_usage_once(hass)

    _ensure_gallery_store(hass)
    await _load_gallery_once(hass)

    _register_services_once(hass)
    _register_views_once(hass)

    _ensure_plates_store(hass)
    await _load_plates_once(hass)

    aws_access_key_id = entry.data.get(CONF_AWS_ACCESS_KEY_ID)
    aws_secret_access_key = entry.data.get(CONF_AWS_SECRET_ACCESS_KEY)
    region_name = entry.data.get(CONF_REGION_NAME)
    collection_id = entry.data.get(CONF_COLLECTION_ID)

    try:
        client = await hass.async_add_executor_job(
            _create_rekognition_client_sync,
            aws_access_key_id,
            aws_secret_access_key,
            region_name,
        )
    except Exception as e:
        _LOGGER.error("%s: cannot create rekognition client: %s", DOMAIN, e)
        return False

    options = _get_options(entry)
    data["options"] = options

    processor = AFRProcessor(hass, client, collection_id, options)

    data["clients"][entry.entry_id] = client
    data["processors"][entry.entry_id] = processor

    data["rekognition_client"] = client
    data["processor"] = processor

    # Keep runtime objects in sync with entry.options changes (no restart needed).
    async def _on_entry_update(hass: HomeAssistant, updated_entry: ConfigEntry) -> None:
        try:
            new_opt = _get_options(updated_entry)
            data["options"] = new_opt

            proc = data.get("processors", {}).get(updated_entry.entry_id)
            if proc:
                proc.update_options(new_opt)

            # S3 bucket/prefix can be configured at first setup (entry.data) and later edited in options.
            aws_access_key_id = updated_entry.data.get(CONF_AWS_ACCESS_KEY_ID)
            aws_secret_access_key = updated_entry.data.get(CONF_AWS_SECRET_ACCESS_KEY)
            region_name = updated_entry.data.get(CONF_REGION_NAME)

            bucket = (new_opt.get(CONF_S3_BUCKET) or updated_entry.data.get(CONF_S3_BUCKET) or "").strip()
            cloud_enabled = bool(new_opt.get(CONF_CLOUD_GALLERY_ENABLED, True))
            cloud_prefix = (new_opt.get(CONF_CLOUD_GALLERY_PREFIX) or AFR_SCAN_DIRNAME).strip("/")
            if not cloud_prefix:
                cloud_prefix = AFR_SCAN_DIRNAME

            if bucket and cloud_enabled:
                # Ensure S3 client exists
                ctx = data.get("s3", {}).get(updated_entry.entry_id)
                s3_client = ctx.get("client") if isinstance(ctx, dict) else None
                if s3_client is None:
                    try:
                        s3_client = await hass.async_add_executor_job(
                            _create_s3_client_sync,
                            aws_access_key_id,
                            aws_secret_access_key,
                            region_name,
                        )
                        data.setdefault("s3", {})[updated_entry.entry_id] = {
                            "client": s3_client,
                            "bucket": bucket,
                            "prefix": cloud_prefix,
                        }
                    except Exception as e:
                        _LOGGER.warning("%s: cannot create S3 client on options update: %s", DOMAIN, e)
                        s3_client = None
                else:
                    # Update bucket/prefix
                    data.setdefault("s3", {})[updated_entry.entry_id] = {
                        "client": s3_client,
                        "bucket": bucket,
                        "prefix": cloud_prefix,
                    }

                if proc and s3_client is not None:
                    try:
                        proc.set_cloud_gallery(s3_client, bucket, cloud_prefix)
                    except Exception:
                        pass
            else:
                # Cloud disabled / bucket removed
                try:
                    data.get("s3", {}).pop(updated_entry.entry_id, None)
                except Exception:
                    pass
                if proc:
                    try:
                        proc.set_cloud_gallery(None, "", "")
                    except Exception:
                        pass
        except Exception as e:
            _LOGGER.debug("%s: entry update handler failed: %s", DOMAIN, e)

    entry.async_on_unload(entry.add_update_listener(_on_entry_update))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _initial_faces_refresh(_now):
        try:
            processor.update_options(_get_options(entry))
            await processor.async_refresh_faces_index()
        except Exception as err:
            _LOGGER.warning("Initial faces index refresh failed: %s", err)

    async_call_later(hass, 5, _initial_faces_refresh)

    scan_dir = Path(hass.config.path("www", AFR_SCAN_DIRNAME))
    scan_dir.mkdir(parents=True, exist_ok=True)

    training_dir = Path(hass.config.path(TRAINING_ROOT_DIRNAME, "training_cache"))
    training_dir.mkdir(parents=True, exist_ok=True)

    bucket = (options.get(CONF_S3_BUCKET) or entry.data.get(CONF_S3_BUCKET) or "").strip()
    cloud_enabled = bool(options.get(CONF_CLOUD_GALLERY_ENABLED, True))
    cloud_prefix = (options.get(CONF_CLOUD_GALLERY_PREFIX) or AFR_SCAN_DIRNAME).strip("/")
    sync_on_startup = bool(options.get(CONF_CLOUD_GALLERY_SYNC_ON_STARTUP, True))
    scan_upload_enabled = bool(options.get(CONF_CLOUD_SCAN_UPLOAD_ENABLED, False))

    if bucket and cloud_enabled:
        try:
            s3_client = await hass.async_add_executor_job(
                _create_s3_client_sync,
                aws_access_key_id,
                aws_secret_access_key,
                region_name,
            )

            data["s3"][entry.entry_id] = {
                "client": s3_client,
                "bucket": bucket,
                "prefix": cloud_prefix,
            }

            try:
                processor.set_cloud_gallery(s3_client, bucket, cloud_prefix)
            except Exception:
                pass

            if sync_on_startup:
                if scan_upload_enabled:
                    await processor.async_cloud_gallery_sync(s3_client, bucket, cloud_prefix)

                try:
                    local_has_files = any(training_dir.rglob("*"))
                except Exception:
                    local_has_files = False

                try:
                    persons = (data.get("gallery") or {}).get("persons") or {}
                    local_has_gallery = bool(persons)
                except Exception:
                    local_has_gallery = False

                if not local_has_files and not local_has_gallery:
                    await async_face_gallery_sync_from_s3(
                        hass, entry_id=entry.entry_id, force_align=False
                    )
        except Exception as e:
            _LOGGER.warning("%s: Cloud Gallery (S3) init/sync failed: %s", DOMAIN, e)

    await processor.async_bootstrap()
    await _register_panel_once(hass)

    return True


def _create_rekognition_client_sync(
    aws_access_key_id: str, aws_secret_access_key: str, region_name: str
):
    return boto3.client(
        "rekognition",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=region_name,
    )


def _create_s3_client_sync(
    aws_access_key_id: str, aws_secret_access_key: str, region_name: str
):
    return boto3.client(
        "s3",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=region_name,
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = get_domain_data(hass)
        data.get("processors", {}).pop(entry.entry_id, None)
        data.get("clients", {}).pop(entry.entry_id, None)
        data.get("s3", {}).pop(entry.entry_id, None)

        processors = data.get("processors", {})
        if processors:
            first_id = next(iter(processors.keys()))
            data["processor"] = processors[first_id]
            data["rekognition_client"] = data.get("clients", {}).get(first_id)
        else:
            data.pop("processor", None)
            data.pop("rekognition_client", None)

    return unload_ok
