from __future__ import annotations

"""File-backed face gallery store.

We intentionally avoid Home Assistant's .storage Store for the face gallery.
Historically, storing the gallery as a plain JSON file under /config/amazon_face_gallery
proved far more reliable for external synchronization (e.g. S3) and for avoiding
stale cache issues.

Source of truth (local):
  /config/amazon_face_gallery/gallery.json

Training images (local):
  /config/amazon_face_gallery/training_cache/<Person>/<image>.

This store keeps the public API compatible with the previous Store-based
implementation: async_load(), async_save(), schedule_save().
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

from ..const import DOMAIN, TRAINING_ROOT_DIRNAME
from ..util.debounce import DebouncedAsyncSaver

_LOGGER = logging.getLogger(__name__)

DEFAULT_GALLERY: dict[str, Any] = {
    "updated_at": None,
    "persons": {},
}


def _normalize_gallery(gallery: dict[str, Any] | None) -> dict[str, Any]:
    # Backward compatibility:
    # - Home Assistant Store files contain a wrapper like {"version":..., "key":..., "data": {...}}.
    #   If we ever read a legacy Store blob (from old local .storage or old S3 backups),
    #   unwrap it transparently.
    if isinstance(gallery, dict) and isinstance(gallery.get("data"), dict):
        inner = gallery.get("data")
        if isinstance(inner, dict) and isinstance(inner.get("persons"), (dict, list)):
            gallery = inner

    g = dict(DEFAULT_GALLERY)
    if isinstance(gallery, dict):
        g.update(gallery)
    if not isinstance(g.get("persons"), dict):
        g["persons"] = {}
    return g


def _gallery_file(hass: HomeAssistant) -> Path:
    # /config/amazon_face_gallery/gallery.json
    return Path(hass.config.path(TRAINING_ROOT_DIRNAME, "gallery.json"))


def _legacy_ha_storage_file(hass: HomeAssistant) -> Path:
    # legacy: /config/.storage/amazon_face_recognition_gallery
    return Path(hass.config.path(".storage", f"{DOMAIN}_gallery"))


def _read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    # compact, but readable enough for debugging
    data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False)
    tmp.write_text(data, encoding="utf-8")
    os.replace(str(tmp), str(path))


class AFRGalleryStore:
    """File-backed store for the face gallery.

    Supports both immediate saves and debounced (batched) saves.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._path = _gallery_file(hass)
        self._legacy_path = _legacy_ha_storage_file(hass)
        self._debouncer = DebouncedAsyncSaver(
            hass,
            delay=1.2,
            save_fn=self._async_save_raw,
            eq_fn=lambda a, b: a == b,
        )

    async def async_load(self) -> dict[str, Any]:
        # 1) Prefer the new file-backed store
        data = await self.hass.async_add_executor_job(_read_json_file, self._path)

        # 2) One-time migration from legacy HA .storage, if present.
        if data is None and self._legacy_path.exists():
            legacy = await self.hass.async_add_executor_job(_read_json_file, self._legacy_path)
            if isinstance(legacy, dict):
                try:
                    await self.hass.async_add_executor_job(
                        _atomic_write_json, self._path, _normalize_gallery(legacy)
                    )
                    data = legacy
                    _LOGGER.info("%s: migrated gallery store from .storage to %s", DOMAIN, self._path)
                except Exception as e:
                    _LOGGER.warning("%s: failed migrating gallery store: %s", DOMAIN, e)

        gallery = _normalize_gallery(data if isinstance(data, dict) else None)
        self._debouncer.set_last_saved(gallery)
        return gallery

    async def _async_save_raw(self, gallery: dict[str, Any]) -> None:
        normalized = _normalize_gallery(gallery)
        await self.hass.async_add_executor_job(_atomic_write_json, self._path, normalized)

    async def async_save(self, gallery: dict[str, Any]) -> None:
        """Immediate save (no debounce)."""
        normalized = _normalize_gallery(gallery)
        await self._async_save_raw(normalized)
        self._debouncer.set_last_saved(normalized)

    def schedule_save(self, gallery: dict[str, Any]) -> None:
        """Debounced save (batch multiple updates)."""
        self._debouncer.schedule(_normalize_gallery(gallery))
