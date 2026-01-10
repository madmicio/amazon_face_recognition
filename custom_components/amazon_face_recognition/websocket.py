from __future__ import annotations

import voluptuous as vol
from homeassistant.core import HomeAssistant, callback
from homeassistant.components import websocket_api

from .const import DOMAIN, EVENT_UPDATED


def async_register_websockets(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_get_last_result)
    websocket_api.async_register_command(hass, ws_get_index)
    websocket_api.async_register_command(hass, ws_subscribe_updates)


@websocket_api.websocket_command(
    {vol.Required("type"): "amazon_face_recognition/get_last_result"}
)
@websocket_api.async_response
async def ws_get_last_result(hass: HomeAssistant, connection, msg) -> None:
    data = hass.data.get(DOMAIN, {})
    connection.send_result(msg["id"], data.get("last_result", {}))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "amazon_face_recognition/get_index",
        vol.Optional("limit", default=20): vol.Coerce(int),
    }
)
@websocket_api.async_response
async def ws_get_index(hass: HomeAssistant, connection, msg) -> None:
    data = hass.data.get(DOMAIN, {})
    index = data.get("index", {"updated_at": None, "items": []})

    limit = max(1, min(int(msg["limit"]), 500))
    connection.send_result(
        msg["id"],
        {"updated_at": index.get("updated_at"), "items": (index.get("items") or [])[:limit]},
    )


@websocket_api.websocket_command(
    {vol.Required("type"): "amazon_face_recognition/subscribe_updates"}
)
@websocket_api.async_response
async def ws_subscribe_updates(hass: HomeAssistant, connection, msg) -> None:
    @callback
    def _forward(event) -> None:
        # manda l'evento alla card come websocket "event"
        connection.send_message(websocket_api.event_message(msg["id"], event.data))

    unsub = hass.bus.async_listen(EVENT_UPDATED, _forward)
    connection.subscriptions[msg["id"]] = unsub
    connection.send_result(msg["id"], {"subscribed": True})
