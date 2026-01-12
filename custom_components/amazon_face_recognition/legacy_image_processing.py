"""
amazon_face_recognition - image_processing.py

Object detection + face recognition via AWS Rekognition.
- Person boxes (RED) from detect_labels
- Face boxes (YELLOW) from detect_faces
- Face identification per-face by cropping and calling search_faces_by_image on the crop

Extra features:
- Save annotated images under /config/www/snapshots
- Keep only last N saved files
- Maintain recognition_index.json
- Save recognition_latest.jpg if enabled
- Persistent monthly usage sensor via Store
- Services for indexing/deleting faces in collection
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import io
import re
import json
import asyncio
import datetime
import logging
from typing import Optional, Dict, Any, Tuple

import boto3
import botocore

from PIL import Image, ImageDraw, UnidentifiedImageError, ImageFont

import voluptuous as vol

from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.image_processing import ImageProcessingEntity
from homeassistant.const import ATTR_ENTITY_ID
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,

    # ConfigEntry data keys
    CONF_AWS_ACCESS_KEY_ID,
    CONF_AWS_SECRET_ACCESS_KEY,
    CONF_REGION_NAME,
    CONF_COLLECTION_ID,

    # Options
    CONF_SOURCES,
    CONF_ROI_Y_MIN,
    CONF_ROI_X_MIN,
    CONF_ROI_Y_MAX,
    CONF_ROI_X_MAX,
    CONF_SCALE,
    CONF_SAVE_FILE_FOLDER,
    CONF_MAX_SAVED_FILES,
    CONF_SAVE_FILE_FORMAT,
    CONF_SAVE_TIMESTAMPED_FILE,
    CONF_ALWAYS_SAVE_LATEST_FILE,
    CONF_SHOW_BOXES,
    CONF_S3_BUCKET,
    CONF_LABEL_FONT_SCALE,
    CONF_MAX_RED_BOXES,
    CONF_MIN_RED_BOX_AREA,
    CONF_EXCLUDED_OBJECT_LABELS,
    CONF_AWS_API_COST,
    CONF_DEFAULT_MIN_CONFIDENCE,
    CONF_TARGETS_CONFIDENCE,
    CONF_EXCLUDE_TARGETS,

    # Defaults
    DEFAULT_ROI_Y_MIN,
    DEFAULT_ROI_X_MIN,
    DEFAULT_ROI_Y_MAX,
    DEFAULT_ROI_X_MAX,
    DEFAULT_SCALE,
    DEFAULT_MAX_SAVED_FILES,
    DEFAULT_SAVE_FILE_FORMAT,
    DEFAULT_SAVE_TIMESTAMPED_FILE,
    DEFAULT_ALWAYS_SAVE_LATEST_FILE,
    DEFAULT_SHOW_BOXES,
    DEFAULT_LABEL_FONT_SCALE,
    DEFAULT_MAX_RED_BOXES,
    DEFAULT_MIN_RED_BOX_AREA,
    DEFAULT_AWS_API_COST,
    DEFAULT_DEFAULT_MIN_CONFIDENCE,
    DEFAULT_TARGETS_CONFIDENCE,
    DEFAULT_EXCLUDE_TARGETS,
    EXCLUDED_OBJECT_LABELS,
    DEFAULT_EXCLUDED_OBJECT_LABELS,

    # Events / keys / colors
    EVENT_UPDATED,
    EVENT_OBJECT_DETECTED,
    EVENT_FACE_DETECTED,
    SAVED_FILE,
    RED,
    YELLOW,

    # Font path (MUST exist in const.py)
    FONT_PATH,
)

_LOGGER = logging.getLogger(__name__)
_LOGGER.warning("%s: image_processing.py IMPORTED", DOMAIN)


SERVICES_REGISTERED = False


# -----------------------------
# Small helpers (module-level)
# -----------------------------
def with_alpha(color, opacity: float):
    r, g, b = color
    a = int(255 * max(0.0, min(1.0, opacity)))
    return (r, g, b, a)




def _utc_iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def get_valid_filename(name: str) -> str:
    return re.sub(r"(?u)[^-\w.]", "", str(name).strip().replace(" ", "_"))


def _atomic_write_json(path: Path, data: dict) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp_path.replace(path)


def _load_json_index(path: Path) -> dict:
    try:
        if not path.exists():
            return {"updated_at": _utc_iso_now(), "items": []}
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"updated_at": _utc_iso_now(), "items": []}
        if "items" not in data or not isinstance(data["items"], list):
            data["items"] = []
        if "updated_at" not in data:
            data["updated_at"] = _utc_iso_now()
        return data
    except Exception:
        return {"updated_at": _utc_iso_now(), "items": []}


def _folder_to_local_base(folder: Path) -> str:
    """Convert /config/www/... to /local/..."""
    try:
        s = str(folder)
        if s.startswith("/config/www/"):
            rel = s[len("/config/www/") :].strip("/")
            return f"/local/{rel}" if rel else "/local"
        if s == "/config/www":
            return "/local"
    except Exception:
        pass
    return "/local"


def _read_bootstrap_from_disk(directory: Path, always_save_latest: bool = False):
    """
    Legge recognition_index.json da disco e prepara (index_data, last_result).
    NIENTE hass qui dentro (così può girare in executor).
    """
    index_path = directory / "recognition_index.json"
    index_data = _load_json_index(index_path)

    items = index_data.get("items") or []
    latest = None
    if items and isinstance(items, list):
        items_sorted = sorted(
            [it for it in items if isinstance(it, dict) and it.get("file")],
            key=lambda it: (it.get("timestamp") or "", it.get("file") or ""),
            reverse=True,
        )
        latest = items_sorted[0] if items_sorted else None

    if latest:
        base = _folder_to_local_base(directory)
        file = latest.get("file")
        image_url = f"{base}/{file}" if file else None

        last_result = {
            "id": Path(file).stem if file else None,
            "timestamp": latest.get("timestamp"),
            "recognized": latest.get("recognized") or [],
            "unrecognized_count": int(latest.get("unrecognized_count") or 0),
            "file": file,
            "image_url": image_url,
            "latest_url": f"{base}/recognition_latest.jpg" if always_save_latest else None,
            "objects": latest.get("objects") or {},
        }
    else:
        last_result = {}

    return index_data, last_result


def _cleanup_old_recognition_files(directory: Path, keep: int = 10, prefix: str = "recognition_") -> None:
    """Keep only newest `keep` timestamped files. DO NOT touch recognition_latest.jpg."""
    try:
        keep = int(keep)
        if keep < 1:
            return

        files = sorted(
            [
                p for p in directory.glob(f"{prefix}*")
                if p.is_file()
                and p.name != "recognition_latest.jpg"
                and p.name != "recognition.jpg"
            ],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for p in files[keep:]:
            try:
                p.unlink()
            except Exception:
                pass
    except Exception:
        return


def _update_recognition_index(
    directory: Path,
    filename: str,
    timestamp_iso: str,
    recognized: list,
    unrecognized_count: int,
    keep: int,
    prefix: str = "recognition_",
    index_name: str = "recognition_index.json",
    objects: Optional[Dict[str, Any]] = None,
) -> None:
    """Update/create recognition_index.json atomically."""
    try:
        index_path = directory / index_name
        data = _load_json_index(index_path)

        recognized = sorted({str(x) for x in (recognized or []) if x})
        unrecognized_count = int(unrecognized_count or 0)

        keep = int(keep) if keep else 10
        if keep < 1:
            keep = 1

        # map by file
        by_file = {}
        for it in data.get("items", []):
            if isinstance(it, dict) and it.get("file"):
                by_file[str(it["file"])] = it

        by_file[filename] = {
            "file": filename,
            "timestamp": timestamp_iso,
            "recognized": recognized,
            "unrecognized_count": unrecognized_count,
            "objects": objects or {},
        }

        # keep only entries whose file exists
        existing_files = {
            p.name for p in directory.glob(f"{prefix}*")
            if p.is_file()
            and p.name not in ("recognition_latest.jpg", "recognition.jpg")
        }
        existing_files.add(filename)

        by_file = {k: v for k, v in by_file.items() if k in existing_files}

        def _key(it: dict):
            ts = it.get("timestamp") or ""
            return (ts, it.get("file") or "")

        items = sorted(by_file.values(), key=_key, reverse=True)[:keep]
        data["updated_at"] = _utc_iso_now()
        data["items"] = items
        _atomic_write_json(index_path, data)
    except Exception:
        return


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _center_of_box(box: dict) -> dict:
    cx = (box["x_min"] + box["x_max"]) / 2
    cy = (box["y_min"] + box["y_max"]) / 2
    return {"x": cx, "y": cy}


def _point_in_box(box: dict, p: dict) -> bool:
    return (box["x_min"] <= p["x"] <= box["x_max"]) and (box["y_min"] <= p["y"] <= box["y_max"])


def _expand_box(box: dict, pad: float = 0.06) -> dict:
    w = box["x_max"] - box["x_min"]
    h = box["y_max"] - box["y_min"]
    dx = w * pad
    dy = h * pad
    return {
        "x_min": _clamp(box["x_min"] - dx),
        "y_min": _clamp(box["y_min"] - dy),
        "x_max": _clamp(box["x_max"] + dx),
        "y_max": _clamp(box["y_max"] + dy),
    }


def _norm_to_pixels(box: dict, img_w: int, img_h: int):
    left = int(box["x_min"] * img_w)
    top = int(box["y_min"] * img_h)
    right = int(box["x_max"] * img_w)
    bottom = int(box["y_max"] * img_h)

    left = max(0, min(img_w - 1, left))
    top = max(0, min(img_h - 1, top))
    right = max(1, min(img_w, right))
    bottom = max(1, min(img_h, bottom))
    if right <= left:
        right = min(img_w, left + 1)
    if bottom <= top:
        bottom = min(img_h, top + 1)
    return (left, top, right, bottom)


def _apply_roi_and_get_bytes(img: Image.Image, roi: dict) -> Tuple[bytes, Tuple[int, int], Image.Image]:
    """
    Crop ROI normalized 0..1 from PIL image:
      - bytes JPEG of cropped image for AWS
      - (offset_x, offset_y) in pixels (currently unused, but kept)
      - cropped PIL image (RGB)
    """
    w, h = img.size
    x_min = _clamp(float(roi.get("x_min", 0.0)))
    y_min = _clamp(float(roi.get("y_min", 0.0)))
    x_max = _clamp(float(roi.get("x_max", 1.0)))
    y_max = _clamp(float(roi.get("y_max", 1.0)))

    if x_max <= x_min or y_max <= y_min:
        x_min, y_min, x_max, y_max = 0.0, 0.0, 1.0, 1.0

    left, top, right, bottom = _norm_to_pixels(
        {"x_min": x_min, "y_min": y_min, "x_max": x_max, "y_max": y_max},
        w,
        h,
    )

    cropped = img.crop((left, top, right, bottom)).convert("RGB")

    with io.BytesIO() as out:
        cropped.save(out, format="JPEG", quality=90)
        return out.getvalue(), (left, top), cropped


def draw_box_scaled(
    img: Image.Image,
    box_norm,
    img_w: int,
    img_h: int,
    text: str,
    color,
    thickness=None,
    box_opacity: float = 0.5,
    label_opacity: float = 0.5,
    font_scale: float = DEFAULT_LABEL_FONT_SCALE,
):
    """
    box_norm: (y_min, x_min, y_max, x_max) normalized 0..1
    Draw bounding box + optional label with alpha overlays on RGBA.
    Returns updated RGBA image.
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    y_min, x_min, y_max, x_max = box_norm

    left = int(x_min * img_w)
    top = int(y_min * img_h)
    right = int(x_max * img_w)
    bottom = int(y_max * img_h)

    if thickness is None:
        thickness = max(2, int(min(img_w, img_h) * 0.004))

    try:
        fs = float(font_scale)
    except Exception:
        fs = DEFAULT_LABEL_FONT_SCALE

    fs = max(0.005, min(0.10, fs))
    font_size = max(14, int(min(img_w, img_h) * fs))

    try:
        font = ImageFont.truetype(str(FONT_PATH), font_size)
    except Exception:
        font = ImageFont.load_default()

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    outline_rgba = with_alpha(color, box_opacity)
    for i in range(thickness):
        odraw.rectangle([left - i, top - i, right + i, bottom + i], outline=outline_rgba)

    if not text:
        return Image.alpha_composite(img, overlay)

    lines = str(text).split("\n")
    pad = max(3, int(font_size * 0.25))
    line_gap = max(2, int(font_size * 0.20))

    line_sizes = []
    max_w = 0
    total_h = 0
    for line in lines:
        bbox = odraw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        line_sizes.append((w, h))
        max_w = max(max_w, w)
        total_h += h
    total_h += line_gap * (len(lines) - 1)

    text_x = left
    text_y = top - (total_h + 2 * pad)
    if text_y < 0:
        text_y = top + pad

    bg_left = int(text_x - pad)
    bg_top = int(text_y - pad)
    bg_right = int(text_x + max_w + pad)
    bg_bottom = int(text_y + total_h + pad)

    bg_left = max(0, bg_left)
    bg_top = max(0, bg_top)
    bg_right = min(img_w, bg_right)
    bg_bottom = min(img_h, bg_bottom)

    bg_rgba = with_alpha((0, 0, 0), label_opacity)
    odraw.rectangle([bg_left, bg_top, bg_right, bg_bottom], fill=bg_rgba)

    y = text_y
    for (line, (w, h)) in zip(lines, line_sizes):
        odraw.text((text_x, y), line, font=font, fill=(255, 255, 255, 255))
        y += h + line_gap

    return Image.alpha_composite(img, overlay)


def get_objects(response: dict):
    """Parse detect_labels response -> (objects, labels)."""
    objects = []
    labels = []
    dp = 3

    for label in response.get("Labels", []):
        instances = label.get("Instances", [])
        if instances:
            for instance in instances:
                box = instance["BoundingBox"]
                x_min, y_min, w, h = box["Left"], box["Top"], box["Width"], box["Height"]
                x_max, y_max = x_min + w, y_min + h

                bounding_box = {
                    "x_min": round(x_min, dp),
                    "y_min": round(y_min, dp),
                    "x_max": round(x_max, dp),
                    "y_max": round(y_max, dp),
                    "width": round(w, dp),
                    "height": round(h, dp),
                }

                centroid = {
                    "x": round(x_min + w / 2, dp),
                    "y": round(y_min + h / 2, dp),
                }

                objects.append(
                    {
                        "name": label["Name"].lower(),
                        "confidence": round(instance["Confidence"], dp),
                        "bounding_box": bounding_box,
                        "centroid": centroid,
                    }
                )
        else:
            labels.append(
                {
                    "name": label["Name"].lower(),
                    "confidence": round(label["Confidence"], dp),
                }
            )

    return objects, labels


# -----------------------------
# Sensors
# -----------------------------
class RecognizedPersonSensor(SensorEntity):
    """Sensor: last recognized person(s)."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_name = "Last Recognized Person"
        self._attr_unique_id = f"{DOMAIN}_recognized_person"

        self._recognized_names = set()
        self._confidence_details = {}

        self._last_scan_time = "no scan from boot"
        self._last_scan_time_person_found = "no person found from boot"
        self._last_scan_person_found = False
        self._last_scan = []
        self._last_file = None

        self._reset_task = None

    @property
    def state(self):
        return ", ".join(sorted(self._recognized_names)) if self._recognized_names else "None"

    @property
    def extra_state_attributes(self):
        return {
            "last_scan": self._last_scan,
            "last_scan_person_found": self._last_scan_person_found,
            "last_time_scan_person_found": self._last_scan_time_person_found,
            "last_scan_time": self._last_scan_time,
            "confidence": self._confidence_details or {},
            "file": self._last_file,
        }

    async def update_recognized_faces(
        self,
        recognized_names,
        recognized_faces_details,
        person_found: bool,
        file: Optional[str] = None,
    ):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._last_scan_time = now
        self._last_scan_person_found = bool(person_found)

        if person_found:
            self._last_scan_time_person_found = now
            if file is not None:
                self._last_file = file

        if recognized_names:
            self._recognized_names = set(recognized_names)
            self._confidence_details = recognized_faces_details or {}
            self._last_scan = sorted(self._recognized_names)
        elif person_found:
            self._recognized_names = {"person"}
            self._confidence_details = {}
            self._last_scan = ["person"]
        else:
            self._recognized_names.clear()
            self._confidence_details = {}
            self._last_scan = []
            self._last_file = None

        self.async_write_ha_state()

        if self._reset_task and not self._reset_task.done():
            self._reset_task.cancel()

        async def _reset_later():
            try:
                await asyncio.sleep(15)
                self._recognized_names.clear()
                self._confidence_details = {}
                self._last_scan = []
                self.async_write_ha_state()
            except asyncio.CancelledError:
                return

        self._reset_task = self.hass.async_create_task(_reset_later())


class AWSPersonSensor(SensorEntity):
    """Sensor entity to track registered persons in AWS Rekognition."""

    def __init__(self, hass: HomeAssistant, rekognition_client, collection_id: str):
        self.hass = hass
        self._rekognition_client = rekognition_client
        self._collection_id = collection_id
        self._attr_name = "AWS Persons"
        self._attr_unique_id = "aws_persons_sensor"
        self._attr_icon = "mdi:account-multiple"
        self._attr_extra_state_attributes = {}

    async def async_added_to_hass(self):
        self.async_schedule_update_ha_state(True)

    @property
    def state(self):
        face_counts = self._attr_extra_state_attributes.get("face_counts", {})
        return ", ".join(face_counts.keys()) or "Nessuno"

    @property
    def extra_state_attributes(self):
        return self._attr_extra_state_attributes

    async def async_update(self):
        try:
            response = await self.hass.async_add_executor_job(
                lambda: self._rekognition_client.list_faces(CollectionId=self._collection_id)
            )

            face_counts = {}
            for face in response.get("Faces", []):
                name = face.get("ExternalImageId", "Unknown")
                face_counts[name] = face_counts.get(name, 0) + 1

            self._attr_extra_state_attributes = {"face_counts": face_counts}
            self.async_write_ha_state()

        except Exception as e:
            _LOGGER.error("Error updating AWS Persons sensor: %s", str(e))


class AwsRekognitionMonthlyUsageSensor(SensorEntity):
    """
    1 sensore persistente:
      - state: scans_month
      - attributes: last_month, AWS_API_calls, Est_costs, month
    Persistenza via storage Store.
    Reset mensile automatico.
    """

    _attr_name = "AWS Rekognition Scans Month"
    _attr_unique_id = f"{DOMAIN}_aws_rekognition_scans_month"
    _attr_icon = "mdi:counter"

    def __init__(self, hass: HomeAssistant, api_cost: float):
        self.hass = hass
        self._api_cost = float(api_cost or DEFAULT_AWS_API_COST)
        self._store = Store(hass, 1, f"{DOMAIN}_monthly_usage")
        self._data = {
            "month": None,          # "YYYY-MM"
            "scans_month": 0,
            "aws_calls_month": 0,
            "last_month_scans": 0,
        }

    @property
    def state(self):
        return str(int(self._data.get("scans_month", 0)))

    @property
    def extra_state_attributes(self):
        calls = int(self._data.get("aws_calls_month", 0))
        cost = round(calls * float(self._api_cost), 6)
        return {
            "last_month": int(self._data.get("last_month_scans", 0)),
            "AWS_API_calls": calls,
            "Est_costs": cost,
            "AWS_api_cost": float(self._api_cost),
            "month": self._data.get("month"),
        }

    async def async_added_to_hass(self):
        await self._async_load()
        self._rollover_if_needed()
        self.async_write_ha_state()

    def _current_month_key(self) -> str:
        now = datetime.datetime.now()
        return now.strftime("%Y-%m")

    def _rollover_if_needed(self) -> None:
        cur = self._current_month_key()
        stored = self._data.get("month")
        if stored != cur:
            self._data["last_month_scans"] = int(self._data.get("scans_month", 0))
            self._data["scans_month"] = 0
            self._data["aws_calls_month"] = 0
            self._data["month"] = cur

    async def _async_load(self):
        try:
            loaded = await self._store.async_load()
            if isinstance(loaded, dict):
                self._data.update(loaded)
        except Exception:
            pass

    async def _async_save(self):
        try:
            await self._store.async_save(self._data)
        except Exception:
            pass

    async def async_increment(self, scans_delta: int = 0, aws_calls_delta: int = 0):
        self._rollover_if_needed()
        self._data["scans_month"] = int(self._data.get("scans_month", 0)) + int(scans_delta or 0)
        self._data["aws_calls_month"] = int(self._data.get("aws_calls_month", 0)) + int(aws_calls_delta or 0)
        await self._async_save()
        self.async_write_ha_state()


# -----------------------------
# async_setup_entry
# -----------------------------
async def async_setup_entry(
    
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    _LOGGER.warning(
        "%s: image_processing async_setup_entry CALLED (entry_id=%s)",
        DOMAIN,
        entry.entry_id,
    )
    data = dict(entry.data or {})
    opt = dict(entry.options or {})

    region = data[CONF_REGION_NAME]
    access_key = data[CONF_AWS_ACCESS_KEY_ID]
    secret_key = data[CONF_AWS_SECRET_ACCESS_KEY]
    collection_id = (data.get(CONF_COLLECTION_ID) or "").strip() or None

    aws_config = {
        "region_name": region,
        "aws_access_key_id": access_key,
        "aws_secret_access_key": secret_key,
    }

    # Options
    sources = opt.get(CONF_SOURCES, [])
    if isinstance(sources, str):
        sources = [sources]
    sources = [str(x).strip() for x in (sources or []) if str(x).strip()]

    roi_y_min = float(opt.get(CONF_ROI_Y_MIN, DEFAULT_ROI_Y_MIN))
    roi_x_min = float(opt.get(CONF_ROI_X_MIN, DEFAULT_ROI_X_MIN))
    roi_y_max = float(opt.get(CONF_ROI_Y_MAX, DEFAULT_ROI_Y_MAX))
    roi_x_max = float(opt.get(CONF_ROI_X_MAX, DEFAULT_ROI_X_MAX))
    scale = float(opt.get(CONF_SCALE, DEFAULT_SCALE))

    save_file_folder = opt.get(CONF_SAVE_FILE_FOLDER, "/config/www/snapshots/")
    save_file_folder = Path(save_file_folder) if save_file_folder else None

    max_saved_files = int(opt.get(CONF_MAX_SAVED_FILES, DEFAULT_MAX_SAVED_FILES))
    save_file_format = str(opt.get(CONF_SAVE_FILE_FORMAT, DEFAULT_SAVE_FILE_FORMAT)).lower()
    save_timestamped_file = bool(opt.get(CONF_SAVE_TIMESTAMPED_FILE, DEFAULT_SAVE_TIMESTAMPED_FILE))
    always_save_latest_file = bool(opt.get(CONF_ALWAYS_SAVE_LATEST_FILE, DEFAULT_ALWAYS_SAVE_LATEST_FILE))
    show_boxes = bool(opt.get(CONF_SHOW_BOXES, DEFAULT_SHOW_BOXES))

    s3_bucket = (opt.get(CONF_S3_BUCKET) or "").strip() or None

    label_font_scale = float(opt.get(CONF_LABEL_FONT_SCALE, DEFAULT_LABEL_FONT_SCALE))
    max_red_boxes = int(opt.get(CONF_MAX_RED_BOXES, DEFAULT_MAX_RED_BOXES))
    min_red_box_area = float(opt.get(CONF_MIN_RED_BOX_AREA, DEFAULT_MIN_RED_BOX_AREA))

    excluded_object_labels = opt.get(CONF_EXCLUDED_OBJECT_LABELS, DEFAULT_EXCLUDED_OBJECT_LABELS)

    api_cost = float(opt.get(CONF_AWS_API_COST, DEFAULT_AWS_API_COST))

    default_min_confidence = float(opt.get(CONF_DEFAULT_MIN_CONFIDENCE, DEFAULT_DEFAULT_MIN_CONFIDENCE))
    targets_confidence = opt.get(CONF_TARGETS_CONFIDENCE, DEFAULT_TARGETS_CONFIDENCE) or {}
    exclude_targets = {
        str(x).strip().lower()
        for x in (opt.get(CONF_EXCLUDE_TARGETS, DEFAULT_EXCLUDE_TARGETS) or [])
        if str(x).strip()
    }

    if not sources:
        _LOGGER.warning("%s: nessuna camera configurata nelle opzioni (sources).", DOMAIN)

    def _make_client(service: str):
        return boto3.client(service, **aws_config)

    rekognition_client = await hass.async_add_executor_job(lambda: _make_client("rekognition"))
    s3_client = await hass.async_add_executor_job(lambda: _make_client("s3")) if s3_bucket else None

    entities = []

    # # usage sensor (one per hass)
    hass.data.setdefault(DOMAIN, {})
    # if "usage_sensor" not in hass.data[DOMAIN]:
    #     usage_sensor = AwsRekognitionMonthlyUsageSensor(hass, api_cost=api_cost)
    #     hass.data[DOMAIN]["usage_sensor"] = usage_sensor
    #     entities.append(usage_sensor)

    # # persons sensor (optional)
    # if collection_id:
    #     entities.append(AWSPersonSensor(hass, rekognition_client, collection_id))

    # # recognized sensor (one per hass)
    # if "recognized_person_sensor" not in hass.data[DOMAIN]:
    #     recognized_sensor = RecognizedPersonSensor(hass)
    #     hass.data[DOMAIN]["recognized_person_sensor"] = recognized_sensor
    #     entities.append(recognized_sensor)

    # # entities per camera
    # for cam_entity_id in sources:
    #     entities.append(
    #         ObjectDetection(
    #             hass=hass,
    #             rekognition_client=rekognition_client,
    #             s3_client=s3_client,
    #             region=region,
    #             roi_y_min=roi_y_min,
    #             roi_x_min=roi_x_min,
    #             roi_y_max=roi_y_max,
    #             roi_x_max=roi_x_max,
    #             scale=scale,
    #             show_boxes=show_boxes,
    #             save_file_format=save_file_format,
    #             save_file_folder=save_file_folder,
    #             save_timestamped_file=save_timestamped_file,
    #             always_save_latest_file=always_save_latest_file,
    #             s3_bucket=s3_bucket,
    #             camera_entity=cam_entity_id,
    #             collection_id=collection_id,
    #             max_saved_files=max_saved_files,
    #             label_font_scale=label_font_scale,
    #             max_red_boxes=max_red_boxes,
    #             min_red_box_area=min_red_box_area,
    #             excluded_object_labels=excluded_object_labels,
    #             default_min_confidence=default_min_confidence,
    #             targets_confidence=targets_confidence,
    #             exclude_targets=exclude_targets,
    #         )
    #     )

    # BOOTSTRAP: preload index/last_result from disk
    if save_file_folder:
        try:
            index_data, last_result = await hass.async_add_executor_job(
                _read_bootstrap_from_disk,
                save_file_folder,
                bool(always_save_latest_file),
            )
            hass.data[DOMAIN]["index"] = index_data
            hass.data[DOMAIN]["last_result"] = last_result
            _LOGGER.info("%s: boot preload OK (items=%s)", DOMAIN, len(index_data.get("items") or []))
        except Exception as e:
            _LOGGER.warning("%s: boot preload failed: %s", DOMAIN, e)

    # BOOTSTRAP faces_index from AWS + push websocket
    if collection_id:
        try:
            def _build_faces_index():
                persons = {}
                kwargs = {"CollectionId": collection_id, "MaxResults": 4096}
                while True:
                    resp = rekognition_client.list_faces(**kwargs)
                    for face in resp.get("Faces", []):
                        name = face.get("ExternalImageId") or "Unknown"
                        persons[name] = persons.get(name, 0) + 1
                    token = resp.get("NextToken")
                    if not token:
                        break
                    kwargs["NextToken"] = token

                return {
                    "updated_at": _utc_iso_now(),
                    "persons": {k: {"count": v} for k, v in sorted(persons.items())},
                }

            faces_index = await hass.async_add_executor_job(_build_faces_index)
            hass.data[DOMAIN]["faces_index"] = faces_index

            from .websocket import publish_faces_update
            hass.loop.call_soon_threadsafe(publish_faces_update, hass, faces_index)

            _LOGGER.info("%s: faces_index preload OK (persons=%s)", DOMAIN, len(faces_index.get("persons") or {}))
        except Exception as e:
            _LOGGER.warning("%s: faces_index preload failed: %s", DOMAIN, e)

    async_add_entities(entities, update_before_add=False)


# -----------------------------
# Main ImageProcessing entity
# -----------------------------
class ObjectDetection(ImageProcessingEntity):
    """Object + face recognition."""

    def __init__(
        self,
        hass: HomeAssistant,
        rekognition_client,
        s3_client,
        region: str,
        roi_y_min: float,
        roi_x_min: float,
        roi_y_max: float,
        roi_x_max: float,
        scale: float,
        show_boxes: bool,
        save_file_format: str,
        save_file_folder: Optional[Path],
        save_timestamped_file: bool,
        always_save_latest_file: bool,
        s3_bucket: Optional[str],
        camera_entity: str,
        name: Optional[str] = None,
        collection_id: Optional[str] = None,
        max_saved_files: int = DEFAULT_MAX_SAVED_FILES,
        label_font_scale: float = DEFAULT_LABEL_FONT_SCALE,
        max_red_boxes: int = DEFAULT_MAX_RED_BOXES,
        min_red_box_area: float = DEFAULT_MIN_RED_BOX_AREA,
        excluded_object_labels=None,
        default_min_confidence: float = DEFAULT_DEFAULT_MIN_CONFIDENCE,
        targets_confidence: Optional[Dict[str, float]] = None,
        exclude_targets: Optional[set] = None,
    ):
        self.hass = hass

        # AWS
        self._collection_id = collection_id
        self._aws_rekognition_client = rekognition_client
        self._aws_s3_client = s3_client
        self._aws_region = region

        # ROI (normalized + safe ordering)
        self._roi_y_min = _clamp(float(roi_y_min))
        self._roi_x_min = _clamp(float(roi_x_min))
        self._roi_y_max = _clamp(float(roi_y_max))
        self._roi_x_max = _clamp(float(roi_x_max))

        if self._roi_y_max <= self._roi_y_min:
            self._roi_y_min, self._roi_y_max = 0.0, 1.0
        if self._roi_x_max <= self._roi_x_min:
            self._roi_x_min, self._roi_x_max = 0.0, 1.0

        # Filtering config
        self._default_min_confidence = float(default_min_confidence or DEFAULT_DEFAULT_MIN_CONFIDENCE)
        self._targets_confidence = {
            str(k).strip().lower(): float(v)
            for k, v in (targets_confidence or {}).items()
            if str(k).strip()
        }
        self._exclude_targets = {
            str(x).strip().lower()
            for x in (exclude_targets or set())
            if str(x).strip()
        }
        self._new_mode = bool(self._targets_confidence) or (self._default_min_confidence != DEFAULT_DEFAULT_MIN_CONFIDENCE)

        # Entity name / camera entity
        self._camera_entity = camera_entity
        if name:
            self._name = name
        else:
            entity_name = split_entity_id(camera_entity)[1]
            self._name = f"afr_{entity_name}"

        # processing state
        self._state = None
        self._objects = []
        self._labels = []
        self._targets_found = []
        self._summary = {}

        self._scale = float(scale or 1.0)
        self._show_boxes = bool(show_boxes)

        # save settings
        self._save_file_format = (save_file_format or DEFAULT_SAVE_FILE_FORMAT).lower()
        self._save_file_folder = save_file_folder
        self._save_timestamped_file = bool(save_timestamped_file)
        self._always_save_latest_file = bool(always_save_latest_file)
        self._s3_bucket = s3_bucket

        # image frame
        self._image: Optional[Image.Image] = None
        self._image_width: Optional[int] = None
        self._image_height: Optional[int] = None

        # faces/person association
        self._faces = []
        self._person_labels = []
        self._confidence_details = {}
        self._person_found = False
        self._has_identified_faces = False

        self._attr_unique_id = f"{DOMAIN}_{self._camera_entity}"

        # overlay settings
        try:
            self._max_saved_files = int(max_saved_files or DEFAULT_MAX_SAVED_FILES)
        except Exception:
            self._max_saved_files = DEFAULT_MAX_SAVED_FILES

        try:
            self._label_font_scale = float(label_font_scale)
        except Exception:
            self._label_font_scale = DEFAULT_LABEL_FONT_SCALE
        self._label_font_scale = max(0.005, min(0.10, self._label_font_scale))

        try:
            self._max_red_boxes = int(max_red_boxes)
        except Exception:
            self._max_red_boxes = DEFAULT_MAX_RED_BOXES
        self._max_red_boxes = max(0, min(50, self._max_red_boxes))

        try:
            self._min_red_box_area = float(min_red_box_area)
        except Exception:
            self._min_red_box_area = DEFAULT_MIN_RED_BOX_AREA
        self._min_red_box_area = max(0.0, min(1.0, self._min_red_box_area))

        if excluded_object_labels:
            self._excluded_object_labels = {str(x).strip().lower() for x in excluded_object_labels}
        else:
            self._excluded_object_labels = set(EXCLUDED_OBJECT_LABELS)

    # ------------------------------
    # Services registration (once)
    # ------------------------------
    async def async_added_to_hass(self):
        global SERVICES_REGISTERED
        if SERVICES_REGISTERED:
            return
        SERVICES_REGISTERED = True

        self.hass.services.async_register(
            DOMAIN,
            "index_face",
            self.async_index_face,
            vol.Schema({vol.Required("file_path"): cv.string, vol.Required("name"): cv.string}),
        )

        self.hass.services.async_register(
            DOMAIN,
            "delete_face_by_id",
            self.async_delete_face_by_id,
            vol.Schema({vol.Required("face_id"): cv.string}),
        )

        self.hass.services.async_register(
            DOMAIN,
            "delete_faces_by_name",
            self.async_delete_faces_by_name,
            vol.Schema({vol.Required("name"): cv.string}),
        )

        self.hass.services.async_register(
            DOMAIN,
            "delete_all_faces",
            self.async_delete_all_faces,
            vol.Schema({}),
        )

        _LOGGER.info("%s: servizi Rekognition registrati.", DOMAIN)

    async def _refresh_faces_index(self):
        if not self._collection_id:
            return

        def _build():
            persons = {}
            kwargs = {"CollectionId": self._collection_id, "MaxResults": 4096}
            while True:
                resp = self._aws_rekognition_client.list_faces(**kwargs)
                for face in resp.get("Faces", []):
                    name = face.get("ExternalImageId") or "Unknown"
                    persons[name] = persons.get(name, 0) + 1
                token = resp.get("NextToken")
                if not token:
                    break
                kwargs["NextToken"] = token

            return {
                "updated_at": _utc_iso_now(),
                "persons": {k: {"count": v} for k, v in sorted(persons.items())},
            }

        faces_index = await self.hass.async_add_executor_job(_build)
        self.hass.data.setdefault(DOMAIN, {})
        self.hass.data[DOMAIN]["faces_index"] = faces_index

        from .websocket import publish_faces_update
        self.hass.loop.call_soon_threadsafe(publish_faces_update, self.hass, faces_index)

    async def async_index_face(self, call):
        if not self._collection_id:
            _LOGGER.error("collection_id non configurato: impossibile indicizzare volti.")
            return

        file_path = call.data.get("file_path")
        name = (call.data.get("name") or "").strip().title()

        if not file_path or not name:
            _LOGGER.error("Missing file_path or name parameter.")
            return

        try:
            def load_image():
                with open(file_path, "rb") as image_file:
                    return image_file.read()

            image_bytes = await self.hass.async_add_executor_job(load_image)

            def index_faces():
                return self._aws_rekognition_client.index_faces(
                    CollectionId=self._collection_id,
                    Image={"Bytes": image_bytes},
                    ExternalImageId=name,
                    DetectionAttributes=["ALL"],
                )

            response = await self.hass.async_add_executor_job(index_faces)
            _LOGGER.info("Face indexed successfully: %s", response)

            await self._refresh_faces_index()
        except Exception as e:
            _LOGGER.error("Error indexing face: %s", str(e))

    async def async_delete_face_by_id(self, call):
        if not self._collection_id:
            _LOGGER.error("collection_id non configurato: impossibile cancellare volti.")
            return

        face_id = (call.data.get("face_id") or "").strip()
        if not face_id:
            _LOGGER.error("Missing face_id.")
            return

        try:
            await self.hass.async_add_executor_job(
                lambda: self._aws_rekognition_client.delete_faces(
                    CollectionId=self._collection_id,
                    FaceIds=[face_id],
                )
            )
            _LOGGER.info("Rimosso FaceId=%s dalla collezione.", face_id)
            await self._refresh_faces_index()
        except Exception as e:
            _LOGGER.error("Errore cancellando FaceId=%s: %s", face_id, e)

    async def async_delete_faces_by_name(self, call):
        if not self._collection_id:
            _LOGGER.error("collection_id non configurato: impossibile cancellare volti.")
            return

        name_to_delete = (call.data.get("name") or "").strip()
        if not name_to_delete:
            _LOGGER.error("Missing name.")
            return

        try:
            response = await self.hass.async_add_executor_job(
                lambda: self._aws_rekognition_client.list_faces(CollectionId=self._collection_id)
            )

            face_ids = [
                face["FaceId"]
                for face in response.get("Faces", [])
                if face.get("ExternalImageId") == name_to_delete
            ]

            if not face_ids:
                _LOGGER.info("Nessun volto trovato con il nome '%s'.", name_to_delete)
                return

            for i in range(0, len(face_ids), 10):
                batch = face_ids[i: i + 10]
                await self.hass.async_add_executor_job(
                    lambda b=batch: self._aws_rekognition_client.delete_faces(
                        CollectionId=self._collection_id,
                        FaceIds=b,
                    )
                )

            _LOGGER.info("Rimossi %s volti con il nome '%s'.", len(face_ids), name_to_delete)
            await self._refresh_faces_index()

        except Exception as e:
            _LOGGER.error("Errore nella cancellazione dei volti '%s': %s", name_to_delete, e)

    async def async_delete_all_faces(self, call):
        if not self._collection_id:
            _LOGGER.error("collection_id non configurato: impossibile cancellare volti.")
            return

        try:
            response = await self.hass.async_add_executor_job(
                lambda: self._aws_rekognition_client.list_faces(CollectionId=self._collection_id)
            )

            face_ids = [face["FaceId"] for face in response.get("Faces", [])]
            if not face_ids:
                _LOGGER.info("Nessun volto trovato nella collezione.")
                return

            for i in range(0, len(face_ids), 10):
                batch = face_ids[i: i + 10]
                await self.hass.async_add_executor_job(
                    lambda b=batch: self._aws_rekognition_client.delete_faces(
                        CollectionId=self._collection_id,
                        FaceIds=b,
                    )
                )

            _LOGGER.info("Rimossi %s volti dalla collezione.", len(face_ids))
            await self._refresh_faces_index()
        except Exception as e:
            _LOGGER.error("Errore nella cancellazione di tutti i volti: %s", e)

    # ------------------------------
    # helpers
    # ------------------------------
    def _recognized_names_set(self) -> set:
        names = set()
        for f in getattr(self, "_faces", []):
            n = f.get("name")
            if n and n != "Unknown":
                names.add(str(n))
        return names

    def _get_object_summary_for_index(self) -> dict:
        excluded_labels = getattr(self, "_excluded_object_labels", None) or set(EXCLUDED_OBJECT_LABELS)
        excluded_labels = {str(x).strip().lower() for x in excluded_labels if str(x).strip()}

        exclude_targets = getattr(self, "_exclude_targets", None) or set()
        exclude_targets = {str(x).strip().lower() for x in exclude_targets if str(x).strip()}

        recognized_names = {str(x).strip() for x in self._recognized_names_set() if str(x).strip()}
        recognized_names_l = {n.lower() for n in recognized_names}

        counts = Counter([str(o.get("name", "")).lower() for o in (getattr(self, "_targets_found", []) or [])])

        out = {}
        for name, count in counts.items():
            if not name:
                continue
            if name in excluded_labels:
                continue
            if name in exclude_targets:
                continue
            if name in recognized_names_l:
                continue
            out[name] = int(count)
        return out

    def _count_people_from_targets(self) -> int:
        persons = [o for o in getattr(self, "_targets_found", []) if o.get("name") == "person"]
        if not persons:
            return 0

        MIN_CONF = 80.0
        MIN_AREA = 0.02

        filtered = []
        for p in persons:
            bb = p.get("bounding_box")
            if not bb:
                continue
            conf = float(p.get("confidence", 0.0))
            w = max(0.0, bb.get("x_max", 0) - bb.get("x_min", 0))
            h = max(0.0, bb.get("y_max", 0) - bb.get("y_min", 0))
            area = w * h
            if conf < MIN_CONF:
                continue
            if area < MIN_AREA:
                continue
            filtered.append(p)

        return len(filtered) if filtered else len(persons)

    def _crop_face_bytes(self, face_box_norm: dict) -> bytes:
        if self._image is None:
            return b""

        expanded = _expand_box(face_box_norm, pad=0.15)
        crop_px = _norm_to_pixels(expanded, self._image_width, self._image_height)

        face_img = self._image.convert("RGB").crop(crop_px)

        min_side = 160
        if face_img.size[0] < min_side or face_img.size[1] < min_side:
            scale = max(min_side / face_img.size[0], min_side / face_img.size[1])
            new_size = (int(face_img.size[0] * scale), int(face_img.size[1] * scale))
            face_img = face_img.resize(new_size, Image.LANCZOS)

        with io.BytesIO() as out:
            face_img.save(out, format="JPEG", quality=90)
            return out.getvalue()

    def _search_face_in_collection(self, face_bytes: bytes, threshold: float = 80.0):
        if not self._collection_id or not face_bytes:
            return None

        try:
            resp = self._aws_rekognition_client.search_faces_by_image(
                CollectionId=self._collection_id,
                Image={"Bytes": face_bytes},
                MaxFaces=1,
                FaceMatchThreshold=threshold,
            )
            matches = resp.get("FaceMatches", [])
            if not matches:
                return None
            m = matches[0]
            name = m["Face"].get("ExternalImageId", "Unknown")
            sim = float(m.get("Similarity", 0.0))
            return {"name": name, "similarity": round(sim, 2)}
        except botocore.exceptions.ClientError as e:
            _LOGGER.error("search_faces_by_image error: %s", e)
            return None
        except Exception as e:
            _LOGGER.error("search_faces_by_image generic error: %s", e)
            return None

    # ------------------------------
    # HA ImageProcessing
    # ------------------------------
    def process_image(self, image: bytes):
        """Runs in executor (sync). MUST be thread-safe with hass interactions."""
        self._faces = []
        self._person_labels = []
        self._confidence_details = {}
        self._person_found = False
        self._has_identified_faces = False

        # 1) Open + ROI crop
        try:
            self._image = Image.open(io.BytesIO(bytearray(image)))
            self._image_width, self._image_height = self._image.size

            roi = {
                "x_min": getattr(self, "_roi_x_min", 0.0),
                "y_min": getattr(self, "_roi_y_min", 0.0),
                "x_max": getattr(self, "_roi_x_max", 1.0),
                "y_max": getattr(self, "_roi_y_max", 1.0),
            }
            roi_bytes, (_, _), roi_img = _apply_roi_and_get_bytes(self._image, roi)

            # after ROI, work only on cropped image
            self._image = roi_img
            self._image_width, self._image_height = self._image.size
            image = roi_bytes

        except Exception as e:
            _LOGGER.error("Errore durante il caricamento/crop ROI immagine: %s", e)
            return

        # 2) scale (optional)
        if self._scale != DEFAULT_SCALE:
            try:
                newsize = (
                    int(self._image_width * self._scale),
                    int(self._image_height * self._scale),
                )
                self._image.thumbnail(newsize, Image.LANCZOS)
                self._image_width, self._image_height = self._image.size
                with io.BytesIO() as output:
                    self._image.save(output, format="JPEG", quality=90)
                    image = output.getvalue()
            except Exception as e:
                _LOGGER.warning("Scale failed (ignored): %s", e)

        # reset per-frame
        self._state = None
        self._objects = []
        self._labels = []
        self._targets_found = []
        self._summary = {}

        saved_image_path = None
        recognized_names_set = set()

        # monthly scans +1 (thread-safe schedule)
        try:
            usage = self.hass.data.get(DOMAIN, {}).get("usage_sensor")
            if usage:
                self.hass.loop.call_soon_threadsafe(
                    self.hass.async_create_task,
                    usage.async_increment(scans_delta=1),
                )
        except Exception:
            pass

        # 3) detect_labels (AWS CALL +1)
        try:
            response_labels = self._aws_rekognition_client.detect_labels(Image={"Bytes": image})
            try:
                usage = self.hass.data.get(DOMAIN, {}).get("usage_sensor")
                if usage:
                    self.hass.loop.call_soon_threadsafe(
                        self.hass.async_create_task,
                        usage.async_increment(aws_calls_delta=1),
                    )
            except Exception:
                pass

            self._objects, self._labels = get_objects(response_labels)

        except botocore.exceptions.ClientError as error:
            _LOGGER.error("Errore in detect_labels: %s", error)
            return
        except Exception as e:
            _LOGGER.error("Errore generico in detect_labels: %s", e)
            return

        # 4) filter objects (UI-only)
        self._targets_found = []
        for obj in self._objects:
            name = str(obj.get("name", "")).strip().lower()
            conf = float(obj.get("confidence", 0.0))
            if not name:
                continue
            if name in self._exclude_targets:
                continue
            min_conf = float(self._targets_confidence.get(name, self._default_min_confidence))
            if conf >= min_conf:
                self._targets_found.append(obj)

        self._state = len(self._targets_found)
        persons = [o for o in self._targets_found if o.get("name") == "person"]
        self._person_found = len(persons) > 0

        # 5) detect_faces (only if person)
        faces_detected = []
        if self._person_found:
            try:
                faces_resp = self._aws_rekognition_client.detect_faces(
                    Image={"Bytes": image},
                    Attributes=["DEFAULT"],
                )
                try:
                    usage = self.hass.data.get(DOMAIN, {}).get("usage_sensor")
                    if usage:
                        self.hass.loop.call_soon_threadsafe(
                            self.hass.async_create_task,
                            usage.async_increment(aws_calls_delta=1),
                        )
                except Exception:
                    pass

                for fd in faces_resp.get("FaceDetails", []):
                    bb = fd.get("BoundingBox")
                    if not bb:
                        continue
                    x_min = float(bb["Left"])
                    y_min = float(bb["Top"])
                    x_max = x_min + float(bb["Width"])
                    y_max = y_min + float(bb["Height"])
                    faces_detected.append(
                        {
                            "bounding_box": {
                                "x_min": _clamp(x_min),
                                "y_min": _clamp(y_min),
                                "x_max": _clamp(x_max),
                                "y_max": _clamp(y_max),
                            }
                        }
                    )
            except botocore.exceptions.ClientError as e:
                _LOGGER.error("detect_faces error: %s", e)
            except Exception as e:
                _LOGGER.error("detect_faces generic error: %s", e)

        # 6) per-face recognition
        for face in faces_detected:
            match = None
            if self._collection_id:
                face_bytes = self._crop_face_bytes(face["bounding_box"])
                try:
                    usage = self.hass.data.get(DOMAIN, {}).get("usage_sensor")
                    if usage:
                        self.hass.loop.call_soon_threadsafe(
                            self.hass.async_create_task,
                            usage.async_increment(aws_calls_delta=1),
                        )
                except Exception:
                    pass

                match = self._search_face_in_collection(face_bytes, threshold=80.0)

            if match:
                face["name"] = match["name"]
                face["confidence"] = match["similarity"]
                recognized_names_set.add(match["name"])

                prev = self._confidence_details.get(match["name"])
                if prev is None or match["similarity"] > prev:
                    self._confidence_details[match["name"]] = match["similarity"]
            else:
                face["name"] = "Unknown"
                face["confidence"] = 0.0

            self._faces.append(face)

        self._has_identified_faces = any(f.get("name") and f["name"] != "Unknown" for f in self._faces)

        # 7) associate person boxes with best face inside
        for p in persons:
            p_box = p["bounding_box"]
            pb = {
                "x_min": p_box["x_min"],
                "y_min": p_box["y_min"],
                "x_max": p_box["x_max"],
                "y_max": p_box["y_max"],
            }

            best = None
            for f in self._faces:
                fc = _center_of_box(f["bounding_box"])
                if _point_in_box(pb, fc) and f.get("name") and f["name"] != "Unknown":
                    if best is None or f["confidence"] > best["confidence"]:
                        best = {"name": f["name"], "confidence": f["confidence"]}

            self._person_labels.append(
                {
                    "bounding_box": pb,
                    "person_confidence": float(p.get("confidence", 0.0)),
                    "matched_name": best["name"] if best else None,
                    "matched_similarity": best["confidence"] if best else None,
                }
            )

        # 8) summary
        self._summary = dict(Counter([obj["name"] for obj in self._targets_found]))
        for f in self._faces:
            if f.get("name") and f["name"] != "Unknown":
                self._summary[f["name"]] = self._summary.get(f["name"], 0) + 1

        # 9) save image (if needed)
        if self._save_file_folder and (self._state > 0 or self._always_save_latest_file):
            saved_image_path = self.save_image(self._targets_found, self._save_file_folder)

        # 10) fire events THREAD-SAFE
        def _fire_events():
            for target in self._targets_found:
                event_data = dict(target)
                event_data[ATTR_ENTITY_ID] = self.entity_id
                if saved_image_path:
                    event_data[SAVED_FILE] = saved_image_path
                self.hass.bus.async_fire(EVENT_OBJECT_DETECTED, event_data)

            for face in self._faces:
                face_event_data = {
                    "name": face.get("name"),
                    "confidence": face.get("confidence"),
                    "bounding_box": face.get("bounding_box"),
                    ATTR_ENTITY_ID: self.entity_id,
                }
                if saved_image_path:
                    face_event_data[SAVED_FILE] = saved_image_path
                self.hass.bus.async_fire(EVENT_FACE_DETECTED, face_event_data)

        self.hass.loop.call_soon_threadsafe(_fire_events)

        _LOGGER.info("Recognized faces: %s", list(recognized_names_set))

    # ------------------------------
    # HA properties
    # ------------------------------
    @property
    def camera_entity(self):
        return self._camera_entity

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return "targets"

    @property
    def should_poll(self):
        return False

    @property
    def extra_state_attributes(self):
        attr = {
            "targets_found": [{obj["name"]: obj["confidence"]} for obj in self._targets_found],
            "summary": self._summary,
            "all_objects": [{obj["name"]: obj["confidence"]} for obj in self._objects],
            "labels": self._labels,
            "recognized_faces": self._faces,
            "persons_with_names": self._person_labels,
            "new_mode": bool(self._new_mode),
            "default_min_confidence": float(self._default_min_confidence),
            "targets_confidence": dict(self._targets_confidence or {}),
            "exclude_targets": sorted(self._exclude_targets or []),
            "roi": {
                "y_min": self._roi_y_min,
                "x_min": self._roi_x_min,
                "y_max": self._roi_y_max,
                "x_max": self._roi_x_max,
            },
        }

        if self._save_file_folder:
            attr[CONF_SAVE_FILE_FORMAT] = self._save_file_format
            attr[CONF_SAVE_FILE_FOLDER] = str(self._save_file_folder)
            attr[CONF_SAVE_TIMESTAMPED_FILE] = self._save_timestamped_file
            attr[CONF_ALWAYS_SAVE_LATEST_FILE] = self._always_save_latest_file
            attr[CONF_SHOW_BOXES] = self._show_boxes

        if self._s3_bucket:
            attr[CONF_S3_BUCKET] = self._s3_bucket

        return attr

    # ------------------------------
    # Save image + overlays + index.json
    # ------------------------------
    def save_image(self, targets, directory) -> Optional[str]:
        """
        Saves an annotated image:
        - if save_timestamped_file: recognition_YYYYMMDD_HHMMSS.ext
        - else: recognition.ext (overwritten)
        - also saves recognition_latest.jpg if enabled
        - cleanup old timestamped files
        - update recognition_index.json atomically
        """
        try:
            directory = Path(directory)
            directory.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            _LOGGER.error("save_image: cannot ensure directory exists: %s", e)
            return None

        try:
            img = self._image.convert("RGBA")
        except UnidentifiedImageError:
            _LOGGER.warning("Rekognition unable to process image, bad data")
            return None
        except Exception as e:
            _LOGGER.error("save_image: error converting image: %s", e)
            return None

        # 1) draw identified faces (yellow)
        identified_faces = []
        for f in getattr(self, "_faces", []):
            name = f.get("name", "Unknown")
            if not name or name == "Unknown":
                continue
            fb = f.get("bounding_box")
            if not fb:
                continue

            img = draw_box_scaled(
                img,
                (fb["y_min"], fb["x_min"], fb["y_max"], fb["x_max"]),
                img.width,
                img.height,
                text=f"{name}",
                color=YELLOW,
                box_opacity=0.5,
                label_opacity=0.5,
                font_scale=self._label_font_scale,
            )
            identified_faces.append(f)

        def _face_center_in_person(face_box: dict, person_box: dict) -> bool:
            fc = _center_of_box(face_box)
            return _point_in_box(person_box, fc)

        # 2) draw person boxes (red) only if not identified
        MAX_RED_BOXES = self._max_red_boxes
        MIN_PERSON_AREA = self._min_red_box_area
        MIN_PERSON_CONF = 70.0
        LABEL_MIN_BOX_W = 180
        LABEL_MIN_BOX_H = 180

        red_candidates = []
        for p in getattr(self, "_person_labels", []):
            pb = p.get("bounding_box")
            if not pb:
                continue
            if p.get("matched_name"):
                continue

            has_identified_face_inside = False
            for f in identified_faces:
                fb = f.get("bounding_box")
                if fb and _face_center_in_person(fb, pb):
                    has_identified_face_inside = True
                    break
            if has_identified_face_inside:
                continue

            w = max(0.0, pb["x_max"] - pb["x_min"])
            h = max(0.0, pb["y_max"] - pb["y_min"])
            area = w * h
            conf = float(p.get("person_confidence", 0.0))

            if area < MIN_PERSON_AREA:
                continue
            if conf < MIN_PERSON_CONF:
                continue

            red_candidates.append((area, conf, pb))

        red_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)

        for area, conf, pb in red_candidates[:MAX_RED_BOXES]:
            left = int(pb["x_min"] * img.width)
            top = int(pb["y_min"] * img.height)
            right = int(pb["x_max"] * img.width)
            bottom = int(pb["y_max"] * img.height)
            bw = right - left
            bh = bottom - top

            label = "person"
            if bw < LABEL_MIN_BOX_W or bh < LABEL_MIN_BOX_H:
                label = ""

            img = draw_box_scaled(
                img,
                (pb["y_min"], pb["x_min"], pb["y_max"], pb["x_max"]),
                img.width,
                img.height,
                text=label,
                color=RED,
                box_opacity=0.5,
                label_opacity=0.5,
                font_scale=self._label_font_scale,
            )

        # ---- compute index values ----
        recognized_names = sorted(self._recognized_names_set())
        total_people = self._count_people_from_targets()
        recognized_count = len(recognized_names)
        unrecognized_count = max(0, total_people - recognized_count)
        ts_iso = _utc_iso_now()

        # file format
        ext = str(self._save_file_format).lower()
        if ext not in ("jpg", "png"):
            ext = "jpg"

        # choose output filename (timestamped vs fixed)
        if self._save_timestamped_file:
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recognition_{stamp}.{ext}"
        else:
            filename = f"recognition.{ext}"

        save_path = directory / filename

        # 3) save main file correctly (JPG vs PNG)
        try:
            if ext == "jpg":
                out = img.convert("RGB")
                out.save(save_path, format="JPEG", quality=85, subsampling=2)
            else:
                out = img  # keep RGBA if you want
                out.save(save_path, format="PNG", optimize=True)
        except Exception as e:
            _LOGGER.error("save_image: error saving %s: %s", save_path, e)
            return None

        # 4) save latest jpg (optional)
        if self._always_save_latest_file:
            try:
                latest_path = directory / "recognition_latest.jpg"
                img.convert("RGB").save(latest_path, format="JPEG", quality=85, subsampling=2)
            except Exception as e:
                _LOGGER.warning("save_image: cannot write latest file: %s", e)

        # 5) cleanup old (only timestamped)
        _cleanup_old_recognition_files(directory, keep=self._max_saved_files, prefix="recognition_")

        objects_summary = self._get_object_summary_for_index()

        # 6) update index only if timestamped (altrimenti avrebbe sempre 1 item e basta)
        if self._save_timestamped_file:
            _update_recognition_index(
                directory=directory,
                filename=save_path.name,
                timestamp_iso=ts_iso,
                recognized=recognized_names,
                unrecognized_count=unrecognized_count,
                keep=self._max_saved_files,
                prefix="recognition_",
                objects=objects_summary,
            )

            index_path = directory / "recognition_index.json"
            index_data = _load_json_index(index_path)
        else:
            # se non timestamped, aggiorno solo updated_at e lascio items come sono
            index_path = directory / "recognition_index.json"
            index_data = _load_json_index(index_path)
            index_data["updated_at"] = _utc_iso_now()
            _atomic_write_json(index_path, index_data)

        # 7) runtime cache + websocket/card event
        last_result = {
            "id": save_path.stem,
            "timestamp": ts_iso,
            "recognized": recognized_names,
            "unrecognized_count": unrecognized_count,
            "file": save_path.name,
            "objects": objects_summary or {},
            "camera_entity": self._camera_entity,
            "entity_id": self.entity_id,
        }

        def _publish():
            self.hass.data.setdefault(DOMAIN, {})
            self.hass.data[DOMAIN]["last_result"] = last_result
            self.hass.data[DOMAIN]["index"] = index_data

            self.hass.bus.async_fire(
                EVENT_UPDATED,
                {"last_result": last_result, "updated_at": index_data.get("updated_at")},
            )

        # update recognized sensor with filename (NO path)
        sensor = self.hass.data.get(DOMAIN, {}).get("recognized_person_sensor")
        if sensor:
            try:
                coro = sensor.update_recognized_faces(
                    recognized_names,
                    dict(self._confidence_details),
                    self._person_found,
                    file=save_path.name,
                )
                self.hass.loop.call_soon_threadsafe(self.hass.async_create_task, coro)
            except Exception as e:
                _LOGGER.warning("save_image: failed to update recognized_person_sensor: %s", e)

        self.hass.loop.call_soon_threadsafe(_publish)

        return str(save_path)
