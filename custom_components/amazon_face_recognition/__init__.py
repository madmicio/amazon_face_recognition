"""Amazon Face Recognition integration.

Public entrypoints for Home Assistant are kept here, but the implementation lives
in subpackages (core/, processing/, api/, stores/, sync/, services/).

NOTE: `frontend/aws-face-recognition-card.js` is intentionally left untouched.
"""

from __future__ import annotations

from .core.bootstrap import async_setup, async_setup_entry, async_unload_entry

__all__ = [
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
]
