# custom_components/amazon_face_recognition/__init__.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple

import boto3
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.components.camera import async_get_image
from homeassistant.components.http import StaticPathConfig
import homeassistant.helpers.config_validation as cv
from homeassistant.components import panel_custom
from homeassistant.helpers.event import async_call_later

from .gallery_http import AFRGalleryUploadView, AFRGalleryImageView, AFRGalleryManageView
from .gallery_store import AFRGalleryStore
from .plates_store import AFRPlatesStore

from .const import (
    DOMAIN,
    CONF_AWS_ACCESS_KEY_ID,
    CONF_AWS_SECRET_ACCESS_KEY,
    CONF_REGION_NAME,
    CONF_COLLECTION_ID,
    CONF_S3_BUCKET,
    CONF_CLOUD_GALLERY_ENABLED,
    CONF_CLOUD_GALLERY_PREFIX,
    CONF_CLOUD_GALLERY_SYNC_ON_STARTUP,
    CONF_CLOUD_SCAN_UPLOAD_ENABLED,
    AFR_SCAN_DIRNAME,
    TRAINING_ROOT_DIRNAME,
)
from .processor import AFRProcessor
from .websocket import async_register_websockets
from .face_gallery_s3 import async_face_gallery_sync_from_s3
from .rekognition_services import (
    svc_index_face,
    svc_delete_face_by_id,
    svc_delete_faces_by_name,
    svc_delete_all_faces,
)

try:
    from .usage_store import AFRUsageStore
except Exception:  # pragma: no cover
    AFRUsageStore = None  # type: ignore


_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

# Flags in hass.data[DOMAIN]
_KEY_WS = "_ws_registered"
_KEY_SERVICES = "_services_registered"
_KEY_USAGE_STORE = "usage_store"
_KEY_PANEL = "_panel_registered"

# Optional Cloud Gallery (S3) container
_KEY_S3 = "s3"  # dict[entry_id] -> {client, bucket, prefix}

# Containers
_KEY_CLIENTS = "clients"         # dict[entry_id] -> boto3 rekognition client
_KEY_PROCESSORS = "processors"   # dict[entry_id] -> AFRProcessor
_KEY_VIEWS = "_views_registered"




def _domain_data(hass: HomeAssistant) -> dict:
    """Ensure DOMAIN dict exists and has core keys."""
    data = hass.data.setdefault(DOMAIN, {})

    data.setdefault(_KEY_S3, {})

    # Public data used by card/websocket
    data.setdefault("last_result", {})
    data.setdefault("index", {"updated_at": None, "items": []})
    data.setdefault("faces_index", {"updated_at": None, "persons": {}})
    data.setdefault("gallery", {"updated_at": None, "persons": {}})
    data.setdefault("gallery_store", None)
    data.setdefault("_gallery_loaded", False)
    data.setdefault("plates", {"updated_at": None, "items": {}})
    data.setdefault("plates_store", None)
    data.setdefault("_plates_loaded", False)

    data.setdefault(
        "usage",
        {
            "month": None,
            "scans_month": 0,
            "aws_calls_month": 0,
            "last_month_scans": 0,
            "last_month_api_calls": 0,
        },
    )

    # Multi-entry containers
    data.setdefault(_KEY_CLIENTS, {})
    data.setdefault(_KEY_PROCESSORS, {})

    return data


def _register_views_once(hass: HomeAssistant) -> None:
    data = _domain_data(hass)
    if data.get(_KEY_VIEWS):
        return

    hass.http.register_view(AFRGalleryUploadView)
    hass.http.register_view(AFRGalleryImageView)
    hass.http.register_view(AFRGalleryManageView)

    data[_KEY_VIEWS] = True
    _LOGGER.debug("AFR gallery HTTP views registered")


async def _mount_static_legacy(hass: HomeAssistant) -> None:
    """Legacy: mount /amazon_face_recognition/frontend only if folder exists."""
    frontend_dir = Path(__file__).parent / "frontend"

    if not frontend_dir.exists():
        _LOGGER.warning("AFR frontend directory not found: %s", frontend_dir)
        return

    try:
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    url_path="/amazon_face_recognition/frontend",
                    path=str(frontend_dir),
                    cache_headers=False,
                )
            ]
        )
        _LOGGER.warning(
            "AFR frontend mounted at /amazon_face_recognition/frontend -> %s",
            frontend_dir,
        )
    except Exception as e:
        _LOGGER.error("AFR frontend mount failed: %s", e)


async def _register_panel_once(hass: HomeAssistant) -> None:
    data = _domain_data(hass)
    if data.get(_KEY_PANEL):
        return

    # assicura static mount (serve il JS del panel)
    await _mount_static_legacy(hass)

    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="afr-panel",
        frontend_url_path="afr",
        module_url="/amazon_face_recognition/frontend/afr-panel.js?v=3",
        sidebar_title="Recognition Center",
        sidebar_icon="mdi:face-recognition",
        require_admin=True,
    )

    data[_KEY_PANEL] = True
    _LOGGER.debug("AFR panel registered")


def _register_ws_once(hass: HomeAssistant) -> None:
    """Register websocket commands once."""
    data = _domain_data(hass)
    if data.get(_KEY_WS):
        return
    async_register_websockets(hass)
    data[_KEY_WS] = True
    _LOGGER.debug("AFR websocket commands registered")


def _ensure_usage_store(hass: HomeAssistant) -> None:
    """Create usage store once (if available)."""
    data = _domain_data(hass)
    if data.get(_KEY_USAGE_STORE) is not None:
        return

    if AFRUsageStore is None:
        data[_KEY_USAGE_STORE] = None
        return

    data[_KEY_USAGE_STORE] = AFRUsageStore(hass)
    _LOGGER.debug("AFR usage store initialized")


def _ensure_gallery_store(hass: HomeAssistant) -> None:
    data = _domain_data(hass)
    if data.get("gallery_store") is not None:
        return
    data["gallery_store"] = AFRGalleryStore(hass)
    _LOGGER.debug("AFR gallery store initialized")


async def _load_gallery_once(hass: HomeAssistant) -> None:
    data = _domain_data(hass)
    if data.get("_gallery_loaded"):
        return

    store = data.get("gallery_store")
    if store is None:
        data["_gallery_loaded"] = True
        return

    try:
        gallery = await store.async_load()
        if isinstance(gallery, dict):
            data["gallery"] = gallery
            _LOGGER.debug(
                "AFR: gallery loaded from storage (%d persons)",
                len(gallery.get("persons") or {}),
            )
    except Exception as e:
        _LOGGER.warning("AFR: gallery load failed: %s", e)

    data["_gallery_loaded"] = True


def _ensure_plates_store(hass: HomeAssistant) -> None:
    data = _domain_data(hass)
    if data.get("plates_store") is not None:
        return
    data["plates_store"] = AFRPlatesStore(hass)
    _LOGGER.debug("AFR plates store initialized")


async def _load_plates_once(hass: HomeAssistant) -> None:
    data = _domain_data(hass)
    if data.get("_plates_loaded"):
        return

    store = data.get("plates_store")
    if store is None:
        data["_plates_loaded"] = True
        return

    try:
        plates = await store.async_load()
        if isinstance(plates, dict):
            data["plates"] = plates
            _LOGGER.debug(
                "AFR: plates loaded from storage (%d items)",
                len(plates.get("items") or {}),
            )
    except Exception as e:
        _LOGGER.warning("AFR: plates load failed: %s", e)

    data["_plates_loaded"] = True


def _get_options(entry: ConfigEntry) -> dict:
    """Return processor options from entry.options (already validated by config_flow)."""
    return dict(entry.options or {})


def _resolve_entry_and_processor(
    hass: HomeAssistant, call: ServiceCall
) -> Tuple[Optional[ConfigEntry], Optional[AFRProcessor]]:
    """Resolve which entry/processor to use (supports optional entry_id)."""
    entry_id = (call.data.get("entry_id") or "").strip()
    if entry_id:
        entry = hass.config_entries.async_get_entry(entry_id)
        proc = _domain_data(hass).get(_KEY_PROCESSORS, {}).get(entry_id)
        return entry, proc

    # fallback: first configured entry
    processors = _domain_data(hass).get(_KEY_PROCESSORS, {})
    if not processors:
        return None, None

    first_entry_id = next(iter(processors.keys()))
    entry = hass.config_entries.async_get_entry(first_entry_id)
    return entry, processors.get(first_entry_id)


def _register_services_once(hass: HomeAssistant) -> None:
    """Register HA services once."""
    data = _domain_data(hass)
    if data.get(_KEY_SERVICES):
        return

    async def _persist_usage_if_possible() -> None:
        store = _domain_data(hass).get(_KEY_USAGE_STORE)
        if store is not None:
            try:
                store.schedule_save()
            except Exception:
                pass

    async def _svc_scan(call: ServiceCall) -> None:
        entry2, processor2 = _resolve_entry_and_processor(hass, call)
        if processor2 is None or entry2 is None:
            _LOGGER.error(
                "%s: scan: unable to resolve entry/processor (pass entry_id if multiple entries).",
                DOMAIN,
            )
            return

        entity_id = call.data["entity_id"]
        img = await async_get_image(hass, entity_id)
        if img is None:
            _LOGGER.error("%s: scan: unable to get image from %s", DOMAIN, entity_id)
            return

        processor2.update_options(_get_options(entry2))
        await processor2.async_process_camera_image(entity_id, img.content)
        await _persist_usage_if_possible()

    async def _svc_refresh_faces_index(call: ServiceCall) -> None:
        entry2, processor2 = _resolve_entry_and_processor(hass, call)
        if processor2 is None or entry2 is None:
            _LOGGER.error(
                "%s: refresh_faces_index: unable to resolve entry/processor (pass entry_id if multiple entries).",
                DOMAIN,
            )
            return

        processor2.update_options(_get_options(entry2))
        await processor2.async_refresh_faces_index()

    async def _svc_index_face(call: ServiceCall) -> None:
        entry2, _ = _resolve_entry_and_processor(hass, call)
        if entry2 is None:
            _LOGGER.error(
                "%s: index_face: unable to resolve entry (pass entry_id if multiple entries).",
                DOMAIN,
            )
            return
        await svc_index_face(hass, entry2, call)

    async def _svc_delete_face_by_id(call: ServiceCall) -> None:
        entry2, _ = _resolve_entry_and_processor(hass, call)
        if entry2 is None:
            _LOGGER.error(
                "%s: delete_face_by_id: unable to resolve entry (pass entry_id if multiple entries).",
                DOMAIN,
            )
            return
        await svc_delete_face_by_id(hass, entry2, call)

    async def _svc_delete_faces_by_name(call: ServiceCall) -> None:
        entry2, _ = _resolve_entry_and_processor(hass, call)
        if entry2 is None:
            _LOGGER.error(
                "%s: delete_faces_by_name: unable to resolve entry (pass entry_id if multiple entries).",
                DOMAIN,
            )
            return
        await svc_delete_faces_by_name(hass, entry2, call)

    async def _svc_delete_all_faces(call: ServiceCall) -> None:
        entry2, _ = _resolve_entry_and_processor(hass, call)
        if entry2 is None:
            _LOGGER.error(
                "%s: delete_all_faces: unable to resolve entry (pass entry_id if multiple entries).",
                DOMAIN,
            )
            return
        await svc_delete_all_faces(hass, entry2, call)

    hass.services.async_register(
        DOMAIN,
        "scan",
        _svc_scan,
        vol.Schema(
            {
                vol.Required("entity_id"): cv.entity_id,
                vol.Optional("entry_id"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        "refresh_faces_index",
        _svc_refresh_faces_index,
        vol.Schema({vol.Optional("entry_id"): cv.string}),
    )

    hass.services.async_register(
        DOMAIN,
        "delete_all_faces",
        _svc_delete_all_faces,
        vol.Schema({vol.Optional("entry_id"): cv.string}),
    )

    data[_KEY_SERVICES] = True
    _LOGGER.debug("AFR services registered")


async def _load_usage_once(hass: HomeAssistant) -> None:
    """Load persisted usage into hass.data[DOMAIN]['usage'] once per startup."""
    data = _domain_data(hass)

    if data.get("_usage_loaded"):
        return

    store = data.get(_KEY_USAGE_STORE)
    if store is None:
        data["_usage_loaded"] = True
        return

    try:
        usage = await store.async_load()
        if isinstance(usage, dict):
            data["usage"] = usage
            _LOGGER.debug("AFR: usage loaded from storage: %s", usage)
    except Exception as e:
        _LOGGER.warning("AFR: usage load failed: %s", e)

    data["_usage_loaded"] = True


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration (YAML) + mount frontend static files + auto-load card JS."""
    _domain_data(hass)

    await _mount_static_legacy(hass)

    # Auto-load JS (legacy behavior)
    url = "/amazon_face_recognition/frontend/aws-face-recognition-card.js?v=1"
    try:
        hass.data.setdefault("frontend_extra_module_url", set()).add(url)
        _LOGGER.warning("AFR card auto-loaded via frontend_extra_module_url: %s", url)
    except Exception as e:
        _LOGGER.error("AFR auto-load card failed: %s", e)

    _register_ws_once(hass)

    _ensure_usage_store(hass)
    await _load_usage_once(hass)

    _register_services_once(hass)
    await _register_panel_once(hass)

    _register_views_once(hass)

    _ensure_gallery_store(hass)
    await _load_gallery_once(hass)

    _ensure_plates_store(hass)
    await _load_plates_once(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up integration from a config entry."""
    data = _domain_data(hass)

    _register_ws_once(hass)
    _ensure_usage_store(hass)
    await _load_usage_once(hass)

    _ensure_gallery_store(hass)
    await _load_gallery_once(hass)

    _register_services_once(hass)
    _register_views_once(hass)

    _ensure_plates_store(hass)
    await _load_plates_once(hass)

    # Create rekognition client for this entry
    aws_access_key_id = entry.data.get(CONF_AWS_ACCESS_KEY_ID)
    aws_secret_access_key = entry.data.get(CONF_AWS_SECRET_ACCESS_KEY)
    region_name = entry.data.get(CONF_REGION_NAME)
    collection_id = entry.data.get(CONF_COLLECTION_ID)

    try:
        client = await hass.async_add_executor_job(
            _create_rekognition_client_sync,
            aws_access_key_id,
            aws_secret_access_key,
            region_name,
        )
    except Exception as e:
        _LOGGER.error("%s: cannot create rekognition client: %s", DOMAIN, e)
        return False

    # Create processor
    options = _get_options(entry)
    data["options"] = options

    processor = AFRProcessor(hass, client, collection_id, options)

    data[_KEY_CLIENTS][entry.entry_id] = client
    data[_KEY_PROCESSORS][entry.entry_id] = processor

    # Compatibility pointers (single-entry friendly)
    data["rekognition_client"] = client
    data["processor"] = processor

    # Keep runtime objects in sync with entry.options changes (no restart needed).
    async def _on_entry_update(hass: HomeAssistant, updated_entry: ConfigEntry) -> None:
        try:
            new_opt = _get_options(updated_entry)
            data["options"] = new_opt

            proc = data.get(_KEY_PROCESSORS, {}).get(updated_entry.entry_id)
            if proc:
                proc.update_options(new_opt)

            aws_access_key_id = updated_entry.data.get(CONF_AWS_ACCESS_KEY_ID)
            aws_secret_access_key = updated_entry.data.get(CONF_AWS_SECRET_ACCESS_KEY)
            region_name = updated_entry.data.get(CONF_REGION_NAME)

            bucket = (new_opt.get(CONF_S3_BUCKET) or updated_entry.data.get(CONF_S3_BUCKET) or "").strip()
            cloud_enabled = bool(new_opt.get(CONF_CLOUD_GALLERY_ENABLED, True))
            cloud_prefix = (new_opt.get(CONF_CLOUD_GALLERY_PREFIX) or AFR_SCAN_DIRNAME).strip("/")
            if not cloud_prefix:
                cloud_prefix = AFR_SCAN_DIRNAME

            if bucket and cloud_enabled:
                ctx = data.get("s3", {}).get(updated_entry.entry_id)
                s3_client = ctx.get("client") if isinstance(ctx, dict) else None
                if s3_client is None:
                    try:
                        s3_client = await hass.async_add_executor_job(
                            _create_s3_client_sync,
                            aws_access_key_id,
                            aws_secret_access_key,
                            region_name,
                        )
                        data.setdefault("s3", {})[updated_entry.entry_id] = {
                            "client": s3_client,
                            "bucket": bucket,
                            "prefix": cloud_prefix,
                        }
                    except Exception as e:
                        _LOGGER.warning("%s: cannot create S3 client on options update: %s", DOMAIN, e)
                        s3_client = None
                else:
                    data.setdefault("s3", {})[updated_entry.entry_id] = {
                        "client": s3_client,
                        "bucket": bucket,
                        "prefix": cloud_prefix,
                    }

                if proc and s3_client is not None:
                    try:
                        proc.set_cloud_gallery(s3_client, bucket, cloud_prefix)
                    except Exception:
                        pass
            else:
                try:
                    data.get("s3", {}).pop(updated_entry.entry_id, None)
                except Exception:
                    pass
                if proc:
                    try:
                        proc.set_cloud_gallery(None, "", "")
                    except Exception:
                        pass
        except Exception as e:
            _LOGGER.debug("%s: entry update handler failed: %s", DOMAIN, e)

    entry.async_on_unload(entry.add_update_listener(_on_entry_update))

    # Platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _initial_faces_refresh(_now):
        try:
            processor.update_options(_get_options(entry))
            await processor.async_refresh_faces_index()
        except Exception as err:
            _LOGGER.warning("Initial faces index refresh failed: %s", err)

    async_call_later(hass, 5, _initial_faces_refresh)

    # Snapshot/annotated images folder (exposed as /local/...)
    # IMPORTANT: keep this separate from the training cache.
    scan_dir = Path(hass.config.path("www", AFR_SCAN_DIRNAME))
    scan_dir.mkdir(parents=True, exist_ok=True)

    # Training cache folder (NOT exposed to the frontend)
    training_dir = Path(hass.config.path(TRAINING_ROOT_DIRNAME, "training_cache"))
    training_dir.mkdir(parents=True, exist_ok=True)

    # Optional Cloud Gallery (S3)
    bucket = (options.get(CONF_S3_BUCKET) or entry.data.get(CONF_S3_BUCKET) or "").strip()
    cloud_enabled = bool(options.get(CONF_CLOUD_GALLERY_ENABLED, True))

    # default prefix = snapshots folder name
    cloud_prefix = (options.get(CONF_CLOUD_GALLERY_PREFIX) or AFR_SCAN_DIRNAME).strip("/")
    sync_on_startup = bool(options.get(CONF_CLOUD_GALLERY_SYNC_ON_STARTUP, True))
    scan_upload_enabled = bool(options.get(CONF_CLOUD_SCAN_UPLOAD_ENABLED, False))

    if bucket and cloud_enabled:
        try:
            s3_client = await hass.async_add_executor_job(
                _create_s3_client_sync,
                aws_access_key_id,
                aws_secret_access_key,
                region_name,
            )
            data[_KEY_S3][entry.entry_id] = {
                "client": s3_client,
                "bucket": bucket,
                "prefix": cloud_prefix,
            }
            # Make it available to the processor (for uploads after each scan)
            try:
                processor.set_cloud_gallery(s3_client, bucket, cloud_prefix)
            except Exception:
                pass

            if sync_on_startup:
                # NOTE: scan snapshots/index sync is optional and disabled by default.
                # Face gallery sync is handled below.
                if scan_upload_enabled:
                    await processor.async_cloud_gallery_sync(s3_client, bucket, cloud_prefix)

                # Face gallery sync-on-startup (only if local cache is empty).
                try:
                    local_has_files = any(training_dir.rglob("*"))
                except Exception:
                    local_has_files = False

                try:
                    persons = (data.get("gallery") or {}).get("persons") or {}
                    local_has_gallery = bool(persons)
                except Exception:
                    local_has_gallery = False

                if not local_has_files and not local_has_gallery:
                    await async_face_gallery_sync_from_s3(
                        hass, entry_id=entry.entry_id, force_align=False
                    )
        except Exception as e:
            _LOGGER.warning("%s: Cloud Gallery (S3) init/sync failed: %s", DOMAIN, e)

    # Bootstrap ONLY from disk (IMPORTANT: do not call async_refresh_faces_index here)
    await processor.async_bootstrap()
    await _register_panel_once(hass)

    return True


def _create_rekognition_client_sync(
    aws_access_key_id: str, aws_secret_access_key: str, region_name: str
):
    return boto3.client(
        "rekognition",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=region_name,
    )


def _create_s3_client_sync(
    aws_access_key_id: str, aws_secret_access_key: str, region_name: str
):
    """Create an S3 client (sync). Runs in executor."""
    return boto3.client(
        "s3",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=region_name,
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = _domain_data(hass)
        data.get(_KEY_PROCESSORS, {}).pop(entry.entry_id, None)
        data.get(_KEY_CLIENTS, {}).pop(entry.entry_id, None)

        # keep compatibility pointers coherent
        processors = data.get(_KEY_PROCESSORS, {})
        if processors:
            first_id = next(iter(processors.keys()))
            data["processor"] = processors[first_id]
            data["rekognition_client"] = data.get(_KEY_CLIENTS, {}).get(first_id)
        else:
            data.pop("processor", None)
            data.pop("rekognition_client", None)

    return unload_ok
