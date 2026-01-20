from __future__ import annotations

import datetime
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.event import async_call_later

from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORE_VERSION = 1
STORE_KEY = f"{DOMAIN}_usage"

DEFAULT_USAGE: dict[str, Any] = {
    "month": None,
    "scans_month": 0,
    "aws_calls_month": 0,
    "last_month_scans": 0,
    "last_month_api_calls": 0,
}


def _month_key_now() -> str:
    return datetime.datetime.now().strftime("%Y-%m")


def _rollover_if_needed(usage: dict[str, Any]) -> None:
    cur = _month_key_now()
    if usage.get("month") != cur:
        usage["last_month_scans"] = int(usage.get("scans_month") or 0)
        usage["last_month_api_calls"] = int(usage.get("aws_calls_month") or 0)
        usage["scans_month"] = 0
        usage["aws_calls_month"] = 0
        usage["month"] = cur


class AFRUsageStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store = Store(hass, STORE_VERSION, STORE_KEY)
        self._save_cancel = None  # cancel function from async_call_later

    async def async_load(self) -> dict[str, Any]:
        data = await self._store.async_load()
        usage = dict(DEFAULT_USAGE)

        if isinstance(data, dict):
            usage.update(data)

        _rollover_if_needed(usage)
        return usage

    async def async_save(self, usage: dict[str, Any] | None = None) -> None:
        if usage is None:
            usage = (self.hass.data.get(DOMAIN, {}) or {}).get("usage") or dict(DEFAULT_USAGE)

        usage = dict(DEFAULT_USAGE) | dict(usage)
        _rollover_if_needed(usage)

        await self._store.async_save(usage)

    def schedule_save(self) -> None:
        # debounce: salva una sola volta anche se incrementi 50 volte di fila
        if self._save_cancel is not None:
            return

        @callback
        def _do_save(_now) -> None:
            self._save_cancel = None
            self.hass.async_create_task(self.async_save())

        self._save_cancel = async_call_later(self.hass, 2.0, _do_save)

    def increment(self, scans_delta: int = 0, aws_calls_delta: int = 0) -> None:
        data = self.hass.data.setdefault(DOMAIN, {})
        usage = data.setdefault("usage", dict(DEFAULT_USAGE))

        _rollover_if_needed(usage)

        usage["scans_month"] = int(usage.get("scans_month") or 0) + int(scans_delta or 0)
        usage["aws_calls_month"] = int(usage.get("aws_calls_month") or 0) + int(aws_calls_delta or 0)

        self.schedule_save()
