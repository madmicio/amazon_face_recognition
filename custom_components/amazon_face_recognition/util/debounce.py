from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

_LOGGER = logging.getLogger(__name__)


class DebouncedAsyncSaver:
    """Debounce calls to an async save function.

    This is intentionally minimal:
    - keeps only the latest payload
    - schedules a single save after `delay` seconds
    - optionally skips saving if payload is equal to last_saved
    """

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        delay: float = 1.0,
        save_fn: Callable[[Any], Awaitable[None]],
        eq_fn: Optional[Callable[[Any, Any], bool]] = None,
    ) -> None:
        self.hass = hass
        self.delay = float(delay)
        self._save_fn = save_fn
        self._eq_fn = eq_fn
        self._cancel = None
        self._pending: Any = None
        self._has_pending = False
        self._last_saved: Any = None
        self._saving = False

    def set_last_saved(self, payload: Any) -> None:
        self._last_saved = payload

    def schedule(self, payload: Any) -> None:
        self._pending = payload
        self._has_pending = True

        if self._cancel is not None:
            return

        @callback
        def _do_save(_now) -> None:
            self._cancel = None
            self.hass.async_create_task(self._async_flush())

        self._cancel = async_call_later(self.hass, self.delay, _do_save)

    async def _async_flush(self) -> None:
        if self._saving:
            # if a flush is already running, let it finish; a new schedule will re-trigger
            return

        if not self._has_pending:
            return

        payload = self._pending
        self._pending = None
        self._has_pending = False

        if self._eq_fn is not None and self._last_saved is not None:
            try:
                if self._eq_fn(payload, self._last_saved):
                    return
            except Exception:
                # if comparison fails, save anyway
                pass

        self._saving = True
        try:
            await self._save_fn(payload)
            self._last_saved = payload
        except Exception as e:
            _LOGGER.debug("Debounced save failed: %s", e)
        finally:
            self._saving = False

            # if new pending arrived while saving, schedule another flush soon
            if self._has_pending and self._cancel is None:
                self.schedule(self._pending)
