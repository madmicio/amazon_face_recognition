from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORE_VERSION = 1
STORE_KEY = f"{DOMAIN}_plates"

DEFAULT_PLATES: dict[str, Any] = {
    "updated_at": None,
    "items": {},  # plate -> name
}


class AFRPlatesStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store = Store(hass, STORE_VERSION, STORE_KEY)

    async def async_load(self) -> dict[str, Any]:
        data = await self._store.async_load()
        out = dict(DEFAULT_PLATES)
        if isinstance(data, dict):
            out.update(data)

        if not isinstance(out.get("items"), dict):
            out["items"] = {}
        return out

    async def async_save(self, plates: dict[str, Any]) -> None:
        out = dict(DEFAULT_PLATES)
        if isinstance(plates, dict):
            out.update(plates)

        if not isinstance(out.get("items"), dict):
            out["items"] = {}

        await self._store.async_save(out)
