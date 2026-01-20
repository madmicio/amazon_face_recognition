from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..const import DOMAIN
from ..util.debounce import DebouncedAsyncSaver

_LOGGER = logging.getLogger(__name__)

STORE_VERSION = 1
STORE_KEY = f"{DOMAIN}_plates"

DEFAULT_PLATES: dict[str, Any] = {
    "updated_at": None,
    "items": {},  # plate -> name
}


def _normalize_plates(plates: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(DEFAULT_PLATES)
    if isinstance(plates, dict):
        out.update(plates)
    if not isinstance(out.get("items"), dict):
        out["items"] = {}
    return out


class AFRPlatesStore:
    """HA storage wrapper for plates mapping.

    Supports both immediate saves and debounced saves.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store = Store(hass, STORE_VERSION, STORE_KEY)
        self._debouncer = DebouncedAsyncSaver(
            hass,
            delay=1.0,
            save_fn=self._async_save_raw,
            eq_fn=lambda a, b: a == b,
        )

    async def async_load(self) -> dict[str, Any]:
        data = await self._store.async_load()
        plates = _normalize_plates(data if isinstance(data, dict) else None)
        self._debouncer.set_last_saved(plates)
        return plates

    async def _async_save_raw(self, plates: dict[str, Any]) -> None:
        await self._store.async_save(_normalize_plates(plates))

    async def async_save(self, plates: dict[str, Any]) -> None:
        normalized = _normalize_plates(plates)
        await self._async_save_raw(normalized)
        self._debouncer.set_last_saved(normalized)

    def schedule_save(self, plates: dict[str, Any]) -> None:
        self._debouncer.schedule(_normalize_plates(plates))
