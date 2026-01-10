"""Amazon Face Recognition integration."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.frontend import add_extra_js_url

from .const import DOMAIN
from .websocket import async_register_websockets


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    # inizializza storage runtime
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("last_result", {})
    hass.data[DOMAIN].setdefault("index", {"updated_at": None, "items": []})

    # websocket
    async_register_websockets(hass)

    # serve la cartella frontend con la card
    hass.http.register_static_path(
        "/amazon_face_recognition",
        hass.config.path("custom_components/amazon_face_recognition/frontend"),
        cache_headers=False,
    )

    # carica automaticamente il JS nel frontend (no resource manuale)
    add_extra_js_url(hass, "/amazon_face_recognition/aws-face-recognition-card.js")

    return True

