from __future__ import annotations

from typing import Any, Dict

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.components import websocket_api

from .const import (
    DOMAIN,
    EVENT_UPDATED,
    EVENT_FACES_UPDATED,
    WS_GET_LAST_RESULT,
    WS_GET_INDEX,
    WS_SUBSCRIBE_UPDATES,
    WS_GET_FACES_INDEX,
    WS_SUBSCRIBE_FACES,
)

DEFAULT_INDEX: Dict[str, Any] = {"updated_at": None, "items": []}
DEFAULT_FACES_INDEX: Dict[str, Any] = {"updated_at": None, "persons": {}}


def _data(hass: HomeAssistant) -> dict:
    return hass.data.setdefault(DOMAIN, {})


def async_register_websockets(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_get_last_result)
    websocket_api.async_register_command(hass, ws_get_index)
    websocket_api.async_register_command(hass, ws_subscribe_updates)
    websocket_api.async_register_command(hass, ws_get_faces_index)
    websocket_api.async_register_command(hass, ws_subscribe_faces)


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
    connection.send_result(msg["id"], d.get("last_result", {}) or {})


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
