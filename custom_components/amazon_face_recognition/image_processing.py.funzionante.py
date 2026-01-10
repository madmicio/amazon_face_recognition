"""
Platform that will perform object detection + face recognition.
- Person boxes (RED) from detect_labels
- Face boxes (YELLOW) from detect_faces
- Face identification per-face by cropping and calling search_faces_by_image on the crop

Extra features:
- Save timestamped annotated images: recognition_YYYYMMDD_HHMMSS.jpg/png
- Keep only last N saved files (max_saved_files)
- Maintain /config/www/snapshots/recognition_index.json with:
  updated_at + items [{file,timestamp,recognized,unrecognized_count}, ...]

Unrecognized count strategy (robust):
- total_people = count of "person" boxes from detect_labels (targets_found) after filtering
- recognized_count = number of unique recognized names (faces matched in collection)
- unrecognized_count = max(0, total_people - recognized_count)
"""

from collections import namedtuple, Counter
import io
import logging
import re
from pathlib import Path
import asyncio
import datetime
import json
from typing import Optional, Dict, Any
import boto3
import botocore

from PIL import Image, ImageDraw, UnidentifiedImageError, ImageFont

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.image_processing import (
    CONF_CONFIDENCE,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_SOURCE,
    PLATFORM_SCHEMA,
    ImageProcessingEntity,
)
from homeassistant.core import split_entity_id
from homeassistant.const import ATTR_ENTITY_ID

_LOGGER = logging.getLogger(__name__)

DOMAIN = "amazon_face_recognition"

# -----------------------------
# Config keys / defaults
# -----------------------------
CONF_REGION = "region_name"
CONF_ACCESS_KEY_ID = "aws_access_key_id"
CONF_SECRET_ACCESS_KEY = "aws_secret_access_key"
CONF_COLLECTION_ID = "collection_id"

DEFAULT_REGION = "us-east-1"
SUPPORTED_REGIONS = [
    "us-east-1", "us-east-2", "us-west-1", "us-west-2", "ca-central-1",
    "eu-west-1", "eu-central-1", "eu-west-2", "eu-west-3",
    "ap-southeast-1", "ap-southeast-2", "ap-northeast-2", "ap-northeast-1",
    "ap-south-1", "sa-east-1",
]

CONF_BOTO_RETRIES = "boto_retries"
CONF_SAVE_FILE_FORMAT = "save_file_format"
CONF_SAVE_FILE_FOLDER = "save_file_folder"
CONF_SAVE_TIMESTAMPED_FILE = "save_timestamped_file"
CONF_ALWAYS_SAVE_LATEST_FILE = "always_save_latest_file"
CONF_SHOW_BOXES = "show_boxes"
CONF_SCALE = "scale"
CONF_TARGET = "target"
CONF_TARGETS = "targets"
CONF_S3_BUCKET = "s3_bucket"

CONF_ROI_Y_MIN = "roi_y_min"
CONF_ROI_X_MIN = "roi_x_min"
CONF_ROI_Y_MAX = "roi_y_max"
CONF_ROI_X_MAX = "roi_x_max"

CONF_MAX_SAVED_FILES = "max_saved_files"
DEFAULT_MAX_SAVED_FILES = 10

DEFAULT_BOTO_RETRIES = 5
PERSON = "person"
DEFAULT_TARGETS = [{CONF_TARGET: PERSON}]

CONF_LABEL_FONT_SCALE = "label_font_scale"
CONF_MAX_RED_BOXES = "max_red_boxes"
CONF_MIN_RED_BOX_AREA = "min_red_box_area"

DEFAULT_LABEL_FONT_SCALE = 0.020
DEFAULT_MAX_RED_BOXES = 6
DEFAULT_MIN_RED_BOX_AREA = 0.03


DEFAULT_ROI_Y_MIN = 0.0
DEFAULT_ROI_Y_MAX = 1.0
DEFAULT_ROI_X_MIN = 0.0
DEFAULT_ROI_X_MAX = 1.0

DEFAULT_SCALE = 1.0

EVENT_OBJECT_DETECTED = "rekognition.object_detected"
EVENT_FACE_DETECTED = "rekognition.face_detected"

EXCLUDED_OBJECT_LABELS = {
    "person",
    "adult",
    "child",
    "male",
    "female",
    "man",
    "woman",
    "people",
}

CONF_EXCLUDED_OBJECT_LABELS = "excluded_object_labels"

SERVICES_REGISTERED = False


FONT_PATH = Path(__file__).parent / "fonts" / "DejaVuSans.ttf"

SAVED_FILE = "saved_file"
MIN_CONFIDENCE = 0.1
JPG = "jpg"
PNG = "png"

# Colors
RED = (255, 0, 0)       # person
YELLOW = (255, 255, 0)  # face


TARGETS_SCHEMA = {
    vol.Required(CONF_TARGET): cv.string,
    vol.Optional(CONF_CONFIDENCE): vol.All(vol.Coerce(float), vol.Range(min=10, max=100)),
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_REGION, default=DEFAULT_REGION): vol.In(SUPPORTED_REGIONS),
        vol.Required(CONF_ACCESS_KEY_ID): cv.string,
        vol.Required(CONF_SECRET_ACCESS_KEY): cv.string,
        vol.Optional(CONF_TARGETS, default=DEFAULT_TARGETS): vol.All(
            cv.ensure_list, [vol.Schema(TARGETS_SCHEMA)]
        ),

        vol.Optional(CONF_ROI_Y_MIN, default=DEFAULT_ROI_Y_MIN): cv.small_float,
        vol.Optional(CONF_ROI_X_MIN, default=DEFAULT_ROI_X_MIN): cv.small_float,
        vol.Optional(CONF_ROI_Y_MAX, default=DEFAULT_ROI_Y_MAX): cv.small_float,
        vol.Optional(CONF_ROI_X_MAX, default=DEFAULT_ROI_X_MAX): cv.small_float,

        vol.Optional(CONF_SCALE, default=DEFAULT_SCALE): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=1)),
        vol.Optional(CONF_SAVE_FILE_FOLDER): cv.string,
        vol.Optional(CONF_MAX_SAVED_FILES, default=DEFAULT_MAX_SAVED_FILES): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=500)
        ),
        vol.Optional(CONF_SAVE_FILE_FORMAT, default=JPG): vol.In([JPG, PNG]),
        vol.Optional(CONF_SAVE_TIMESTAMPED_FILE, default=False): cv.boolean,
        vol.Optional(CONF_ALWAYS_SAVE_LATEST_FILE, default=False): cv.boolean,

        vol.Optional(CONF_S3_BUCKET): cv.string,
        vol.Optional(CONF_SHOW_BOXES, default=True): cv.boolean,
        vol.Optional(CONF_BOTO_RETRIES, default=DEFAULT_BOTO_RETRIES): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(CONF_COLLECTION_ID): cv.string,
        vol.Optional(CONF_LABEL_FONT_SCALE, default=DEFAULT_LABEL_FONT_SCALE): vol.All(
            vol.Coerce(float), vol.Range(min=0.005, max=0.10)
        ),
        vol.Optional(CONF_MAX_RED_BOXES, default=DEFAULT_MAX_RED_BOXES): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=50)
        ),
        vol.Optional(CONF_MIN_RED_BOX_AREA, default=DEFAULT_MIN_RED_BOX_AREA): vol.All(
            vol.Coerce(float), vol.Range(min=0.0, max=1.0)
        ),
        vol.Optional(CONF_EXCLUDED_OBJECT_LABELS, default=list(EXCLUDED_OBJECT_LABELS)): vol.All(
            cv.ensure_list,
            [cv.string],
        ),


    }
)

Box = namedtuple("Box", "y_min x_min y_max x_max")
Point = namedtuple("Point", "y x")


# -----------------------------
# Small helpers (module-level)
# -----------------------------
def with_alpha(color, opacity: float):
    r, g, b = color
    a = int(255 * max(0.0, min(1.0, opacity)))
    return (r, g, b, a)




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


def _folder_to_local_base(folder: Path) -> str:
    """
    Convert a /config/www/... path to a /local/... base URL.
    Fallback: /local
    """
    try:
        s = str(folder)
        # Home Assistant maps /config/www -> /local
        if s.startswith("/config/www/"):
            rel = s[len("/config/www/") :].strip("/")
            return f"/local/{rel}" if rel else "/local"
        if s == "/config/www":
            return "/local"
    except Exception:
        pass
    return "/local"



def draw_box_scaled(
    img: Image.Image,
    box,
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
    box: (y_min, x_min, y_max, x_max) normalized 0..1
    Draw bounding box + optional label with alpha overlays on RGBA.
    Returns updated RGBA image.
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    y_min, x_min, y_max, x_max = box

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


def get_valid_filename(name: str) -> str:
    return re.sub(r"(?u)[^-\w.]", "", str(name).strip().replace(" ", "_"))


def _utc_iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _cleanup_old_recognition_files(directory: Path, keep: int = 10, prefix: str = "recognition_") -> None:
    """Keep only the newest `keep` files that start with prefix (by mtime)."""
    try:
        keep = int(keep)
        if keep < 1:
            return

        files = sorted(
            [p for p in directory.glob(f"{prefix}*") if p.is_file()],
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
    """
    Update/create JSON index:
    {
      "updated_at": "...Z",
      "items": [
         {"file": "...", "timestamp": "...Z", "recognized": [...], "unrecognized_count": N},
         ...
      ]
    }
    Keeps last `keep` items and removes entries pointing to files not present.
    """
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

        existing_files = {p.name for p in directory.glob(f"{prefix}*") if p.is_file()}
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

    def __init__(self, hass):
        self.hass = hass
        self._attr_name = "Last Recognized Person"
        self._attr_unique_id = f"{DOMAIN}_recognized_person"

        self._recognized_names = set()
        self._confidence_details = {}

        self._last_scan_time = "no scan from boot"
        self._last_scan_time_person_found = "no person found from boot"
        self._last_scan_person_found = False
        self._last_scan = []

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
        }

    async def update_recognized_faces(self, recognized_names, recognized_faces_details, person_found: bool):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._last_scan_time = now
        self._last_scan_person_found = bool(person_found)
        if person_found:
            self._last_scan_time_person_found = now

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

        self.async_write_ha_state()

        if self._reset_task and not self._reset_task.done():
            self._reset_task.cancel()

        async def _reset_later():
            try:
                await asyncio.sleep(15)
                self._recognized_names.clear()
                self.async_write_ha_state()
            except asyncio.CancelledError:
                return

        self._reset_task = self.hass.async_create_task(_reset_later())


class AWSPersonSensor(SensorEntity):
    """Sensor entity to track registered persons in AWS Rekognition."""

    def __init__(self, hass, rekognition_client, collection_id):
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


# -----------------------------
# Platform setup
# -----------------------------
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up platform (async)."""
    max_saved_files = config.get(CONF_MAX_SAVED_FILES, DEFAULT_MAX_SAVED_FILES)
    collection_id = config.get(CONF_COLLECTION_ID)

    aws_config = {
        CONF_REGION: config[CONF_REGION],
        CONF_ACCESS_KEY_ID: config[CONF_ACCESS_KEY_ID],
        CONF_SECRET_ACCESS_KEY: config[CONF_SECRET_ACCESS_KEY],
    }

    async def _make_client(service: str):
        return await hass.async_add_executor_job(lambda: boto3.client(service, **aws_config))

    # retry NON bloccante
    rekognition_client = None
    last_err = None
    for attempt in range(0, int(config[CONF_BOTO_RETRIES]) + 1):
        try:
            rekognition_client = await _make_client("rekognition")
            last_err = None
            break
        except Exception as e:
            last_err = e
            _LOGGER.warning("boto3 rekognition client failed, retry %s/%s: %s",
                            attempt, config[CONF_BOTO_RETRIES], e)
            await asyncio.sleep(1)

    if rekognition_client is None:
        raise Exception(f"Failed to create boto3 rekognition client. Last error: {last_err}")

    s3_bucket = config.get(CONF_S3_BUCKET)
    s3_client = await _make_client("s3") if s3_bucket else None

    save_file_folder = config.get(CONF_SAVE_FILE_FOLDER)
    save_file_folder = Path(save_file_folder) if save_file_folder else None

    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(
            ObjectDetection(
                rekognition_client=rekognition_client,
                s3_client=s3_client,
                region=config.get(CONF_REGION),
                targets=config.get(CONF_TARGETS),
                confidence=config.get(CONF_CONFIDENCE),
                roi_y_min=config[CONF_ROI_Y_MIN],
                roi_x_min=config[CONF_ROI_X_MIN],
                roi_y_max=config[CONF_ROI_Y_MAX],
                roi_x_max=config[CONF_ROI_X_MAX],
                scale=config[CONF_SCALE],
                show_boxes=config[CONF_SHOW_BOXES],
                save_file_format=config[CONF_SAVE_FILE_FORMAT],
                save_file_folder=save_file_folder,
                save_timestamped_file=config.get(CONF_SAVE_TIMESTAMPED_FILE),
                always_save_latest_file=config.get(CONF_ALWAYS_SAVE_LATEST_FILE),
                s3_bucket=s3_bucket,
                camera_entity=camera.get(CONF_ENTITY_ID),
                name=camera.get(CONF_NAME),
                collection_id=collection_id,
                max_saved_files=max_saved_files,
                label_font_scale=config.get(CONF_LABEL_FONT_SCALE),
                max_red_boxes=config.get(CONF_MAX_RED_BOXES),
                min_red_box_area=config.get(CONF_MIN_RED_BOX_AREA),
                excluded_object_labels=config.get(CONF_EXCLUDED_OBJECT_LABELS),
            )
        )

    recognized_sensor = RecognizedPersonSensor(hass)
    hass.recognized_person_sensor = recognized_sensor

    # ➕ aggiungi il sensore AWS SOLO se collection_id è configurato
    if collection_id:
        entities.append(AWSPersonSensor(hass, rekognition_client, collection_id))
    entities.append(recognized_sensor)

    # ✅ BOOTSTRAP: popola hass.data dal file su disco (così la card si riempie al boot)
    if save_file_folder:
        try:
            index_data, last_result = await hass.async_add_executor_job(
                _read_bootstrap_from_disk,
                save_file_folder,
                bool(config.get(CONF_ALWAYS_SAVE_LATEST_FILE)),
            )

            hass.data.setdefault(DOMAIN, {})
            hass.data[DOMAIN]["index"] = index_data
            hass.data[DOMAIN]["last_result"] = last_result

            _LOGGER.info(
                "amazon_face_recognition: boot preload OK (items=%s)",
                len(index_data.get("items") or []),
            )
        except Exception as e:
            _LOGGER.warning("amazon_face_recognition: boot preload failed: %s", e)



    async_add_entities(entities)



# -----------------------------
# Main ImageProcessing entity
# -----------------------------
class ObjectDetection(ImageProcessingEntity):
    """Object + face recognition."""

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

        _LOGGER.info("Servizi Amazon Rekognition registrati con successo.")

    async def async_index_face(self, call):
        if not self._collection_id:
            _LOGGER.error("collection_id non configurato: impossibile indicizzare volti.")
            return
        file_path = call.data.get("file_path")
        name = call.data["name"].strip().title()

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

        except Exception as e:
            _LOGGER.error("Error indexing face: %s", str(e))

    async def async_delete_faces_by_name(self, call):
        if not self._collection_id:
            _LOGGER.error("collection_id non configurato: impossibile cancellare volti.")
            return
        name_to_delete = call.data.get("name")

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

        except Exception as e:
            _LOGGER.error("Errore nella cancellazione di tutti i volti: %s", e)

    def __init__(
        self,
        rekognition_client,
        s3_client,
        region,
        targets,
        confidence,
        roi_y_min,
        roi_x_min,
        roi_y_max,
        roi_x_max,
        scale,
        show_boxes,
        save_file_format,
        save_file_folder,
        save_timestamped_file,
        always_save_latest_file,
        s3_bucket,
        camera_entity,
        name=None,
        collection_id=None,
        max_saved_files=DEFAULT_MAX_SAVED_FILES,
        label_font_scale=DEFAULT_LABEL_FONT_SCALE,
        max_red_boxes=DEFAULT_MAX_RED_BOXES,
        min_red_box_area=DEFAULT_MIN_RED_BOX_AREA,
        excluded_object_labels=None,

    ):
        self._collection_id = collection_id
        self._aws_rekognition_client = rekognition_client
        self._aws_s3_client = s3_client
        self._aws_region = region

        self._confidence = confidence
        self._targets = targets or []
        for target in self._targets:
            if CONF_CONFIDENCE not in target:
                target.update({CONF_CONFIDENCE: self._confidence})

        self._targets_names = [target[CONF_TARGET] for target in self._targets]
        self._summary = {target: 0 for target in self._targets_names}

        self._camera_entity = camera_entity
        if name:
            self._name = name
        else:
            entity_name = split_entity_id(camera_entity)[1]
            self._name = f"rekognition_{entity_name}"

        self._state = None
        self._objects = []
        self._labels = []
        self._targets_found = []

        self._scale = scale
        self._show_boxes = show_boxes

        self._save_file_format = save_file_format
        self._save_file_folder = save_file_folder
        self._save_timestamped_file = save_timestamped_file
        self._always_save_latest_file = always_save_latest_file
        self._s3_bucket = s3_bucket

        self._image = None
        self._image_width = None
        self._image_height = None

        self._faces = []              # faces with bbox + match info
        self._person_labels = []      # person bbox + matched name
        self._confidence_details = {} # name -> best similarity
        self._person_found = False
        self._has_identified_faces = False

        try:
            self._max_saved_files = int(max_saved_files or DEFAULT_MAX_SAVED_FILES)
        except Exception:
            self._max_saved_files = DEFAULT_MAX_SAVED_FILES
        try:
            self._label_font_scale = float(label_font_scale)
        except Exception:
            self._label_font_scale = DEFAULT_LABEL_FONT_SCALE

        # clamp di sicurezza
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
            self._excluded_object_labels = {
                str(x).strip().lower() for x in excluded_object_labels
            }
        else:
            self._excluded_object_labels = set(EXCLUDED_OBJECT_LABELS)



    # ------------------------------
    # Count & sets helpers (methods)
    # ------------------------------
    def _recognized_names_set(self) -> set:
        names = set()
        for f in getattr(self, "_faces", []):
            n = f.get("name")
            if n and n != "Unknown":
                names.add(str(n))
        return names
    def _get_object_summary_for_index(self) -> dict:
        """
        Build a filtered objects summary for recognition_index.json:
        - start from self._summary (AWS labels + names added by code)
        - remove person-related labels
        - remove recognized names (Sofia, Emma, etc.)
        - keep only AWS 'real' objects
        """
        # base blacklist (se non hai ancora la config YAML)
        excluded = getattr(self, "_excluded_object_labels", None)
        if not excluded:
            excluded = set(EXCLUDED_OBJECT_LABELS)

        excluded = {str(x).strip().lower() for x in excluded if str(x).strip()}

        recognized_names = {str(x).strip() for x in self._recognized_names_set() if str(x).strip()}

        out = {}
        summary = getattr(self, "_summary", {}) or {}

        for label, count in summary.items():
            if label is None:
                continue
            key = str(label).strip()
            if not key:
                continue

            key_l = key.lower()

            # 1) escludi classi persona
            if key_l in excluded:
                continue

            # 2) escludi nomi riconosciuti (ExternalImageId)
            # NB: i nomi possono avere maiuscole (Sofia), quindi confronto case-sensitive
            if key in recognized_names:
                continue

            # count deve essere int
            try:
                out[key_l] = int(count)
            except Exception:
                continue

        return out

    def _count_people_from_targets(self) -> int:
        """
        Count people using detect_labels "person" instances (targets_found),
        filtering likely-spurious tiny/low-confidence boxes.
        """
        persons = [o for o in getattr(self, "_targets_found", []) if o.get("name") == "person"]
        if not persons:
            return 0

        # Tuning: align to your target confidence for person (80) + avoid micro boxes
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

    # ------------------------------
    # per-face search helpers
    # ------------------------------
    def _crop_face_bytes(self, face_box_norm: dict) -> bytes:
        """Crop a face region from self._image using normalized coords and return JPEG bytes."""
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
        """Search a single face crop in the Rekognition collection."""
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
    # HA processing
    # ------------------------------
    def process_image(self, image: bytes):
        """Process an image."""
        self._faces = []
        self._person_labels = []
        self._confidence_details = {}
        self._person_found = False
        self._has_identified_faces = False

        try:
            self._image = Image.open(io.BytesIO(bytearray(image)))
            self._image_width, self._image_height = self._image.size
        except Exception as e:
            _LOGGER.error("Errore durante il caricamento dell'immagine: %s", e)
            return

        if self._scale != DEFAULT_SCALE:
            newsize = (
                int(self._image_width * self._scale),
                int(self._image_height * self._scale),
            )
            self._image.thumbnail(newsize, Image.LANCZOS)
            self._image_width, self._image_height = self._image.size
            with io.BytesIO() as output:
                self._image.save(output, format="JPEG")
                image = output.getvalue()
            _LOGGER.debug("Image scaled: %s W=%s H=%s", self._scale, self._image_width, self._image_height)

        # reset per-frame
        self._state = None
        self._objects = []
        self._labels = []
        self._targets_found = []
        self._summary = {target: 0 for target in self._targets_names}

        saved_image_path = None
        recognized_names_set = set()

        # 1) detect_labels
        try:
            response_labels = self._aws_rekognition_client.detect_labels(Image={"Bytes": image})
            self._objects, self._labels = get_objects(response_labels)
        except botocore.exceptions.ClientError as error:
            _LOGGER.error("Errore in detect_labels: %s", error)
            return
        except Exception as e:
            _LOGGER.error("Errore generico in detect_labels: %s", e)
            return

        self._targets_found = [obj for obj in self._objects if obj["confidence"] >= MIN_CONFIDENCE]
        self._state = len(self._targets_found)

        persons = [o for o in self._targets_found if o["name"] == "person"]
        self._person_found = len(persons) > 0

        # 2) detect_faces (only if person present)
        faces_detected = []
        if self._person_found:
            try:
                faces_resp = self._aws_rekognition_client.detect_faces(
                    Image={"Bytes": image},
                    Attributes=["DEFAULT"],
                )
                for fd in faces_resp.get("FaceDetails", []):
                    bb = fd.get("BoundingBox")
                    if not bb:
                        continue
                    x_min = float(bb["Left"])
                    y_min = float(bb["Top"])
                    x_max = x_min + float(bb["Width"])
                    y_max = y_min + float(bb["Height"])
                    faces_detected.append(
                        {"bounding_box": {"x_min": _clamp(x_min), "y_min": _clamp(y_min), "x_max": _clamp(x_max), "y_max": _clamp(y_max)}}
                    )
            except botocore.exceptions.ClientError as e:
                _LOGGER.error("detect_faces error: %s", e)
            except Exception as e:
                _LOGGER.error("detect_faces generic error: %s", e)

        # 3) per-face recognition
        for face in faces_detected:
            match = None
            if self._collection_id:
                face_bytes = self._crop_face_bytes(face["bounding_box"])
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

        # 4) associate each person box with best face inside (optional; used for drawing logic)
        for p in persons:
            p_box = p["bounding_box"]
            pb = {"x_min": p_box["x_min"], "y_min": p_box["y_min"], "x_max": p_box["x_max"], "y_max": p_box["y_max"]}

            best = None
            for f in self._faces:
                fc = _center_of_box(f["bounding_box"])
                if _point_in_box(pb, fc):
                    if f.get("name") and f["name"] != "Unknown":
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

        # summary
        self._summary = dict(Counter([obj["name"] for obj in self._targets_found]))
        for f in self._faces:
            if f.get("name") and f["name"] != "Unknown":
                self._summary[f["name"]] = self._summary.get(f["name"], 0) + 1

        # save image (and update index.json there)
        if self._save_file_folder and (self._state > 0 or self._always_save_latest_file):
            saved_image_path = self.save_image(self._targets_found, self._save_file_folder)

        # fire events
        for target in self._targets_found:
            event_data = target.copy()
            event_data[ATTR_ENTITY_ID] = self.entity_id
            if saved_image_path:
                event_data[SAVED_FILE] = saved_image_path
            self.hass.bus.fire(EVENT_OBJECT_DETECTED, event_data)

        for face in self._faces:
            face_event_data = {
                "name": face.get("name"),
                "confidence": face.get("confidence"),
                "bounding_box": face.get("bounding_box"),
                ATTR_ENTITY_ID: self.entity_id,
            }
            if saved_image_path:
                face_event_data[SAVED_FILE] = saved_image_path
            self.hass.bus.fire(EVENT_FACE_DETECTED, face_event_data)

        # update sensor
        if hasattr(self.hass, "recognized_person_sensor"):
            self.hass.loop.call_soon_threadsafe(
                self.hass.async_create_task,
                self.hass.recognized_person_sensor.update_recognized_faces(
                    list(recognized_names_set),
                    dict(self._confidence_details),
                    self._person_found,
                ),
            )

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
            "targets": self._targets,
            "targets_found": [{obj["name"]: obj["confidence"]} for obj in self._targets_found],
            "summary": self._summary,
            "all_objects": [{obj["name"]: obj["confidence"]} for obj in self._objects],
            "labels": self._labels,
            "recognized_faces": self._faces,
            "persons_with_names": self._person_labels,
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
    def save_image(self, targets, directory) -> str:
        """
        Saves an annotated image:
        - recognition_YYYYMMDD_HHMMSS.<ext>
        - cleanup old files to keep last N
        - update recognition_index.json (atomic)
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

            label = f"{name}"
            img = draw_box_scaled(
                img,
                (fb["y_min"], fb["x_min"], fb["y_max"], fb["x_max"]),
                img.width,
                img.height,
                text=label,
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

        # ---- compute index.json values (AWS-based people count) ----
        recognized_names = sorted(self._recognized_names_set())
        total_people = self._count_people_from_targets()
        recognized_count = len(recognized_names)
        unrecognized_count = max(0, total_people - recognized_count)
        ts_iso = _utc_iso_now()

        # 3) save timestamped file
        ext = str(self._save_file_format).lower()
        if ext not in ("jpg", "png"):
            ext = "jpg"

        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recognition_{stamp}.{ext}"
        save_path = directory / filename

        try:
            out = img.convert("RGB") if ext == "jpg" else img
            out.save(save_path, quality=85, subsampling=2)
        except Exception as e:
            _LOGGER.error("save_image: error saving %s: %s", save_path, e)
            return None

        # 4) cleanup old files and update index
        _cleanup_old_recognition_files(directory, keep=self._max_saved_files, prefix="recognition_")

        objects_summary = self._get_object_summary_for_index()


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

        # 5) aggiorna runtime cache + websocket push (zero-config card)
        from .const import DOMAIN, EVENT_UPDATED

        index_path = directory / "recognition_index.json"
        index_data = _load_json_index(index_path)

        image_url = f"/local/snapshots/{save_path.name}"
        latest_url = f"/local/snapshots/recognition_latest.{ext}" if self._always_save_latest_file else None

        last_result = {
            "id": save_path.stem,
            "timestamp": ts_iso,
            "recognized": recognized_names,
            "unrecognized_count": unrecognized_count,
            "file": save_path.name,
            "image_url": image_url,
            "latest_url": latest_url,
            "objects": objects_summary or {},
            "camera_entity": self._camera_entity,
            "entity_id": self.entity_id,
        }

        def _publish():
            # hass.data update (thread-safe)
            self.hass.data.setdefault(DOMAIN, {})
            self.hass.data[DOMAIN]["last_result"] = last_result
            self.hass.data[DOMAIN]["index"] = index_data

            # bus event (thread-safe)
            self.hass.bus.async_fire(
                EVENT_UPDATED,
                {"last_result": last_result, "updated_at": index_data.get("updated_at")},
            )

        # esegui tutto nel main loop di HA
        self.hass.loop.call_soon_threadsafe(_publish)

