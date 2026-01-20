"""Options handling helpers.

Home Assistant ConfigEntry.options may be empty right after initial install,
even if the UI shows defaults. We therefore merge defaults explicitly so
runtime behavior matches what the user sees without requiring an options
toggle/save roundtrip.
"""

from __future__ import annotations

from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry

from ..const import (
    CONF_SCALE,
    CONF_MAX_SAVED_FILES,
    CONF_SAVE_FILE_FORMAT,
    CONF_SAVE_TIMESTAMPED_FILE,
    CONF_ALWAYS_SAVE_LATEST_FILE,
    CONF_SHOW_BOXES,
    CONF_MAX_RED_BOXES,
    CONF_MIN_RED_BOX_AREA,
    CONF_MIN_RED_BOX_AREA_PCT,
    CONF_AWS_API_COST,
    CONF_DEFAULT_MIN_CONFIDENCE,
    CONF_TARGETS_CONFIDENCE,
    CONF_EXCLUDE_TARGETS,
    CONF_EXCLUDED_OBJECT_LABELS,
    CONF_LABEL_FONT_LEVEL,
    CONF_SCAN_CARS,
    CONF_VEHICLE_AREA_ABS_MIN,
    CONF_MAX_VEHICLES_TO_SCAN,
    CONF_CLOUD_GALLERY_ENABLED,
    CONF_CLOUD_GALLERY_PREFIX,
    CONF_CLOUD_GALLERY_SYNC_ON_STARTUP,
    CONF_CLOUD_SCAN_UPLOAD_ENABLED,
    DEFAULT_SCALE,
    DEFAULT_MAX_SAVED_FILES,
    DEFAULT_SAVE_FILE_FORMAT,
    DEFAULT_SAVE_TIMESTAMPED_FILE,
    DEFAULT_ALWAYS_SAVE_LATEST_FILE,
    DEFAULT_SHOW_BOXES,
    DEFAULT_MAX_RED_BOXES,
    DEFAULT_MIN_RED_BOX_AREA,
    DEFAULT_MIN_RED_BOX_AREA_PCT,
    DEFAULT_AWS_API_COST,
    DEFAULT_DEFAULT_MIN_CONFIDENCE,
    DEFAULT_TARGETS_CONFIDENCE,
    DEFAULT_EXCLUDE_TARGETS,
    DEFAULT_EXCLUDED_OBJECT_LABELS,
    DEFAULT_LABEL_FONT_LEVEL,
    DEFAULT_VEHICLE_AREA_ABS_MIN,
    DEFAULT_MAX_VEHICLES_TO_SCAN,
)


DEFAULTS: Dict[str, Any] = {
    CONF_SCALE: DEFAULT_SCALE,
    CONF_MAX_SAVED_FILES: DEFAULT_MAX_SAVED_FILES,
    CONF_SAVE_FILE_FORMAT: DEFAULT_SAVE_FILE_FORMAT,
    CONF_SAVE_TIMESTAMPED_FILE: DEFAULT_SAVE_TIMESTAMPED_FILE,
    CONF_ALWAYS_SAVE_LATEST_FILE: DEFAULT_ALWAYS_SAVE_LATEST_FILE,
    CONF_SHOW_BOXES: DEFAULT_SHOW_BOXES,
    CONF_MAX_RED_BOXES: DEFAULT_MAX_RED_BOXES,
    CONF_MIN_RED_BOX_AREA: DEFAULT_MIN_RED_BOX_AREA,
    CONF_MIN_RED_BOX_AREA_PCT: DEFAULT_MIN_RED_BOX_AREA_PCT,
    CONF_AWS_API_COST: DEFAULT_AWS_API_COST,
    CONF_DEFAULT_MIN_CONFIDENCE: DEFAULT_DEFAULT_MIN_CONFIDENCE,
    CONF_TARGETS_CONFIDENCE: DEFAULT_TARGETS_CONFIDENCE,
    CONF_EXCLUDE_TARGETS: DEFAULT_EXCLUDE_TARGETS,
    CONF_EXCLUDED_OBJECT_LABELS: DEFAULT_EXCLUDED_OBJECT_LABELS,
    CONF_LABEL_FONT_LEVEL: DEFAULT_LABEL_FONT_LEVEL,
    CONF_SCAN_CARS: False,
    CONF_VEHICLE_AREA_ABS_MIN: DEFAULT_VEHICLE_AREA_ABS_MIN,
    CONF_MAX_VEHICLES_TO_SCAN: DEFAULT_MAX_VEHICLES_TO_SCAN,
    # cloud flags (keep previous behavior: enabled+sync by default)
    CONF_CLOUD_GALLERY_ENABLED: True,
    CONF_CLOUD_GALLERY_SYNC_ON_STARTUP: True,
    CONF_CLOUD_SCAN_UPLOAD_ENABLED: False,
}


def merge_defaults(options: Dict[str, Any] | None) -> Dict[str, Any]:
    """Return a new dict with DEFAULTS filled for missing keys."""
    merged = dict(DEFAULTS)
    if isinstance(options, dict):
        merged.update(options)
    # Normalize empty prefix to None-ish (handled elsewhere)
    if merged.get(CONF_CLOUD_GALLERY_PREFIX) in (None, ""):
        merged.pop(CONF_CLOUD_GALLERY_PREFIX, None)
    return merged


def get_entry_options(entry: ConfigEntry) -> Dict[str, Any]:
    """Get merged options for an entry (defaults + entry.options)."""
    return merge_defaults(dict(entry.options or {}))
