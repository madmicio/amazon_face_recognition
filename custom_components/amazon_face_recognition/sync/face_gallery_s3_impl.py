"""Face gallery bidirectional sync with S3.

This module syncs ONLY the local face gallery cache (training_cache + gallery store)
to/from S3.

It intentionally does NOT touch local annotated snapshots.
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..const import DOMAIN, TRAINING_ROOT_DIRNAME

_LOGGER = logging.getLogger(__name__)


def _utc_iso_now() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _local_training_cache_root(hass) -> Path:
    # Keep consistent with integration folder creation.
    return Path(hass.config.path(TRAINING_ROOT_DIRNAME, "training_cache"))


def _local_gallery_storage_file(hass) -> Path:
    """Return the local JSON file that contains the face gallery.

    Source of truth (local): /config/amazon_face_gallery/gallery.json
    (We intentionally avoid HA .storage for the face gallery.)
    """
    return Path(hass.config.path(TRAINING_ROOT_DIRNAME, "gallery.json"))


def _local_gallery_legacy_file(hass) -> Path:
    """Legacy HA Store file path (older versions).

    Kept only for migration / backward-compat downloads.
    """
    return Path(hass.config.path(".storage", f"{DOMAIN}_gallery"))


def _s3_base(prefix: str) -> str:
    # Reuse cloud_gallery_prefix but isolate face gallery under a stable subfolder.
    p = (prefix or "").strip("/")
    return f"{p}/face_gallery".strip("/")


def _s3_keys(prefix: str) -> Tuple[str, str, str]:
    base = _s3_base(prefix)
    # Current keys
    gallery_key = f"{base}/gallery.json"
    manifest_key = f"{base}/manifest.json"
    cache_prefix = f"{base}/training_cache/"
    return gallery_key, manifest_key, cache_prefix


def _s3_legacy_gallery_keys(prefix: str) -> List[str]:
    """Legacy keys used by previous iterations.

    We accept these on download so users can upgrade without wiping S3.
    """
    base = _s3_base(prefix)
    return [
        f"{base}/{DOMAIN}_gallery",        # old: raw HA .storage filename
        f"{base}/gallery_store.json",      # old: custom name used in some builds
    ]


def _iter_local_files(cache_root: Path) -> Iterable[Path]:
    if not cache_root.exists():
        return []
    # training_cache/<Person>/<file>
    out: List[Path] = []
    for p in cache_root.rglob("*"):
        if p.is_file():
            out.append(p)
    return out


def _rel_from_cache_root(cache_root: Path, file_path: Path) -> str:
    rel = file_path.relative_to(cache_root)
    return str(rel).replace("\\", "/")


def _list_local_cache_rels(cache_root: Path) -> List[str]:
    rels: List[str] = []
    for fp in _iter_local_files(cache_root):
        try:
            rels.append(_rel_from_cache_root(cache_root, fp))
        except Exception:
            continue
    rels.sort()
    return rels


def s3_put_json(s3_client, bucket: str, key: str, payload: Dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    s3_client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")


def s3_get_json(s3_client, bucket: str, key: str) -> Optional[Dict[str, Any]]:
    try:
        obj = s3_client.get_object(Bucket=bucket, Key=key)
        raw = obj["Body"].read()
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def s3_list_keys(s3_client, bucket: str, prefix: str) -> List[str]:
    """Return list of keys under prefix."""
    return list(s3_list_objects(s3_client, bucket, prefix).keys())


def s3_list_objects(s3_client, bucket: str, prefix: str) -> Dict[str, Dict[str, Any]]:
    """Return mapping Key -> {Size, ETag, LastModified}.

    Uses list_objects_v2 and is safe for pagination.
    """
    out: Dict[str, Dict[str, Any]] = {}
    token = None
    while True:
        kwargs = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3_client.list_objects_v2(**kwargs)
        for it in resp.get("Contents") or []:
            k = it.get("Key")
            if not k:
                continue
            out[k] = {
                "Size": int(it.get("Size") or 0),
                "ETag": (it.get("ETag") or "").strip('"') if isinstance(it.get("ETag"), str) else "",
                "LastModified": it.get("LastModified"),
            }
        if resp.get("IsTruncated"):
            token = resp.get("NextContinuationToken")
            continue
        break
    return out


def s3_upload_file(s3_client, bucket: str, key: str, local_path: Path) -> None:
    s3_client.upload_file(str(local_path), bucket, key)


def s3_head_size(s3_client, bucket: str, key: str) -> int | None:
    try:
        r = s3_client.head_object(Bucket=bucket, Key=key)
        return int(r.get("ContentLength") or 0)
    except Exception:
        return None


def s3_download_file(s3_client, bucket: str, key: str, local_path: Path) -> None:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    s3_client.download_file(bucket, key, str(local_path))


def s3_delete_keys(s3_client, bucket: str, keys: Iterable[str]) -> None:
    batch: List[str] = []
    for k in keys:
        if not k:
            continue
        batch.append(k)
        if len(batch) >= 1000:
            s3_client.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": x} for x in batch]})
            batch.clear()
    if batch:
        s3_client.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": x} for x in batch]})


def sync_up_face_gallery(
    s3_client,
    bucket: str,
    prefix: str,
    cache_root: Path,
    storage_path: Path,
) -> None:
    """Upload local training_cache + gallery.json to S3 (best effort).

    S3 is kept aligned with local state:
      - upload gallery.json
      - upload training_cache files
      - (best effort) prune remote files that no longer exist locally
    """
    gallery_key, manifest_key, cache_prefix = _s3_keys(prefix)

    # Upload gallery.json (if present)
    try:
        if storage_path.exists() and storage_path.is_file():
            s3_upload_file(s3_client, bucket, gallery_key, storage_path)
    except Exception as e:
        _LOGGER.debug("%s: face gallery upload failed (gallery.json): %s", DOMAIN, e)

    # Remote listing once (fast path)
    local_files = _list_local_cache_rels(cache_root)
    local_set = set(local_files)
    remote_map: Dict[str, Dict[str, Any]] = {}
    try:
        remote_map = s3_list_objects(s3_client, bucket, cache_prefix)
    except Exception as e:
        _LOGGER.debug("%s: face gallery remote list failed: %s", DOMAIN, e)

    # Remove remote files that are no longer present locally (keep S3 identical)
    try:
        to_delete: List[str] = []
        for k in remote_map.keys():
            if not k.startswith(cache_prefix):
                continue
            rel = k[len(cache_prefix):]
            if rel and rel not in local_set:
                to_delete.append(k)
        if to_delete:
            s3_delete_keys(s3_client, bucket, to_delete)
    except Exception as e:
        _LOGGER.debug("%s: face gallery remote prune failed: %s", DOMAIN, e)

    # Upload only missing or changed (by size)
    for rel in local_files:
        lp = cache_root / rel
        key = f"{cache_prefix}{rel}"
        try:
            local_size = int(lp.stat().st_size)
        except Exception:
            local_size = -1

        remote_size = None
        if key in remote_map:
            try:
                remote_size = int(remote_map[key].get("Size") or 0)
            except Exception:
                remote_size = None

        if remote_size is not None and local_size >= 0 and remote_size == local_size:
            continue

        try:
            s3_upload_file(s3_client, bucket, key, lp)
        except Exception as e:
            _LOGGER.debug("%s: face gallery file upload failed %s: %s", DOMAIN, key, e)

    # Write a small manifest (debug + quicker sanity checks)
    try:
        payload = {
            "updated_at": _utc_iso_now(),
            "gallery_key": gallery_key,
            "training_cache_count": len(local_files),
            "training_cache": local_files,
        }
        s3_put_json(s3_client, bucket, manifest_key, payload)
    except Exception:
        pass


def sync_down_face_gallery(
    s3_client,
    bucket: str,
    prefix: str,
    cache_root: Path,
    storage_path: Path,
    force_align: bool,
) -> Tuple[bool, int, int]:
    """Download S3 face gallery into local training_cache.

    Returns: (store_downloaded, downloaded_files, deleted_local_files)
    """
    gallery_key, _manifest_key, cache_prefix = _s3_keys(prefix)

    # Download gallery.json (or legacy equivalents) - only if missing/changed.
    store_downloaded = False

    def _download_if_needed(key: str) -> bool:
        remote_size = s3_head_size(s3_client, bucket, key)
        if remote_size is None:
            return False
        local_size = int(storage_path.stat().st_size) if storage_path.exists() else None
        if local_size is not None and int(remote_size) == int(local_size):
            return False
        s3_download_file(s3_client, bucket, key, storage_path)
        return True

    try:
        store_downloaded = _download_if_needed(gallery_key)
    except Exception:
        store_downloaded = False

    # Backward compatibility: try legacy keys if gallery.json does not exist remotely.
    # IMPORTANT: we base this on the remote presence, not on whether a local file exists,
    # otherwise upgrades would never download legacy S3 data.
    if s3_head_size(s3_client, bucket, gallery_key) is None:
        for legacy_key in _s3_legacy_gallery_keys(prefix):
            try:
                if _download_if_needed(legacy_key):
                    store_downloaded = True
                    break
            except Exception:
                continue

    # Derive cache listing from remote objects.
    remote_map = s3_list_objects(s3_client, bucket, cache_prefix)

    remote_rels: List[str] = []
    for k in remote_map.keys():
        if not k.startswith(cache_prefix):
            continue
        rel = k[len(cache_prefix):]
        if rel:
            remote_rels.append(rel)
    remote_rels.sort()

    remote_set = set(remote_rels)

    downloaded = 0
    for rel in remote_rels:
        key = f"{cache_prefix}{rel}"
        lp = cache_root / rel

        remote_size = None
        try:
            remote_size = int(remote_map.get(key, {}).get("Size") or 0)
        except Exception:
            remote_size = None

        if lp.exists() and lp.is_file() and remote_size is not None:
            try:
                local_size = int(lp.stat().st_size)
                if local_size == remote_size:
                    continue
            except Exception:
                pass

        try:
            s3_download_file(s3_client, bucket, key, lp)
            downloaded += 1
        except Exception as e:
            _LOGGER.debug("%s: face gallery download failed %s: %s", DOMAIN, key, e)

    deleted = 0
    if force_align:
        # Remove local files not present on S3
        for lp in _iter_local_files(cache_root):
            try:
                rel = _rel_from_cache_root(cache_root, lp)
            except Exception:
                continue
            if rel not in remote_set:
                try:
                    lp.unlink(missing_ok=True)
                    deleted += 1
                except Exception:
                    pass

    return store_downloaded, downloaded, deleted


async def async_face_gallery_sync_from_s3(
    hass,
    *,
    entry_id: Optional[str] = None,
    force_align: bool = True,
) -> Dict[str, Any]:
    """Sync local face gallery cache from S3 and refresh HA gallery store/UI."""
    data = hass.data.get(DOMAIN, {})
    s3_map = (data.get("s3") or {})

    # pick entry
    if not entry_id:
        if isinstance(s3_map, dict) and s3_map:
            entry_id = next(iter(s3_map.keys()))

    ctx = s3_map.get(entry_id) if entry_id and isinstance(s3_map, dict) else None
    if not isinstance(ctx, dict):
        return {"ok": False, "reason": "s3_not_configured"}

    s3_client = ctx.get("client")
    bucket = (ctx.get("bucket") or "").strip()
    prefix = (ctx.get("prefix") or "").strip("/")
    if not s3_client or not bucket:
        return {"ok": False, "reason": "s3_not_configured"}

    cache_root = _local_training_cache_root(hass)
    cache_root.mkdir(parents=True, exist_ok=True)

    storage_path = _local_gallery_storage_file(hass)
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    store_downloaded, downloaded, deleted = await hass.async_add_executor_job(
        sync_down_face_gallery,
        s3_client,
        bucket,
        prefix,
        cache_root,
        storage_path,
        bool(force_align),
    )

    # Reload gallery from HA storage after downloading the storage file.
    gs = data.get("gallery_store")
    if gs is not None:
        try:
            gallery = await gs.async_load()
            if isinstance(gallery, dict) and isinstance(gallery.get("persons"), dict):
                data["gallery"] = gallery
                # notify panel
                try:
                    from ..api.websocket_impl import publish_gallery_update

                    publish_gallery_update(hass, gallery)
                except Exception:
                    pass
        except Exception:
            pass

    return {
        "ok": True,
        "store_downloaded": bool(store_downloaded),
        "downloaded": downloaded,
        "deleted_local": deleted,
    }


async def async_face_gallery_push_to_s3(
    hass,
    *,
    entry_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Upload local face gallery cache + store to S3 (best effort)."""
    data = hass.data.get(DOMAIN, {})
    s3_map = (data.get("s3") or {})

    if not entry_id:
        if isinstance(s3_map, dict) and s3_map:
            entry_id = next(iter(s3_map.keys()))

    ctx = s3_map.get(entry_id) if entry_id and isinstance(s3_map, dict) else None
    if not isinstance(ctx, dict):
        return {"ok": False, "reason": "s3_not_configured"}

    s3_client = ctx.get("client")
    bucket = (ctx.get("bucket") or "").strip()
    prefix = (ctx.get("prefix") or "").strip("/")
    if not s3_client or not bucket:
        return {"ok": False, "reason": "s3_not_configured"}

    cache_root = _local_training_cache_root(hass)
    cache_root.mkdir(parents=True, exist_ok=True)

    storage_path = _local_gallery_storage_file(hass)
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    await hass.async_add_executor_job(
        sync_up_face_gallery,
        s3_client,
        bucket,
        prefix,
        cache_root,
        storage_path,
    )
    return {"ok": True}
