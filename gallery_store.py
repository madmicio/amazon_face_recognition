from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORE_VERSION = 1
STORE_KEY = f"{DOMAIN}_gallery"

DEFAULT_GALLERY: dict[str, Any] = {
    "updated_at": None,
    "persons": {},
}

class AFRGalleryStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store = Store(hass, STORE_VERSION, STORE_KEY)

    async def async_load(self) -> dict[str, Any]:
        data = await self._store.async_load()
        gallery = dict(DEFAULT_GALLERY)
        if isinstance(data, dict):
            gallery.update(data)

        if not isinstance(gallery.get("persons"), dict):
            gallery["persons"] = {}
        return gallery

    async def async_save(self, gallery: dict[str, Any]) -> None:
        g = dict(DEFAULT_GALLERY)
        if isinstance(gallery, dict):
            g.update(gallery)

        if not isinstance(g.get("persons"), dict):
            g["persons"] = {}

        await self._store.async_save(g)
