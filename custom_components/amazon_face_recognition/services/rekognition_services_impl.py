# custom_components/amazon_face_recognition/rekognition_services.py
from __future__ import annotations


import logging
from typing import Optional

import botocore

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from pathlib import Path
from homeassistant.exceptions import HomeAssistantError
from homeassistant.components.persistent_notification import async_create as pn_create


from ..const import DOMAIN, CONF_COLLECTION_ID

_LOGGER = logging.getLogger(__name__)


def _get_client(hass: HomeAssistant):
    return hass.data.get(DOMAIN, {}).get("rekognition_client")


def _get_collection_id(entry: ConfigEntry) -> Optional[str]:
    cid = (entry.data.get(CONF_COLLECTION_ID) or "").strip()
    return cid or None


async def svc_index_face(hass: HomeAssistant, entry: ConfigEntry, call: ServiceCall) -> None:
    client = _get_client(hass)
    collection_id = _get_collection_id(entry)
    processor = hass.data[DOMAIN].get("processor")

    if not client or not collection_id:
        raise HomeAssistantError("Rekognition client o collection_id mancanti. Controlla la configurazione.")

    raw_file = (call.data.get("file") or call.data.get("file_path") or "").strip()
    name = (call.data.get("name") or "").strip()

    if not raw_file:
        raise HomeAssistantError("Campo 'file' mancante. Esempio: /config/www/.../mattia_01.jpg")
    if not name:
        raise HomeAssistantError("Campo 'name' mancante. Esempio: Mattia")

    # Blocca URL http(s) (non è un file locale)
    if raw_file.startswith("http://") or raw_file.startswith("https://"):
        raise HomeAssistantError(
            "Il campo 'file' deve essere un percorso locale su disco (es. /config/www/...), non un URL http(s)."
        )

    # Supporta /local/... convertendolo a /config/www/...
    file_str = raw_file
    if file_str.startswith("/local/"):
        file_str = "/config/www/" + file_str[len("/local/") :]

    p = Path(file_str)

    # Percorso assoluto richiesto
    if not p.is_absolute():
        raise HomeAssistantError(f"Percorso non valido: {file_str}. Usa un percorso assoluto (es. /config/www/...).")

    # Estensioni supportate
    if p.suffix.lower() not in (".jpg", ".jpeg", ".png"):
        raise HomeAssistantError("Formato non supportato. Usa .jpg / .jpeg / .png")

    # File deve esistere
    if not p.exists() or not p.is_file():
        msg = f"File non trovato: {p}"
        res = pn_create(
            hass,
            msg,
            title="Amazon Face Recognition – index_face",
            notification_id="afr_index_face_file_missing",
        )
        if hasattr(res, "__await__"):
            await res
        raise HomeAssistantError(msg)

    def _load_bytes() -> bytes:
        with p.open("rb") as f:
            return f.read()

    try:
        image_bytes = await hass.async_add_executor_job(_load_bytes)
    except Exception as e:
        raise HomeAssistantError(f"Impossibile leggere il file: {p}. Errore: {e}") from e

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
        raise HomeAssistantError(f"Errore AWS durante index_faces: {e}") from e

    _LOGGER.info("Face indexed: %s", resp)

    # refresh faces_index SOLO dopo successo
    if processor:
        await processor.async_refresh_faces_index()


async def svc_delete_face_by_id(hass: HomeAssistant, entry: ConfigEntry, call: ServiceCall) -> None:
    client = _get_client(hass)
    collection_id = _get_collection_id(entry)
    processor = hass.data[DOMAIN].get("processor")
    if processor:
        await processor.async_refresh_faces_index()

    if not client or not collection_id:
        _LOGGER.error("delete_face_by_id: rekognition_client or collection_id missing")
        return

    face_id = (call.data.get("face_id") or "").strip()
    if not face_id:
        _LOGGER.error("delete_face_by_id: Missing face_id")
        return

    def _del():
        client.delete_faces(CollectionId=collection_id, FaceIds=[face_id])

    try:
        await hass.async_add_executor_job(_del)
        _LOGGER.info("Deleted FaceId=%s", face_id)
    except Exception as e:
        _LOGGER.error("delete_face_by_id error: %s", e)
        return

    if processor:
        await processor.async_refresh_faces_index()


async def svc_delete_faces_by_name(hass: HomeAssistant, entry: ConfigEntry, call: ServiceCall) -> None:
    client = _get_client(hass)
    collection_id = _get_collection_id(entry)
    processor = hass.data[DOMAIN].get("processor")
    if processor:
        await processor.async_refresh_faces_index()

    if not client or not collection_id:
        _LOGGER.error("delete_faces_by_name: rekognition_client or collection_id missing")
        return

    name = (call.data.get("name") or "").strip()
    if not name:
        _LOGGER.error("delete_faces_by_name: Missing name")
        return

    def _list():
        resp = client.list_faces(CollectionId=collection_id)
        return [f["FaceId"] for f in resp.get("Faces", []) if f.get("ExternalImageId") == name]

    face_ids = await hass.async_add_executor_job(_list)
    if not face_ids:
        _LOGGER.info("No faces found for name=%s", name)
        return

    def _delete_batch(ids):
        for i in range(0, len(ids), 10):
            client.delete_faces(CollectionId=collection_id, FaceIds=ids[i : i + 10])

    try:
        await hass.async_add_executor_job(_delete_batch, face_ids)
        _LOGGER.info("Deleted %s faces for name=%s", len(face_ids), name)
    except Exception as e:
        _LOGGER.error("delete_faces_by_name error: %s", e)
        return

    if processor:
        await processor.async_refresh_faces_index()


async def svc_delete_all_faces(hass: HomeAssistant, entry: ConfigEntry, call: ServiceCall) -> None:
    client = _get_client(hass)
    collection_id = _get_collection_id(entry)
    processor = hass.data[DOMAIN].get("processor")
    if processor:
        await processor.async_refresh_faces_index()

    if not client or not collection_id:
        _LOGGER.error("delete_all_faces: rekognition_client or collection_id missing")
        return

    def _list_all():
        resp = client.list_faces(CollectionId=collection_id)
        return [f["FaceId"] for f in resp.get("Faces", [])]

    face_ids = await hass.async_add_executor_job(_list_all)
    if not face_ids:
        _LOGGER.info("No faces to delete")
        return

    def _delete_batch(ids):
        for i in range(0, len(ids), 10):
            client.delete_faces(CollectionId=collection_id, FaceIds=ids[i : i + 10])

    try:
        await hass.async_add_executor_job(_delete_batch, face_ids)
        _LOGGER.info("Deleted %s faces", len(face_ids))
    except Exception as e:
        _LOGGER.error("delete_all_faces error: %s", e)
        return

    if processor:
        await processor.async_refresh_faces_index()
