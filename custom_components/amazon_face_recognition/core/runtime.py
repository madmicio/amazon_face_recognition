"""AFR runtime state (hass.data[DOMAIN]) + concurrency locks."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict

from homeassistant.core import HomeAssistant

from ..const import DOMAIN


@dataclass(slots=True)
class AFRLocks:
    """Locks for shared resources."""

    gallery: asyncio.Lock
    plates: asyncio.Lock
    s3_sync: asyncio.Lock
    index: asyncio.Lock
    faces_index: asyncio.Lock


def _default_public_state() -> Dict[str, Any]:
    return {
        "last_result": {},
        "index": {"updated_at": None, "items": []},
        "faces_index": {"updated_at": None, "persons": {}},
        "gallery": {"updated_at": None, "persons": {}},
        "gallery_store": None,
        "_gallery_loaded": False,
        "plates": {"updated_at": None, "items": {}},
        "plates_store": None,
        "_plates_loaded": False,
        "usage": {
            "month": None,
            "scans_month": 0,
            "aws_calls_month": 0,
            "last_month_scans": 0,
            "last_month_api_calls": 0,
        },
    }


def get_domain_data(hass: HomeAssistant) -> Dict[str, Any]:
    """Return `hass.data[DOMAIN]` and ensure it contains required keys."""
    data: Dict[str, Any] = hass.data.setdefault(DOMAIN, {})

    # locks
    locks = data.get("_locks")
    if not isinstance(locks, AFRLocks):
        data["_locks"] = AFRLocks(
            gallery=asyncio.Lock(),
            plates=asyncio.Lock(),
            s3_sync=asyncio.Lock(),
            index=asyncio.Lock(),
            faces_index=asyncio.Lock(),
        )

    # optional cloud gallery container
    data.setdefault("s3", {})  # entry_id -> {client,bucket,prefix}

    # multi-entry containers
    data.setdefault("clients", {})
    data.setdefault("processors", {})

    # misc flags
    data.setdefault("_ws_registered", False)
    data.setdefault("_services_registered", False)
    data.setdefault("_panel_registered", False)
    data.setdefault("_views_registered", False)
    data.setdefault("_usage_loaded", False)

    # public state
    for k, v in _default_public_state().items():
        data.setdefault(k, v)

    return data


def get_locks(hass: HomeAssistant) -> AFRLocks:
    data = get_domain_data(hass)
    return data["_locks"]
