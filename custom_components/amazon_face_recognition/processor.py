# custom_components/amazon_face_recognition/processor.py
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import datetime
import io
import json
import logging
from typing import Any, Dict, Optional, Tuple

import botocore
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    FONT_PATH,
    EVENT_UPDATED,
    EVENT_OBJECT_DETECTED,
    EVENT_FACE_DETECTED,
    SAVED_FILE,
    RED,
    YELLOW,
    EXCLUDED_OBJECT_LABELS,
    # NEW (must exist in const.py):
    # CONF_LABEL_FONT_LEVEL
    # DEFAULT_LABEL_FONT_LEVEL
    CONF_LABEL_FONT_LEVEL,
    DEFAULT_LABEL_FONT_LEVEL,
)

from .websocket import publish_faces_update, publish_update

_LOGGER = logging.getLogger(__name__)


# -----------------------------
# Small helpers
# -----------------------------
def with_alpha(color, opacity: float):
    r, g, b = color
    a = int(255 * max(0.0, min(1.0, opacity)))
    return (r, g, b, a)


def _utc_iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


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


def _read_bootstrap_from_disk(directory: Path, always_save_latest: bool):
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
        unknown = int(latest.get("unrecognized_count") or 0) > 0
        last_result = {
            "id": Path(file).stem if file else None,
            "timestamp": latest.get("timestamp"),
            "recognized": latest.get("recognized") or [],
            "unknown_person_found": bool(latest.get("unknown_person_found", unknown)),
            "file": file,
            "image_url": image_url,
            "latest_url": f"{base}/recognition_latest.jpg" if always_save_latest else None,
            "objects": latest.get("objects") or {},
        }
    else:
        last_result = {}

    return index_data, last_result


def _cleanup_old_recognition_files(directory: Path, keep: int, prefix: str = "recognition_") -> None:
    try:
        keep = int(keep)
        if keep < 1:
            return
        files = sorted(
            [
                p for p in directory.glob(f"{prefix}*")
                if p.is_file() and p.name not in ("recognition_latest.jpg", "recognition.jpg")
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
    unknown_person_found: bool,
    keep: int,
    objects: Optional[Dict[str, Any]] = None,
) -> dict:
    index_path = directory / "recognition_index.json"
    data = _load_json_index(index_path)

    recognized = sorted({str(x) for x in (recognized or []) if x})

    by_file = {}
    for it in data.get("items", []):
        if isinstance(it, dict) and it.get("file"):
            by_file[str(it["file"])] = it

    by_file[filename] = {
        "file": filename,
        "timestamp": timestamp_iso,
        "recognized": recognized,
        "unknown_person_found": bool(unknown_person_found),
        "objects": objects or {},
    }

    existing_files = {p.name for p in directory.glob("recognition_*") if p.is_file()}
    existing_files.discard("recognition_latest.jpg")
    existing_files.discard("recognition.jpg")
    existing_files.add(filename)

    by_file = {k: v for k, v in by_file.items() if k in existing_files}

    def _key(it: dict):
        ts = it.get("timestamp") or ""
        return (ts, it.get("file") or "")

    items = sorted(by_file.values(), key=_key, reverse=True)[: max(1, int(keep))]
    data["updated_at"] = _utc_iso_now()
    data["items"] = items
    _atomic_write_json(index_path, data)
    return data


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
    


# -----------------------------
# FONT LEVEL (1..20) -> SCALE
# -----------------------------
def font_level_to_scale(level: int) -> float:
    """
    Maps a user-friendly slider (1..20) to an internal scale factor.
    Level 6 == ~0.026 (your previous reference).
    """
    try:
        level = int(level)
    except Exception:
        level = int(DEFAULT_LABEL_FONT_LEVEL)

    level = max(1, min(20, level))

    table = {
        1: 0.010,
        2: 0.012,
        3: 0.014,
        4: 0.016,
        5: 0.018,
        6: 0.026,  # reference
        7: 0.030,
        8: 0.034,
        9: 0.038,
        10: 0.042,
        11: 0.046,
        12: 0.050,
        13: 0.055,
        14: 0.060,
        15: 0.066,
        16: 0.072,
        17: 0.078,
        18: 0.085,
        19: 0.092,
        20: 0.100,
    }
    return table[level]


def _load_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Always try truetype first; if it fails, log why and fallback to default.
    """
    try:
        return ImageFont.truetype(str(FONT_PATH), font_size)
    except Exception as e:
        _LOGGER.warning("Font truetype load failed (%s): %s", FONT_PATH, e)
        return ImageFont.load_default()


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
    font_scale: float = 0.02,
):
    """
    Draw a bounding box + label.
    IMPORTANT: the font size must actually change with font_scale.
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

    fs = max(0.005, min(0.10, float(font_scale or 0.02)))

    # ✅ fix: do NOT clamp to 14, otherwise small scales look "stuck"
    font_size = max(6, int(min(img_w, img_h) * fs))

    font = _load_font(font_size)

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

    bg_left = max(0, int(text_x - pad))
    bg_top = max(0, int(text_y - pad))
    bg_right = min(img_w, int(text_x + max_w + pad))
    bg_bottom = min(img_h, int(text_y + total_h + pad))

    bg_rgba = with_alpha((0, 0, 0), label_opacity)
    odraw.rectangle([bg_left, bg_top, bg_right, bg_bottom], fill=bg_rgba)

    y = text_y
    for (line, (_w, h)) in zip(lines, line_sizes):
        odraw.text((text_x, y), line, font=font, fill=(255, 255, 255, 255))
        y += h + line_gap

    return Image.alpha_composite(img, overlay)


def get_objects(response: dict):
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

                objects.append(
                    {
                        "name": label["Name"].lower(),
                        "confidence": round(instance["Confidence"], dp),
                        "bounding_box": {
                            "x_min": round(x_min, dp),
                            "y_min": round(y_min, dp),
                            "x_max": round(x_max, dp),
                            "y_max": round(y_max, dp),
                            "width": round(w, dp),
                            "height": round(h, dp),
                        },
                        "centroid": {"x": round(x_min + w / 2, dp), "y": round(y_min + h / 2, dp)},
                    }
                )
        else:
            labels.append({"name": label["Name"].lower(), "confidence": round(label["Confidence"], dp)})

    return objects, labels


@dataclass
class AFRProcessResult:
    last_result: dict
    index_data: dict


class AFRProcessor:
    def __init__(self, hass: HomeAssistant, rekognition_client, collection_id: Optional[str], options: dict) -> None:
        self.hass = hass
        self._rekognition = rekognition_client
        self._collection_id = collection_id
        self._opt = options or {}

        # per-frame state
        self._image: Optional[Image.Image] = None
        self._image_width: int = 0
        self._image_height: int = 0

        self._objects = []
        self._labels = []
        self._targets_found = []
        self._faces = []
        self._person_labels = []
        self._confidence_details = {}
        self._person_found = False

    def update_options(self, options: dict) -> None:
        self._opt = options or {}

    async def async_bootstrap(self) -> None:
        try:
            folder = Path(self._opt.get("save_file_folder") or "/config/www/snapshots/")
            always_latest = bool(self._opt.get("always_save_latest_file"))
            index_data, last_result = await self.hass.async_add_executor_job(
                _read_bootstrap_from_disk, folder, always_latest
            )
            self.hass.data.setdefault(DOMAIN, {})
            self.hass.data[DOMAIN]["index"] = index_data
            self.hass.data[DOMAIN]["last_result"] = last_result
            self.hass.data[DOMAIN].setdefault("faces_index", {"updated_at": None, "persons": {}})
        except Exception:
            pass



    async def async_refresh_faces_index(self) -> dict | None:
        """Refresh faces_index from Rekognition list_faces (NO scan path)."""
        if not self._collection_id:
            return None

        def _build() -> dict:
            persons: Dict[str, int] = {}

            kwargs: Dict[str, Any] = {
                "CollectionId": self._collection_id,
                "MaxResults": 4096,
            }

            while True:
                resp = self._rekognition.list_faces(**kwargs)

                for face in resp.get("Faces", []) or []:
                    name = (face.get("ExternalImageId") or "Unknown").strip() or "Unknown"
                    persons[name] = persons.get(name, 0) + 1

                token = resp.get("NextToken")
                if not token:
                    break
                kwargs["NextToken"] = token

            return {
                "updated_at": _utc_iso_now(),
                "persons": {k: {"count": v} for k, v in sorted(persons.items())},
            }

        try:
            faces_index = await self.hass.async_add_executor_job(_build)
        except Exception as e:
            # Non far saltare l'integrazione se AWS fallisce
            _LOGGER.warning("%s: refresh_faces_index failed: %s", DOMAIN, e)
            return None

        # ✅ Un SOLO punto di verità: publish aggiorna hass.data e notifica le card
        try:
            self.hass.loop.call_soon_threadsafe(publish_faces_update, self.hass, faces_index)
        except Exception:
            # fallback se già nel thread giusto
            try:
                publish_faces_update(self.hass, faces_index)
            except Exception:
                pass

        return faces_index

    async def async_process_camera_image(self, camera_entity: str, image_bytes: bytes) -> None:
        # do all heavy work in executor
        result: AFRProcessResult = await self.hass.async_add_executor_job(
            self._process_bytes_sync, camera_entity, image_bytes
        )

        # ✅ single push/event (no duplicates)
        # publish_update aggiorna hass.data + spara EVENT_UPDATED
        try:
            publish_update(
                self.hass,
                last_result=result.last_result,
                index_data=result.index_data,
            )
        except Exception:
            # fallback ultra-safe
            try:
                self.hass.loop.call_soon_threadsafe(
                    publish_update,
                    self.hass,
                    last_result=result.last_result,
                    index_data=result.index_data,
                )
            except Exception:
                pass



    # --------------------------
    # SYNC processing (executor)
    # --------------------------
    def _process_bytes_sync(self, camera_entity: str, image: bytes) -> AFRProcessResult:
        # usage counters (scan +1)
        self._usage_increment(scans_delta=1, aws_calls_delta=0)

        # reset per-frame
        self._faces = []
        self._person_labels = []
        self._confidence_details = {}
        self._person_found = False
        self._targets_found = []
        self._objects = []
        self._labels = []

        # 1) open + ROI
        try:
            img = Image.open(io.BytesIO(bytearray(image)))
            self._image = img
            self._image_width, self._image_height = img.size

            roi = {
                "x_min": float(self._opt.get("roi_x_min", 0.0)),
                "y_min": float(self._opt.get("roi_y_min", 0.0)),
                "x_max": float(self._opt.get("roi_x_max", 1.0)),
                "y_max": float(self._opt.get("roi_y_max", 1.0)),
            }
            roi_bytes, (_, _), roi_img = _apply_roi_and_get_bytes(self._image, roi)
            self._image = roi_img
            self._image_width, self._image_height = self._image.size
            image = roi_bytes
        except Exception as e:
            _LOGGER.error("ROI/open error: %s", e)
            return AFRProcessResult(
                last_result={},
                index_data=self.hass.data.get(DOMAIN, {}).get("index", {"updated_at": None, "items": []}),
            )

        # 2) scale
        scale = float(self._opt.get("scale", 1.0) or 1.0)
        if scale and scale != 1.0:
            try:
                newsize = (int(self._image_width * scale), int(self._image_height * scale))
                self._image.thumbnail(newsize, Image.LANCZOS)
                self._image_width, self._image_height = self._image.size
                with io.BytesIO() as out:
                    self._image.save(out, format="JPEG", quality=90)
                    image = out.getvalue()
            except Exception as e:
                _LOGGER.warning("Scale failed (ignored): %s", e)

        # 3) detect_labels (+1 AWS call)
        try:
            resp_labels = self._rekognition.detect_labels(Image={"Bytes": image})
            self._usage_increment(scans_delta=0, aws_calls_delta=1)
            self._objects, self._labels = get_objects(resp_labels)
        except botocore.exceptions.ClientError as e:
            _LOGGER.error("detect_labels error: %s", e)
            return AFRProcessResult(
                last_result={},
                index_data=self.hass.data.get(DOMAIN, {}).get("index", {"updated_at": None, "items": []}),
            )

        # 4) filter targets
        excluded_object_labels = {
            str(x).strip().lower()
            for x in (self._opt.get("excluded_object_labels") or EXCLUDED_OBJECT_LABELS)
            if str(x).strip()
        }
        exclude_targets = {str(x).strip().lower() for x in (self._opt.get("exclude_targets") or []) if str(x).strip()}
        default_min_conf = float(self._opt.get("default_min_confidence", 10.0))
        targets_confidence = {
            str(k).strip().lower(): float(v)
            for k, v in (self._opt.get("targets_confidence") or {}).items()
            if str(k).strip()
        }

        self._targets_found = []
        for obj in self._objects:
            name = str(obj.get("name", "")).strip().lower()
            conf = float(obj.get("confidence", 0.0))
            if not name:
                continue
            if name in exclude_targets:
                continue
            min_conf = float(targets_confidence.get(name, default_min_conf))
            if conf >= min_conf:
                self._targets_found.append(obj)

        persons = [o for o in self._targets_found if o.get("name") == "person"]
        self._person_found = len(persons) > 0

        # 5) detect_faces only if person (+1 AWS call)
        faces_detected = []
        if self._person_found:
            try:
                faces_resp = self._rekognition.detect_faces(Image={"Bytes": image}, Attributes=["DEFAULT"])
                self._usage_increment(scans_delta=0, aws_calls_delta=1)
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
            except Exception as e:
                _LOGGER.error("detect_faces error: %s", e)

        # 6) per-face search
        recognized_names_set = set()
        for face in faces_detected:
            match = None
            if self._collection_id:
                face_bytes = self._crop_face_bytes(face["bounding_box"])
                if face_bytes:
                    self._usage_increment(scans_delta=0, aws_calls_delta=1)
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

        # ✅ counts per "unknown_person_found"
        faces_detected_count = len(faces_detected)
        faces_unknown_count = sum(1 for f in (self._faces or []) if f.get("name") == "Unknown")

        # 7) associate person boxes with best face
        for p in persons:
            bb = p.get("bounding_box") or {}
            pb = {"x_min": bb.get("x_min"), "y_min": bb.get("y_min"), "x_max": bb.get("x_max"), "y_max": bb.get("y_max")}
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

        # 7b) persons WITHOUT recognized face inside (single source of truth)
        persons_without_recognized_face = []

        for p in persons:
            pb = p.get("bounding_box") or {}
            if not pb:
                continue

            has_recognized_face = False
            for f in (self._faces or []):
                if f.get("name") and f.get("name") != "Unknown":
                    fc = _center_of_box(f["bounding_box"])
                    if _point_in_box(pb, fc):
                        has_recognized_face = True
                        break

            if not has_recognized_face:
                persons_without_recognized_face.append(p)



        # 8) save annotated image + update index
        save_folder = Path(self._opt.get("save_file_folder") or "/config/www/snapshots/")
        save_format = (self._opt.get("save_file_format") or "jpg").lower()
        save_timestamped = bool(self._opt.get("save_timestamped_file"))
        always_latest = bool(self._opt.get("always_save_latest_file"))
        max_saved = int(self._opt.get("max_saved_files") or 10)

        show_boxes = bool(self._opt.get("show_boxes", True))

        # ✅ NEW: slider 1..20 -> internal scale
        font_level = int(self._opt.get(CONF_LABEL_FONT_LEVEL, DEFAULT_LABEL_FONT_LEVEL))
        label_font_scale = font_level_to_scale(font_level)

        max_red_boxes = int(self._opt.get("max_red_boxes") or 6)
        min_red_area = float(self._opt.get("min_red_box_area") or 0.03)

        saved_file = None
        objects_summary = self._get_object_summary_for_index(excluded_object_labels, exclude_targets, recognized_names_set)

        if show_boxes and self._image is not None:
            saved_file = self._save_image(
                directory=save_folder,
                recognized_names=sorted(recognized_names_set),
                objects_summary=objects_summary,
                save_format=save_format,
                save_timestamped=save_timestamped,
                always_latest=always_latest,
                max_saved=max_saved,
                label_font_scale=label_font_scale,
                max_red_boxes=max_red_boxes,
                min_red_area=min_red_area,
                persons_without_recognized_face=persons_without_recognized_face,  # ✅
            )
        else:
            try:
                save_folder.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

        # 9) last_result + index_data
        recognized_names = sorted(recognized_names_set)
        unknown_person_found = bool(persons_without_recognized_face) or (faces_unknown_count > 0)
        # 🚨 ALERT: only unknown persons detected
        alert = bool(persons_without_recognized_face) and not recognized_names




        ts_iso = _utc_iso_now()

        index_data = self.hass.data.get(DOMAIN, {}).get("index", {"updated_at": None, "items": []})
        if saved_file and save_timestamped:
            index_data = _update_recognition_index(
                directory=save_folder,
                filename=saved_file,
                timestamp_iso=ts_iso,
                recognized=recognized_names,
                unknown_person_found=unknown_person_found,
                keep=max_saved,
                objects=objects_summary,
            )

        base = _folder_to_local_base(save_folder)
        image_url = f"{base}/{saved_file}" if saved_file else None
        latest_url = f"{base}/recognition_latest.jpg" if always_latest else None

        last_result = {
            "id": Path(saved_file).stem if saved_file else None,
            "timestamp": ts_iso,
            "recognized": recognized_names,
            "unknown_person_found": unknown_person_found,
            "alert": alert,
            "file": saved_file,
            "image_url": image_url,
            "latest_url": latest_url,
            "objects": objects_summary or {},
            "camera_entity": camera_entity,
            # nice-to-have for UI/debug
            "font_level": font_level,
            "font_scale": label_font_scale,
        }

        return AFRProcessResult(last_result=last_result, index_data=index_data)

    # --------------------------
    # helpers
    # --------------------------
    def _usage_increment(self, scans_delta: int = 0, aws_calls_delta: int = 0) -> None:
        try:
            # Prefer persistent store if available
            store = self.hass.data.get(DOMAIN, {}).get("usage_store")
            if store:
                store.increment(scans_delta=scans_delta, aws_calls_delta=aws_calls_delta)
                return

            # fallback (RAM only)
            data = self.hass.data.setdefault(DOMAIN, {})
            usage = data.setdefault(
                "usage",
                {
                    "month": None,
                    "scans_month": 0,
                    "aws_calls_month": 0,
                    "last_month_scans": 0,
                    "last_month_api_calls": 0,  # <--- NUOVO
                },
            )

            cur = datetime.datetime.now().strftime("%Y-%m")
            if usage.get("month") != cur:
                usage["last_month_scans"] = int(usage.get("scans_month", 0))
                usage["last_month_api_calls"] = int(usage.get("aws_calls_month", 0))
                usage["scans_month"] = 0
                usage["aws_calls_month"] = 0
                usage["month"] = cur

            usage["scans_month"] = int(usage.get("scans_month", 0)) + int(scans_delta or 0)
            usage["aws_calls_month"] = int(usage.get("aws_calls_month", 0)) + int(aws_calls_delta or 0)
        except Exception:
            pass


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
            resp = self._rekognition.search_faces_by_image(
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

    def _get_object_summary_for_index(self, excluded_labels: set, exclude_targets: set, recognized_names_set: set) -> dict:
        recognized_names_l = {str(n).strip().lower() for n in (recognized_names_set or set())}
        counts = Counter([str(o.get("name", "")).lower() for o in (self._targets_found or [])])

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

    def _save_image(
        self,
        directory: Path,
        recognized_names: list[str],
        objects_summary: dict,
        save_format: str,
        save_timestamped: bool,
        always_latest: bool,
        max_saved: int,
        label_font_scale: float,
        max_red_boxes: int,
        min_red_area: float,
        persons_without_recognized_face: list,  # ✅
    ) -> Optional[str]:
        # --- ensure folder ---
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            _LOGGER.error("save_image: cannot ensure directory exists: %s", e)
            return None

        # --- base image ---
        try:
            img = self._image.convert("RGBA") if self._image else None
            if img is None:
                return None
        except UnidentifiedImageError:
            _LOGGER.warning("save_image: bad image data")
            return None
        except Exception as e:
            _LOGGER.error("save_image: cannot convert image: %s", e)
            return None

        # ------------------------------------------------------------
        # 1) YELLOW boxes = recognized faces
        # ------------------------------------------------------------
        identified_faces = []
        for f in (self._faces or []):
            name = f.get("name")
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
                text=str(name),
                color=YELLOW,
                font_scale=label_font_scale,
            )
            identified_faces.append(f)

        # ------------------------------------------------------------
        # 2) RED boxes = person objects with NO recognized face inside
        # ------------------------------------------------------------
        persons = [o for o in (self._targets_found or []) if o.get("name") == "person"]

        # Build a set of person-ids that contain at least one recognized face center
        persons_with_recognized_face = set()
        for f in identified_faces:
            fb = f.get("bounding_box")
            if not fb:
                continue
            fc = _center_of_box(fb)  # normalized center
            for p in persons:
                pb = p.get("bounding_box")
                if not pb:
                    continue
                if _point_in_box(pb, fc):
                    persons_with_recognized_face.add(id(p))

        # --- person confidence threshold (from config flow options) ---
        targets_conf = self._opt.get("targets_confidence") or {}
        default_min = float(self._opt.get("default_min_confidence", 10.0) or 10.0)
        try:
            person_min_conf = float(targets_conf.get("person", default_min))
        except Exception:
            person_min_conf = default_min

        # --- area threshold ---
        try:
            min_area = float(min_red_area or 0.0)
        except Exception:
            min_area = 0.0

        # Select candidates (area/conf), excluding those with recognized face
        
        # 2) RED boxes = persons WITHOUT recognized face
        red_candidates = []

        for p in persons_without_recognized_face:
            pb = p.get("bounding_box")
            if not pb:
                continue

            w = max(0.0, float(pb["x_max"]) - float(pb["x_min"]))
            h = max(0.0, float(pb["y_max"]) - float(pb["y_min"]))
            area = w * h

            conf = float(p.get("confidence", 0.0) or 0.0)

            if area < min_area:
                continue
            if conf < person_min_conf:
                continue

            red_candidates.append((area, conf, pb))


        # Draw up to max_red_boxes
        try:
            limit = max(0, int(max_red_boxes))
        except Exception:
            limit = 0

        for _, __, pb in red_candidates[:limit]:
            img = draw_box_scaled(
                img,
                (pb["y_min"], pb["x_min"], pb["y_max"], pb["x_max"]),
                img.width,
                img.height,
                text="person",
                color=RED,
                font_scale=label_font_scale,
            )

        # ------------------------------------------------------------
        # 3) Save file
        # ------------------------------------------------------------
        ext = (save_format or "jpg").lower()
        if ext not in ("jpg", "png"):
            ext = "jpg"

        if save_timestamped:
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recognition_{stamp}.{ext}"
        else:
            filename = f"recognition.{ext}"

        save_path = directory / filename

        try:
            if ext == "jpg":
                img.convert("RGB").save(save_path, format="JPEG", quality=85, subsampling=2)
            else:
                img.save(save_path, format="PNG", optimize=True)
        except Exception as e:
            _LOGGER.error("save_image: error saving %s: %s", save_path, e)
            return None

        # latest
        if always_latest:
            try:
                img.convert("RGB").save(directory / "recognition_latest.jpg", format="JPEG", quality=85, subsampling=2)
            except Exception as e:
                _LOGGER.warning("save_image: cannot write latest file: %s", e)

        # cleanup timestamped
        _cleanup_old_recognition_files(directory, keep=max_saved, prefix="recognition_")

        return save_path.name
