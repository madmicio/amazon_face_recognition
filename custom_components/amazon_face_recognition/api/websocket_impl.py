from __future__ import annotations

from typing import Any, Dict

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.components import websocket_api
from homeassistant.util import dt as dt_util
from homeassistant.config_entries import ConfigEntry


from ..const import (
    DOMAIN,
    EVENT_UPDATED,
    EVENT_FACES_UPDATED,
    WS_GET_LAST_RESULT,
    WS_GET_INDEX,
    WS_SUBSCRIBE_UPDATES,
    WS_GET_FACES_INDEX,
    WS_SUBSCRIBE_FACES,
    EVENT_GALLERY_UPDATED,
    WS_GET_GALLERY,
    WS_SUBSCRIBE_GALLERY,
    WS_SYNC_FACE_GALLERY,
    EVENT_PLATES_UPDATED,
    WS_GET_PLATES,
    WS_SET_PLATES,
    WS_SUBSCRIBE_PLATES,
    CONF_SCAN_CARS,

    EVENT_ROI_UPDATED,
    WS_GET_ROI,
    WS_SET_ROI,
    WS_SUBSCRIBE_ROI,
)

from ..core.runtime import get_locks

DEFAULT_INDEX: Dict[str, Any] = {"updated_at": None, "items": []}
DEFAULT_FACES_INDEX: Dict[str, Any] = {"updated_at": None, "persons": {}}

def _is_scan_cars_enabled(hass: HomeAssistant) -> bool:
    """Return scan_cars flag.

    Fast-path: use the cached options stored by __init__.py into hass.data[DOMAIN]["options"].
    Fallback: read it from the first config entry.
    """
    try:
        d = hass.data.get(DOMAIN) or {}
        opts = d.get("options") or {}
        if isinstance(opts, dict) and CONF_SCAN_CARS in opts:
            return bool(opts.get(CONF_SCAN_CARS, False))
    except Exception:
        pass

    try:
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            return False
        entry: ConfigEntry = entries[0]
        return bool((entry.options or {}).get(CONF_SCAN_CARS, False))
    except Exception:
        return False



def _data(hass: HomeAssistant) -> dict:
    return hass.data.setdefault(DOMAIN, {})


def async_register_websockets(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_get_last_result)
    websocket_api.async_register_command(hass, ws_get_index)
    websocket_api.async_register_command(hass, ws_subscribe_updates)
    websocket_api.async_register_command(hass, ws_get_faces_index)
    websocket_api.async_register_command(hass, ws_subscribe_faces)
    websocket_api.async_register_command(hass, ws_get_gallery)
    websocket_api.async_register_command(hass, ws_subscribe_gallery)
    websocket_api.async_register_command(hass, ws_sync_face_gallery)
    websocket_api.async_register_command(hass, ws_get_plates)
    websocket_api.async_register_command(hass,ws_set_plates)
    websocket_api.async_register_command(hass, ws_subscribe_plates)
    websocket_api.async_register_command(hass, ws_get_roi)
    websocket_api.async_register_command(hass, ws_set_roi)
    websocket_api.async_register_command(hass, ws_subscribe_roi)




# -------- Commands --------

@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_GET_LAST_RESULT,
        vol.Required("id"): int,
    }
)

@websocket_api.async_response
async def ws_get_last_result(hass, connection, msg) -> None:
    d = _data(hass)
    last = dict(d.get("last_result", {}) or {})

    # Leggi le options che salvi in hass.data[DOMAIN]["options"]
    opts = d.get("options") or {}
    last["scan_cars_enabled"] = bool(opts.get(CONF_SCAN_CARS, False))

    connection.send_result(msg["id"], last)


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_GET_INDEX,
        vol.Required("id"): int,
        vol.Optional("limit", default=20): vol.Coerce(int),
    }
)
@websocket_api.async_response
async def ws_get_index(hass, connection, msg) -> None:
    d = _data(hass)
    index = d.get("index") or DEFAULT_INDEX

    limit = max(1, min(int(msg.get("limit", 20)), 500))
    items = (index.get("items") or [])[:limit]

    connection.send_result(
        msg["id"],
        {"updated_at": index.get("updated_at"), "items": items},
    )


def _subscribe_event(hass: HomeAssistant, connection, msg_id: int, event_type: str):
    @callback
    def _forward(event) -> None:
        connection.send_message(websocket_api.event_message(msg_id, event.data))

    return hass.bus.async_listen(event_type, _forward)


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_SUBSCRIBE_UPDATES,
        vol.Required("id"): int,
    }
)
@websocket_api.async_response
async def ws_subscribe_updates(hass, connection, msg) -> None:
    unsub = _subscribe_event(hass, connection, msg["id"], EVENT_UPDATED)
    connection.subscriptions[msg["id"]] = unsub
    connection.send_result(msg["id"], {"subscribed": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_GET_FACES_INDEX,
        vol.Required("id"): int,
    }
)
@websocket_api.async_response
async def ws_get_faces_index(hass, connection, msg) -> None:
    d = _data(hass)
    faces_index = d.get("faces_index") or DEFAULT_FACES_INDEX
    connection.send_result(msg["id"], faces_index)


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_SUBSCRIBE_FACES,
        vol.Required("id"): int,
    }
)
@websocket_api.async_response
async def ws_subscribe_faces(hass, connection, msg) -> None:
    unsub = _subscribe_event(hass, connection, msg["id"], EVENT_FACES_UPDATED)
    connection.subscriptions[msg["id"]] = unsub
    connection.send_result(msg["id"], {"subscribed": True})


# -------- Publish helpers (performance) --------

@callback
def publish_faces_update(hass: HomeAssistant, faces_index: dict) -> None:
    d = _data(hass)
    d["faces_index"] = faces_index or DEFAULT_FACES_INDEX
    hass.bus.async_fire(EVENT_FACES_UPDATED, d["faces_index"])


@callback
def publish_update(
    hass: HomeAssistant,
    *,
    last_result: dict | None = None,
    index_data: dict | None = None,
) -> None:
    """
    Update cache + fire EVENT_UPDATED once (no duplicate events).
    Payload small: last_result + updated_at.
    """
    d = _data(hass)
    payload: Dict[str, Any] = {}

    if last_result is not None:
        d["last_result"] = last_result or {}
        payload["last_result"] = d["last_result"]

    if index_data is not None:
        d["index"] = index_data or DEFAULT_INDEX
        payload["updated_at"] = d["index"].get("updated_at")

    if payload:
        hass.bus.async_fire(EVENT_UPDATED, payload)

@callback
def publish_gallery_update(hass: HomeAssistant, gallery: dict) -> None:
    hass.data[DOMAIN]["gallery"] = gallery
    hass.bus.async_fire(EVENT_GALLERY_UPDATED, gallery)

@websocket_api.websocket_command(
    {vol.Required("type"): WS_GET_GALLERY}
)
@websocket_api.async_response
async def ws_get_gallery(hass, connection, msg):
    connection.send_result(msg["id"], hass.data[DOMAIN].get("gallery"))

@websocket_api.websocket_command(
    {vol.Required("type"): WS_SUBSCRIBE_GALLERY}
)
@websocket_api.async_response
async def ws_subscribe_gallery(hass, connection, msg):
    @callback
    def forward(event):
        connection.send_message(
            websocket_api.event_message(msg["id"], event.data)
        )

    unsub = hass.bus.async_listen(EVENT_GALLERY_UPDATED, forward)
    connection.send_result(msg["id"], {})
    connection.subscriptions[msg["id"]] = unsub


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_SYNC_FACE_GALLERY,
        vol.Required("id"): int,
        vol.Optional("entry_id"): str,
        vol.Optional("force_align", default=True): bool,
    }
)
@websocket_api.async_response
async def ws_sync_face_gallery(hass, connection, msg):
    """Sync local face gallery (training_cache + store) from S3, then refresh faces_index."""
    from ..sync.face_gallery_s3_impl import async_face_gallery_sync_from_s3

    # 1) sync gallery da S3 (protetto da lock)
    locks = get_locks(hass)
    async with locks.s3_sync:
        res = await async_face_gallery_sync_from_s3(
            hass,
            entry_id=(msg.get("entry_id") or None),
            force_align=bool(msg.get("force_align", True)),
        )

    # 2) ricostruisci faces_index dalla gallery locale
    faces_index = None
    try:
        gallery = hass.data[DOMAIN].get("gallery") or {}
        persons = gallery.get("persons") or {}

        faces_index = {
            "updated_at": dt_util.utcnow().replace(microsecond=0).isoformat() + "Z",
            "persons": {},
        }

        for name, items in persons.items():
            if isinstance(name, str) and isinstance(items, list):
                faces_index["persons"][name] = {"count": len(items)}

        # aggiorna cache + notifica i subscriber
        publish_faces_update(hass, faces_index)

        # 🔥 QUI ESATTAMENTE
        # aggiungiamo faces_index alla risposta websocket
        if isinstance(res, dict):
            res["faces_index"] = faces_index

    except Exception as e:
        # non bloccare la sync se qualcosa va storto
        pass

    # 3) risposta websocket
    connection.send_result(msg["id"], res)



def _normalize_plate(s: str) -> str:
    # Normalizzazione semplice lato backend:
    # uppercase, rimuovi spazi e separatori comuni
    s = (s or "").strip().upper()
    s = s.replace(" ", "").replace("-", "").replace(".", "")
    return s

@callback
def publish_plates_update(hass: HomeAssistant, plates: dict) -> None:
    d = _data(hass)
    d["plates"] = plates or {"updated_at": None, "items": {}}

    payload = dict(d["plates"])
    payload["scan_cars"] = _is_scan_cars_enabled(hass)

    hass.bus.async_fire(EVENT_PLATES_UPDATED, payload)


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_GET_PLATES,
        vol.Required("id"): int,
    }
)

@websocket_api.async_response
async def ws_get_plates(hass, connection, msg) -> None:
    d = _data(hass)
    plates = d.get("plates") or {"updated_at": None, "items": {}}

    out = dict(plates)
    out["scan_cars"] = _is_scan_cars_enabled(hass)

    connection.send_result(msg["id"], out)


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_SET_PLATES,
        vol.Required("id"): int,
        vol.Required("items"): dict,  # plate -> name
    }
)
@websocket_api.async_response
async def ws_set_plates(hass, connection, msg) -> None:
    d = _data(hass)

    raw_items = msg.get("items") or {}
    items: dict[str, str] = {}

    # pulizia + normalizzazione
    for k, v in raw_items.items():
        plate = _normalize_plate(str(k))
        name = (str(v) if v is not None else "").strip()
        if not plate:
            continue
        if not name:
            # se name vuoto -> non salvare (equivale a delete)
            continue
        items[plate] = name

    plates = {
        "updated_at": dt_util.utcnow().replace(microsecond=0).isoformat() + "Z",
        "items": dict(sorted(items.items())),
    }

    # salva su store se presente (protetto da lock)
    locks = get_locks(hass)
    async with locks.plates:
        store = d.get("plates_store")
        if store is not None:
            try:
                await store.async_save(plates)
            except Exception:
                pass
        d["plates"] = plates

    publish_plates_update(hass, plates)
    connection.send_result(msg["id"], {"ok": True, "count": len(plates["items"])})

@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_SUBSCRIBE_PLATES,
        vol.Required("id"): int,
    }
)
@websocket_api.async_response
async def ws_subscribe_plates(hass, connection, msg) -> None:
    unsub = _subscribe_event(hass, connection, msg["id"], EVENT_PLATES_UPDATED)
    connection.subscriptions[msg["id"]] = unsub
    connection.send_result(msg["id"], {"subscribed": True})


# ----------------- ROI -----------------

def _get_first_entry(hass: HomeAssistant) -> ConfigEntry | None:
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None


def _roi_payload_from_entry(entry: ConfigEntry | None) -> Dict[str, Any]:
    if entry is None:
        return {"updated_at": None, "by_camera": {}}
    opts = dict(entry.options or {})
    roi = opts.get("roi_by_camera")
    if not isinstance(roi, dict):
        roi = {}
    # sanitize: ensure lists
    out: Dict[str, Any] = {}
    for cam, rois in roi.items():
        if isinstance(cam, str) and isinstance(rois, list):
            out[cam] = rois
    return {"updated_at": dt_util.utcnow().replace(microsecond=0).isoformat() + "Z", "by_camera": out}


@callback
def publish_roi_update(hass: HomeAssistant, payload: dict) -> None:
    hass.bus.async_fire(EVENT_ROI_UPDATED, payload)


@websocket_api.websocket_command({vol.Required("type"): WS_GET_ROI})
@websocket_api.async_response
async def ws_get_roi(hass, connection, msg) -> None:
    entry = _get_first_entry(hass)
    # We do NOT update entry.options here; only read.
    payload = _roi_payload_from_entry(entry)
    connection.send_result(msg["id"], payload)


_ROI_ITEM = vol.Schema(
    {
        vol.Required("id"): str,
        vol.Optional("name", default=""): str,
        vol.Required("x"): vol.Coerce(float),
        vol.Required("y"): vol.Coerce(float),
        vol.Required("w"): vol.Coerce(float),
        vol.Required("h"): vol.Coerce(float),
    }
)


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_SET_ROI,
        vol.Required("by_camera"): {str: [_ROI_ITEM]},
    }
)
@websocket_api.async_response
async def ws_set_roi(hass, connection, msg) -> None:
    entry = _get_first_entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_found", "No config entry for domain")
        return

    by_camera: Dict[str, Any] = msg.get("by_camera") or {}

    def clamp01(v: float) -> float:
        try:
            v = float(v)
        except Exception:
            v = 0.0
        return max(0.0, min(1.0, v))

    cleaned: Dict[str, Any] = {}
    for cam, rois in by_camera.items():
        if not isinstance(cam, str) or not isinstance(rois, list):
            continue
        out_list = []
        for r in rois:
            if not isinstance(r, dict):
                continue
            rid = str(r.get("id") or "").strip()
            if not rid:
                continue
            name = str(r.get("name") or "").strip()
            x = clamp01(r.get("x", 0))
            y = clamp01(r.get("y", 0))
            w = clamp01(r.get("w", 0))
            h = clamp01(r.get("h", 0))
            # reject tiny/zero
            if w <= 0.001 or h <= 0.001:
                continue
            out_list.append({"id": rid, "name": name, "x": x, "y": y, "w": w, "h": h})
        cleaned[cam] = out_list

    new_opts = dict(entry.options or {})
    new_opts["roi_by_camera"] = cleaned
    hass.config_entries.async_update_entry(entry, options=new_opts)

    payload = {"updated_at": dt_util.utcnow().replace(microsecond=0).isoformat() + "Z", "by_camera": cleaned}
    publish_roi_update(hass, payload)
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command({vol.Required("type"): WS_SUBSCRIBE_ROI})
@websocket_api.async_response
async def ws_subscribe_roi(hass, connection, msg) -> None:
    unsub = _subscribe_event(hass, connection, msg["id"], EVENT_ROI_UPDATED)
    connection.subscriptions[msg["id"]] = unsub
    connection.send_result(msg["id"], {"subscribed": True})
