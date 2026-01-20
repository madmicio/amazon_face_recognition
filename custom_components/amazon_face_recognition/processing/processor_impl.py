# custom_components/amazon_face_recognition/processor.py
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import datetime
import io
import json
import logging
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple
import re

import botocore
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

from homeassistant.core import HomeAssistant

from ..const import (
    DOMAIN,
    FONT_PATH,
    RED,
    FUCHSIA,
    YELLOW,
    EXCLUDED_OBJECT_LABELS,
    CONF_LABEL_FONT_LEVEL,
    DEFAULT_LABEL_FONT_LEVEL,
    CONF_VEHICLE_AREA_ABS_MIN,
    CONF_MAX_VEHICLES_TO_SCAN,
    DEFAULT_VEHICLE_AREA_ABS_MIN,
    DEFAULT_MAX_VEHICLES_TO_SCAN,
    AFR_SCAN_DIRNAME,
    CONF_S3_BUCKET,
    CONF_CLOUD_GALLERY_ENABLED,
    CONF_CLOUD_GALLERY_PREFIX,
    CONF_CLOUD_GALLERY_SYNC_ON_STARTUP,
    CONF_CLOUD_SCAN_UPLOAD_ENABLED,

)

from ..core.options import merge_defaults

from ..api.websocket_impl import publish_faces_update, publish_update

_LOGGER = logging.getLogger(__name__)


def _log_aws_response(prefix: str, resp: dict, max_chars: int = 8000) -> None:
    """Logga la response AWS in JSON (DEBUG), limitando dimensione e rimuovendo campi pesanti."""
    if not _LOGGER.isEnabledFor(logging.DEBUG):
        return
    try:
        safe = dict(resp or {})

        if "Image" in safe:
            safe["Image"] = "<omitted>"
        if "ResponseMetadata" in safe:
            # spesso utile ma verboso; se lo vuoi, commenta questa riga
            pass

        s = json.dumps(safe, indent=2, default=str)
        if max_chars and len(s) > max_chars:
            s = s[:max_chars] + "\n...<truncated>..."
        _LOGGER.debug("%s\n%s", prefix, s)
    except Exception as e:
        _LOGGER.debug("%s (cannot dump aws resp: %s)", prefix, e)


# -----------------------------
# Small helpers
# -----------------------------

# caratteri consentiti (togli spazi e separatori)
_CLEAN_RE = re.compile(r"[^A-Z0-9]")

# semplice regex: 5..10 alfanumerici (worldwide-ish)
_PLATE_RE = re.compile(r"^[A-Z0-9]{5,10}$")

# stopword super-base per evitare parole “ovvie”
_STOP = {"SALE", "AUTO", "CAR", "MOTOR", "SERVICE", "TEST", "CHEERS"}


def _normalize_plate(s: str) -> str:
    s = (s or "").upper()
    s = _CLEAN_RE.sub("", s)
    return s


def _score_plate_candidate(s: str, conf: float, geom: dict | None) -> float:
    """
    Scoring worldwide:
    - lunghezza ragionevole
    - mix lettere/numeri (preferito, ma non obbligatorio)
    - confidenza AWS
    - preferisci box largo e basso (targhe spesso orizzontali, in basso)
    """
    t = _normalize_plate(s)
    if not t:
        return -1.0
    if t in _STOP:
        return -1.0

    L = len(t)
    if L < 4 or L > 12:
        return -1.0

    has_a = any("A" <= c <= "Z" for c in t)
    has_d = any("0" <= c <= "9" for c in t)

    score = float(conf or 0.0)

    if has_a and has_d:
        score += 30
    elif has_d:
        score += 10
    else:
        score -= 20

    if 6 <= L <= 8:
        score += 15
    elif 5 <= L <= 10:
        score += 8

    if geom and "BoundingBox" in geom:
        bb = geom["BoundingBox"]
        w = float(bb.get("Width", 0.0))
        h = float(bb.get("Height", 0.0))
        top = float(bb.get("Top", 0.0))

        if h > 0 and w / h > 2.2:
            score += 10
        if top > 0.45:
            score += 6

    return score


def _pick_best_plate_from_detect_text(resp: dict, min_conf: float = 70.0):
    """
    Ritorna SEMPRE 3 valori:
      (best_plate: str|None, best_conf: float, best_geom: dict|None)
    """
    best_plate: str | None = None
    best_conf: float = 0.0
    best_geom: dict | None = None

    for det in (resp.get("TextDetections") or []):
        if det.get("Type") != "LINE":
            continue

        conf = float(det.get("Confidence", 0.0) or 0.0)
        if conf < float(min_conf or 0.0):
            continue

        raw = det.get("DetectedText", "") or ""
        txt = _normalize_plate(raw)

        if not txt:
            continue
        if txt in _STOP:
            continue
        if not _PLATE_RE.match(txt):
            continue

        geom = det.get("Geometry")  # può essere None

        if conf > best_conf:
            best_plate = txt
            best_conf = conf
            best_geom = geom

    return best_plate, float(best_conf), best_geom


def _crop_by_geometry(img: Image.Image, geom: dict, pad: float = 0.25) -> bytes:
    """
    geom è Geometry di detect_text. Ritaglia area testo con padding.
    """
    base = img.convert("RGB") if img.mode != "RGB" else img

    w, h = base.size
    bb = (geom or {}).get("BoundingBox") or {}
    x = float(bb.get("Left", 0.0))
    y = float(bb.get("Top", 0.0))
    bw = float(bb.get("Width", 0.0))
    bh = float(bb.get("Height", 0.0))

    px = bw * pad
    py = bh * pad

    x1 = _clamp(x - px)
    y1 = _clamp(y - py)
    x2 = _clamp(x + bw + px)
    y2 = _clamp(y + bh + py)

    left = int(x1 * w)
    top = int(y1 * h)
    right = int(x2 * w)
    bottom = int(y2 * h)

    left = max(0, min(w - 1, left))
    top = max(0, min(h - 1, top))
    right = max(1, min(w, right))
    bottom = max(1, min(h, bottom))

    crop = base.crop((left, top, right, bottom))

    # upscale per OCR
    cw, ch = crop.size
    min_w = 900
    if cw < min_w:
        scale = min_w / max(1, cw)
        crop = crop.resize((int(cw * scale), int(ch * scale)), Image.LANCZOS)

    with io.BytesIO() as out:
        crop.save(out, format="JPEG", quality=95)
        return out.getvalue()


def _crop_vehicle_for_plate(img: Image.Image, vehicle_box: dict) -> bytes:
    """
    Crop robusto e 'worldwide': prende la parte bassa del veicolo,
    dove statisticamente sta la targa (front/back).
    """
    base = img.convert("RGB") if img.mode != "RGB" else img
    w, h = base.size

    left = int(float(vehicle_box["x_min"]) * w)
    top = int(float(vehicle_box["y_min"]) * h)
    right = int(float(vehicle_box["x_max"]) * w)
    bottom = int(float(vehicle_box["y_max"]) * h)

    left = max(0, min(w - 1, left))
    top = max(0, min(h - 1, top))
    right = max(1, min(w, right))
    bottom = max(1, min(h, bottom))

    vw = right - left
    vh = bottom - top
    if vw < 10 or vh < 10:
        crop = base
    else:
        roi_top = top + int(vh * 0.45)
        roi_bottom = bottom
        roi_left = max(0, left - int(vw * 0.05))
        roi_right = min(w, right + int(vw * 0.05))
        crop = base.crop((roi_left, roi_top, roi_right, roi_bottom))

    cw, ch = crop.size
    min_side = 700
    if max(cw, ch) < min_side:
        scale = min_side / max(cw, ch)
        crop = crop.resize((int(cw * scale), int(ch * scale)), Image.LANCZOS)

    with io.BytesIO() as out:
        crop.save(out, format="JPEG", quality=95)
        return out.getvalue()


def with_alpha(color, opacity: float):
    r, g, b = color
    a = int(255 * max(0.0, min(1.0, opacity)))
    return (r, g, b, a)


def _utc_iso_now() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


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


# --------------------------
# Cloud Gallery helpers (S3)
# --------------------------

def _s3_upload_file_sync(s3_client, bucket: str, key: str, path: Path) -> None:
    """Upload a local file to S3 (best-effort, sync)."""
    try:
        if not path.exists():
            return
        # ExtraArgs helps HA / browsers infer the correct content type when served elsewhere.
        extra = {}
        name = path.name.lower()
        if name.endswith(".jpg") or name.endswith(".jpeg"):
            extra["ContentType"] = "image/jpeg"
        elif name.endswith(".png"):
            extra["ContentType"] = "image/png"
        elif name.endswith(".json"):
            extra["ContentType"] = "application/json"
        if extra:
            s3_client.upload_file(str(path), bucket, key, ExtraArgs=extra)
        else:
            s3_client.upload_file(str(path), bucket, key)
    except Exception as e:
        _LOGGER.debug("%s: s3 upload failed (%s): %s", DOMAIN, key, e)


def _s3_download_file_sync(s3_client, bucket: str, key: str, dest: Path) -> bool:
    """Download a file from S3 to dest (best-effort, sync). Returns True if downloaded."""
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        s3_client.download_file(bucket, key, str(dest))
        return True
    except Exception:
        return False


def _s3_sync_down_sync(s3_client, bucket: str, prefix: str, directory: Path, limit: int) -> None:
    """Sync down remote index + referenced images into local directory."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
        index_key = f"{prefix}/recognition_index.json"
        index_path = directory / "recognition_index.json"

        # Download index.json if present
        got_index = _s3_download_file_sync(s3_client, bucket, index_key, index_path)
        if not got_index:
            return

        data = _load_json_index(index_path)
        items = data.get("items") or []
        if not isinstance(items, list):
            return

        # Download missing images referenced by the index
        count = 0
        for it in items:
            if count >= limit:
                break
            if not isinstance(it, dict):
                continue
            fn = it.get("file")
            if not fn or not isinstance(fn, str):
                continue
            dest = directory / fn
            if dest.exists():
                continue
            if _s3_download_file_sync(s3_client, bucket, f"{prefix}/{fn}", dest):
                count += 1

        # Try to download latest image too (optional)
        latest_dest = directory / "recognition_latest.jpg"
        if not latest_dest.exists():
            _s3_download_file_sync(s3_client, bucket, f"{prefix}/recognition_latest.jpg", latest_dest)
    except Exception as e:
        _LOGGER.debug("%s: s3 sync-down failed: %s", DOMAIN, e)


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
            "plates": latest.get("plates") or [],
            "camera_entity": latest.get("camera_entity"),
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
                p
                for p in directory.glob(f"{prefix}*")
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


def _box_area(pb: dict) -> float:
    """Area in coordinate normalizzate 0..1."""
    return max(0.0, float(pb["x_max"]) - float(pb["x_min"])) * max(
        0.0, float(pb["y_max"]) - float(pb["y_min"])
    )


def _center_of_box(bb: dict) -> tuple[float, float]:
    """Center in coordinate normalizzate 0..1."""
    cx = (float(bb["x_min"]) + float(bb["x_max"])) / 2.0
    cy = (float(bb["y_min"]) + float(bb["y_max"])) / 2.0
    return cx, cy


def _point_in_box(pb: dict, pt: tuple[float, float]) -> bool:
    x, y = pt
    return (
        float(pb["x_min"]) <= x <= float(pb["x_max"])
        and float(pb["y_min"]) <= y <= float(pb["y_max"])
    )


def map_recognized_faces_to_person_ids(persons: list[dict], faces: list[dict]) -> set[int]:
    """
    Ritorna un set di id(person_dict) che consideriamo 'riconosciuti'.

    Regola robusta:
    - per ogni volto riconosciuto, trova tutte le PERSON che contengono il centro del volto
    - scegli la PERSON col box PIÙ PICCOLO (più tight) -> riduce falsi match
    """
    recognized_person_ids: set[int] = set()

    for f in (faces or []):
        name = f.get("name")
        if not name or name == "Unknown":
            continue
        fb = f.get("bounding_box")
        if not fb:
            continue

        fc = _center_of_box(fb)

        candidates: list[tuple[float, dict]] = []
        for p in persons:
            pb = p.get("bounding_box")
            if not pb:
                continue
            if _point_in_box(pb, fc):
                candidates.append((_box_area(pb), p))

        if candidates:
            candidates.sort(key=lambda t: t[0])  # box più piccolo
            recognized_person_ids.add(id(candidates[0][1]))

    return recognized_person_ids


def _update_recognition_index(
    directory: Path,
    filename: str,
    timestamp_iso: str,
    recognized: list,
    unknown_person_found: bool,
    keep: int,
    objects: Optional[Dict[str, Any]] = None,
    plates: Optional[list] = None,
    camera_entity: Optional[str] = None,
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
        "plates": plates or [],
        "camera_entity": camera_entity,
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


def _expand_box(box: dict, pad: float = 0.06) -> dict:
    w = float(box["x_max"]) - float(box["x_min"])
    h = float(box["y_max"]) - float(box["y_min"])
    dx = w * pad
    dy = h * pad
    return {
        "x_min": _clamp(float(box["x_min"]) - dx),
        "y_min": _clamp(float(box["y_min"]) - dy),
        "x_max": _clamp(float(box["x_max"]) + dx),
        "y_max": _clamp(float(box["y_max"]) + dy),
    }


def _norm_to_pixels(box: dict, img_w: int, img_h: int):
    left = int(float(box["x_min"]) * img_w)
    top = int(float(box["y_min"]) * img_h)
    right = int(float(box["x_max"]) * img_w)
    bottom = int(float(box["y_max"]) * img_h)

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


@lru_cache(maxsize=64)
def _load_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load and cache fonts by size.

    This function is called for every drawn label; caching avoids repeated
    filesystem access and font parsing.
    """
    try:
        # truetype is preferred (better glyph coverage and size scaling)
        return ImageFont.truetype(str(FONT_PATH), int(font_size))
    except Exception as e:
        # Avoid spamming logs if the font is missing on the target system.
        # Log only once per distinct exception message.
        key = f"{type(e).__name__}:{e}"
        if not getattr(_load_font, "_warned", set()).__contains__(key):
            _load_font._warned = getattr(_load_font, "_warned", set()) | {key}  # type: ignore[attr-defined]
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
    label_opacity: float = 0.7,
    font_scale: float = 0.02,
    occupied_labels: list[tuple[int, int, int, int]] | None = None,
):
    """
    Draw a bounding box + label.

    Anti-collisione label (pulita):
    - prova SOPRA
    - se collide -> prova SOTTO
    - se collide -> prova DENTRO
    Stop. Niente label che "volano" lontano.
    """
    if occupied_labels is None:
        occupied_labels = []

    def _intersects(a, b) -> bool:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        return not (ax2 <= bx1 or bx2 <= ax1 or ay2 <= by1 or by2 <= ay1)

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

    def _label_rect_for(tx: int, ty: int) -> tuple[int, int, int, int]:
        bg_left = max(0, int(tx - pad))
        bg_top = max(0, int(ty - pad))
        bg_right = min(img_w, int(tx + max_w + pad))
        bg_bottom = min(img_h, int(ty + total_h + pad))
        return (bg_left, bg_top, bg_right, bg_bottom)

    candidates = [
        (left, top - (total_h + 2 * pad)),  # sopra
        (left, bottom + pad),               # sotto
        (left, top + pad),                  # dentro
    ]

    chosen_x, chosen_y = candidates[-1]
    chosen_rect = _label_rect_for(chosen_x, chosen_y)

    for tx, ty in candidates:
        tx = max(0, min(img_w - (max_w + pad), tx))
        ty = max(0, min(img_h - (total_h + pad), ty))
        rect = _label_rect_for(tx, ty)

        if rect[2] <= rect[0] or rect[3] <= rect[1]:
            continue
        if any(_intersects(rect, r) for r in occupied_labels):
            continue

        chosen_x, chosen_y, chosen_rect = tx, ty, rect
        break

    bg_rgba = with_alpha((0, 0, 0), label_opacity)
    # odraw.rectangle(list(chosen_rect), fill=bg_rgba)
    # raggio proporzionale al font (tweak a piacere)
    radius = max(3, int(font_size * 0.35))

    try:
        odraw.rounded_rectangle(list(chosen_rect), radius=radius, fill=bg_rgba)
    except Exception:
        # fallback nel caso la tua versione Pillow non supporti rounded_rectangle
        odraw.rectangle(list(chosen_rect), fill=bg_rgba)

    y = chosen_y
    for (line, (_w, h)) in zip(lines, line_sizes):
        odraw.text((chosen_x, y), line, font=font, fill=(255, 255, 255, 255))
        y += h + line_gap

    occupied_labels.append(chosen_rect)

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
        # Merge defaults so initial behavior matches UI defaults even if entry.options is empty.
        self._opt = merge_defaults(options or {})

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

        # Optional Cloud Gallery (S3)
        self._s3_client = None
        self._s3_bucket: Optional[str] = None
        self._s3_prefix: str = AFR_SCAN_DIRNAME

    def set_cloud_gallery(self, s3_client, bucket: str, prefix: str | None = None) -> None:
        """Enable Cloud Gallery uploads for this processor."""
        self._s3_client = s3_client
        self._s3_bucket = (bucket or "").strip() or None
        self._s3_prefix = (prefix or AFR_SCAN_DIRNAME).strip("/") or AFR_SCAN_DIRNAME

    def _scan_dir(self) -> Path:
        """Return fixed scan directory under /config/www and ensure it exists."""
        p = Path(self.hass.config.path("www", AFR_SCAN_DIRNAME))
        p.mkdir(parents=True, exist_ok=True)
        return p


    def update_options(self, options: dict) -> None:
        # Keep options resilient across upgrades.
        # ROI is now configured only via entry.options['roi_by_camera'] (panel/websocket).
        opt = merge_defaults(dict(options or {}))
        for k in ("roi_x_min", "roi_y_min", "roi_x_max", "roi_y_max"):
            opt.pop(k, None)
        self._opt = opt

    async def async_bootstrap(self) -> None:
        try:
            folder = folder = self._scan_dir()
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

    async def async_cloud_gallery_sync(self, s3_client, bucket: str, prefix: str | None = None) -> None:
        """Best-effort sync from S3 Cloud Gallery into the local www folder.

        This enables rebuilding the local gallery after HA migration (no backup).
        It downloads the remote recognition_index.json and any missing images referenced
        by the index, up to the configured max_saved_files.
        """
        prefix = (prefix or AFR_SCAN_DIRNAME).strip("/")
        bucket = (bucket or "").strip()
        if not bucket:
            return

        directory = self._scan_dir()
        max_files = int(self._opt.get("max_saved_files") or 10)
        # Avoid huge downloads on startup: cap to a reasonable number.
        limit = max(1, min(max_files, 200))

        await self.hass.async_add_executor_job(
            _s3_sync_down_sync,
            s3_client,
            bucket,
            prefix,
            directory,
            limit,
        )

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
            _LOGGER.warning("%s: refresh_faces_index failed: %s", DOMAIN, e)
            return None

        try:
            self.hass.loop.call_soon_threadsafe(publish_faces_update, self.hass, faces_index)
        except Exception:
            try:
                publish_faces_update(self.hass, faces_index)
            except Exception:
                pass

        return faces_index

    async def async_process_camera_image(self, camera_entity: str, image_bytes: bytes) -> None:
        result: AFRProcessResult = await self.hass.async_add_executor_job(
            self._process_bytes_sync, camera_entity, image_bytes
        )

        try:
            publish_update(
                self.hass,
                last_result=result.last_result,
                index_data=result.index_data,
            )
        except Exception:
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

        # 1) open + ROI (per-camera, configured via panel -> entry.options['roi_by_camera'])
        # IMPORTANT behavior:
        # - Rekognition runs ONLY on the ROI-cropped image (to reduce costs and false positives).
        # - The saved/annotated snapshot remains the FULL frame.
        #   Therefore every bounding box returned by AWS (relative to the ROI crop)
        #   is re-mapped back onto the full-frame normalized coordinates.
        try:
            full_img = Image.open(io.BytesIO(bytearray(image)))
            self._image = full_img
            full_w, full_h = full_img.size
            self._image_width, self._image_height = full_w, full_h

            # Compute a single bounding ROI that contains all configured ROIs for this camera.
            # If none configured, keep full frame.
            roi_by_camera = self._opt.get("roi_by_camera")
            rois = []
            if isinstance(roi_by_camera, dict):
                rois = roi_by_camera.get(camera_entity) or []
            if not isinstance(rois, list):
                rois = []

            x_min, y_min, x_max, y_max = 0.0, 0.0, 1.0, 1.0
            xs: list[float] = []
            ys: list[float] = []
            x2s: list[float] = []
            y2s: list[float] = []
            for r in rois:
                if not isinstance(r, dict):
                    continue
                try:
                    x = float(r.get("x", 0.0))
                    y = float(r.get("y", 0.0))
                    w = float(r.get("w", 0.0))
                    h = float(r.get("h", 0.0))
                except Exception:
                    continue
                if w <= 0.001 or h <= 0.001:
                    continue
                xs.append(max(0.0, min(1.0, x)))
                ys.append(max(0.0, min(1.0, y)))
                x2s.append(max(0.0, min(1.0, x + w)))
                y2s.append(max(0.0, min(1.0, y + h)))

            if xs and ys and x2s and y2s:
                x_min = max(0.0, min(1.0, min(xs)))
                y_min = max(0.0, min(1.0, min(ys)))
                x_max = max(0.0, min(1.0, max(x2s)))
                y_max = max(0.0, min(1.0, max(y2s)))

                # Guard against inverted/degenerate ROI
                if x_max - x_min < 0.001 or y_max - y_min < 0.001:
                    x_min, y_min, x_max, y_max = 0.0, 0.0, 1.0, 1.0

            roi = {"x_min": x_min, "y_min": y_min, "x_max": x_max, "y_max": y_max}

            # Work image for AWS (ROI crop). Keep FULL frame for output.
            roi_bytes, (roi_left_px, roi_top_px), roi_img = _apply_roi_and_get_bytes(full_img, roi)
            roi_w_px, roi_h_px = roi_img.size
            image = roi_bytes

            # Store mapping context for this frame (work->full). Used to remap ALL AWS bounding boxes.
            self._roi_ctx = {
                "roi_left_px": int(roi_left_px),
                "roi_top_px": int(roi_top_px),
                "roi_w_px": int(roi_w_px),
                "roi_h_px": int(roi_h_px),
                "full_w": int(full_w),
                "full_h": int(full_h),
            }

            def _map_box_work_to_full(bb: dict) -> dict:
                """Map a normalized bounding box from ROI-work image to full-frame normalized coords."""
                try:
                    rx = float(self._roi_ctx.get("roi_left_px", 0))
                    ry = float(self._roi_ctx.get("roi_top_px", 0))
                    rw = float(self._roi_ctx.get("roi_w_px", full_w))
                    rh = float(self._roi_ctx.get("roi_h_px", full_h))
                    fw = float(self._roi_ctx.get("full_w", full_w))
                    fh = float(self._roi_ctx.get("full_h", full_h))

                    x_min_w = float(bb.get("x_min", 0.0))
                    y_min_w = float(bb.get("y_min", 0.0))
                    x_max_w = float(bb.get("x_max", 1.0))
                    y_max_w = float(bb.get("y_max", 1.0))

                    x_min_f = _clamp((rx + x_min_w * rw) / fw)
                    y_min_f = _clamp((ry + y_min_w * rh) / fh)
                    x_max_f = _clamp((rx + x_max_w * rw) / fw)
                    y_max_f = _clamp((ry + y_max_w * rh) / fh)

                    # Guard degenerate mapping
                    if x_max_f <= x_min_f:
                        x_max_f = _clamp(x_min_f + 0.001)
                    if y_max_f <= y_min_f:
                        y_max_f = _clamp(y_min_f + 0.001)

                    return {
                        "x_min": x_min_f,
                        "y_min": y_min_f,
                        "x_max": x_max_f,
                        "y_max": y_max_f,
                        "width": _clamp(x_max_f - x_min_f),
                        "height": _clamp(y_max_f - y_min_f),
                    }
                except Exception:
                    return bb

            self._map_box_work_to_full = _map_box_work_to_full
        except Exception as e:
            _LOGGER.error("ROI/open error: %s", e)
            return AFRProcessResult(
                last_result={},
                index_data=self.hass.data.get(DOMAIN, {}).get("index", {"updated_at": None, "items": []}),
            )

        # 2) scale (analysis only)
        # NOTE: scaling now affects ONLY the ROI-work image sent to AWS.
        # The saved snapshot remains full resolution.
        scale = float(self._opt.get("scale", 1.0) or 1.0)
        if scale and scale != 1.0:
            try:
                # Re-open ROI-work bytes to scale deterministically
                roi_work = Image.open(io.BytesIO(bytearray(image))).convert("RGB")
                rw, rh = roi_work.size
                newsize = (max(1, int(rw * scale)), max(1, int(rh * scale)))
                roi_work = roi_work.resize(newsize, Image.LANCZOS)
                with io.BytesIO() as out:
                    roi_work.save(out, format="JPEG", quality=90)
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

        # Re-map ALL object bounding boxes from ROI-work coordinates back to full-frame coordinates.
        mapper = getattr(self, "_map_box_work_to_full", None)
        if callable(mapper):
            for obj in (self._objects or []):
                bb = obj.get("bounding_box")
                if isinstance(bb, dict) and bb:
                    bb2 = mapper(bb)
                    obj["bounding_box"] = bb2
                    # refresh centroid (used for UX/debug)
                    try:
                        obj["centroid"] = {
                            "x": round((float(bb2["x_min"]) + float(bb2["x_max"])) / 2.0, 4),
                            "y": round((float(bb2["y_min"]) + float(bb2["y_max"])) / 2.0, 4),
                        }
                    except Exception:
                        pass

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

        # 4b) --- vehicle scan gate ---
        scan_cars = bool(self._opt.get("scan_cars", False))
        detected_plates: list[dict] = []
        vehicle_overlays: list[dict] = []


        if scan_cars and self._image is not None:
            _LOGGER.warning("SCAN_CARS: ENABLED")

            vehicle_labels = {
                str(x).strip().lower()
                for x in (self._opt.get("vehicle_labels") or ["car", "vehicle", "truck", "bus", "motorcycle"])
            }

            vehicle_min_conf = float(self._opt.get("vehicle_min_confidence", 70.0) or 70.0)
            plate_min_conf = float(self._opt.get("plate_min_confidence", 70.0) or 70.0)

            _LOGGER.warning(
                "SCAN_CARS: vehicle_labels=%s vehicle_min_conf=%.1f plate_min_conf=%.1f",
                vehicle_labels,
                vehicle_min_conf,
                plate_min_conf,
            )

            vehicles = [
                o for o in self._targets_found
                if str(o.get("name", "")).lower() in vehicle_labels
            ]

            def _plate_owner(plate: str) -> str | None:
                try:
                    items = (self.hass.data.get(DOMAIN, {}).get("plates", {}) or {}).get("items", {}) or {}
                    v = items.get(plate)
                    if isinstance(v, str):
                        v = v.strip()
                        return v or None
                    if isinstance(v, dict):
                        n = (v.get("name") or v.get("owner") or v.get("person") or "").strip()
                        return n or None
                except Exception:
                    pass
                return None


            def _veh_key(v: dict):
                bb = v.get("bounding_box") or {}
                area = (float(bb.get("x_max", 0)) - float(bb.get("x_min", 0))) * (
                    float(bb.get("y_max", 0)) - float(bb.get("y_min", 0))
                )
                return (area, float(v.get("confidence", 0.0) or 0.0))

            vehicles_sorted = sorted(vehicles, key=_veh_key, reverse=True)

            # --- ABS area filter + top-N largest vehicles (conf -> area -> topN) ---
            vehicle_area_abs_min = float(
                self._opt.get(CONF_VEHICLE_AREA_ABS_MIN, DEFAULT_VEHICLE_AREA_ABS_MIN) or DEFAULT_VEHICLE_AREA_ABS_MIN
            )
            max_vehicles_to_scan = int(
                self._opt.get(CONF_MAX_VEHICLES_TO_SCAN, DEFAULT_MAX_VEHICLES_TO_SCAN) or DEFAULT_MAX_VEHICLES_TO_SCAN
            )

            def _veh_area(v: dict) -> float:
                bb = v.get("bounding_box") or {}
                return max(0.0, float(bb.get("x_max", 0.0)) - float(bb.get("x_min", 0.0))) * max(
                    0.0, float(bb.get("y_max", 0.0)) - float(bb.get("y_min", 0.0))
                )

            before_n = len(vehicles_sorted)

            # 1) filter by confidence first
            vehicles_sorted = [v for v in vehicles_sorted if float(v.get("confidence", 0.0) or 0.0) >= vehicle_min_conf]
            after_conf_n = len(vehicles_sorted)

            # 2) filter by absolute area
            vehicles_sorted = [v for v in vehicles_sorted if _veh_area(v) >= vehicle_area_abs_min]
            after_area_n = len(vehicles_sorted)

            # 3) take top-N largest (already sorted by your _veh_key)
            if max_vehicles_to_scan > 0:
                vehicles_sorted = vehicles_sorted[:max_vehicles_to_scan]

            _LOGGER.warning(
                "SCAN_CARS: conf_min=%.1f kept=%d/%d | area_abs_min=%.4f kept=%d | topN=%d => final=%d",
                vehicle_min_conf,
                after_conf_n,
                before_n,
                vehicle_area_abs_min,
                after_area_n,
                max_vehicles_to_scan,
                len(vehicles_sorted),
            )


            for idx, v in enumerate(vehicles_sorted):
                vconf = float(v.get("confidence", 0.0) or 0.0)
                if vconf < vehicle_min_conf:
                    _LOGGER.warning("SCAN_CARS: #%d skip vconf=%.1f < %.1f", idx, vconf, vehicle_min_conf)
                    continue

                label_text = "vehicle"
                plate_value = None
                plate_owner = None

                vb = v.get("bounding_box")
                if not vb:
                    _LOGGER.warning("SCAN_CARS: #%d skip no bounding_box", idx)
                    continue

                area = (float(vb.get("x_max", 0)) - float(vb.get("x_min", 0))) * (
                    float(vb.get("y_max", 0)) - float(vb.get("y_min", 0))
                )
                _LOGGER.warning(
                    "SCAN_CARS: #%d vehicle=%s vconf=%.1f area=%.4f box=%s",
                    idx, v.get("name"), vconf, area, vb
                )

                crop_bytes = _crop_vehicle_for_plate(self._image, vb)
                _LOGGER.warning("SCAN_CARS: #%d crop_bytes=%d", idx, len(crop_bytes or b""))

                if not crop_bytes:
                    _LOGGER.warning("SCAN_CARS: #%d skip empty crop", idx)
                    continue

                # +1 AWS call (detect_text)
                self._usage_increment(scans_delta=0, aws_calls_delta=1)
                _LOGGER.warning("SCAN_CARS: #%d running detect_text", idx)
                txt_resp = self._detect_text_on_image(crop_bytes)

                if not txt_resp:
                    _LOGGER.warning("SCAN_CARS: #%d detect_text returned None", idx)
                    continue

                detections = txt_resp.get("TextDetections") or []
                _LOGGER.warning("SCAN_CARS: #%d detect_text detections=%d", idx, len(detections))

                plate, pconf, geom = _pick_best_plate_from_detect_text(txt_resp, min_conf=plate_min_conf)

                # refine: se ho geometry, crop stretto sulla targa e rilancio detect_text
                if plate and geom:
                    try:
                        crop_img = Image.open(io.BytesIO(crop_bytes)).convert("RGB")
                        refine_bytes = _crop_by_geometry(crop_img, geom, pad=0.35)

                        self._usage_increment(scans_delta=0, aws_calls_delta=1)
                        txt2 = self._detect_text_on_image(refine_bytes)
                        if txt2:
                            plate2, pconf2, _ = _pick_best_plate_from_detect_text(txt2, min_conf=plate_min_conf)
                            if plate2 and (len(plate2) >= len(plate)):
                                plate, pconf = plate2, pconf2
                    except Exception:
                        pass
                if plate:
                    plate_value = plate

                    # lookup nome associato alla targa
                    items = (self.hass.data.get(DOMAIN, {}).get("plates", {}) or {}).get("items", {}) or {}
                    plate_entry = items.get(plate)   # <-- NON usare 'v' qui

                    if isinstance(plate_entry, str):
                        plate_owner = plate_entry.strip() or None
                    elif isinstance(plate_entry, dict):
                        plate_owner = (plate_entry.get("name") or plate_entry.get("owner") or "").strip() or None

                    label_text = plate_owner or plate
                else:
                    label_text = "vehicle"



                # ✅ un solo log finale (niente duplicati "finti")
                _LOGGER.warning("SCAN_CARS: #%d plate_candidate=%s conf=%.1f", idx, plate, float(pconf or 0.0))

                if plate:
                    detected_plates.append(
                        {
                            "plate": plate,
                            "confidence": round(float(pconf), 2),
                            "owner": plate_owner, 
                            "vehicle_label": str(v.get("name")),
                            "vehicle_confidence": round(float(vconf), 2),
                        }
                    )
                
                vehicle_overlays.append(
                    {
                        "bounding_box": vb,
                        "text": label_text,
                        "vehicle_label": str(v.get("name") or "vehicle"),
                        "vehicle_confidence": round(float(vconf), 2),
                        "plate": plate_value,
                        "owner": plate_owner,
                    }
                )


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

                # Re-map face boxes from ROI-work coords -> full-frame coords
                mapper = getattr(self, "_map_box_work_to_full", None)
                if callable(mapper):
                    for f in faces_detected:
                        bb = f.get("bounding_box")
                        if isinstance(bb, dict) and bb:
                            f["bounding_box"] = mapper(bb)
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

        # 7b) persons WITHOUT recognized face inside
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
        save_folder = folder = self._scan_dir()
        save_format = (self._opt.get("save_file_format") or "jpg").lower()
        save_timestamped = bool(self._opt.get("save_timestamped_file"))
        always_latest = bool(self._opt.get("always_save_latest_file"))
        max_saved = int(self._opt.get("max_saved_files") or 10)

        show_boxes = bool(self._opt.get("show_boxes", True))

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
                persons_without_recognized_face=persons_without_recognized_face,
                vehicle_overlays=vehicle_overlays if scan_cars else None,
            )
        else:
            try:
                save_folder.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

        # 9) last_result + index_data
        recognized_names = sorted(recognized_names_set)
        unknown_person_found = bool(persons_without_recognized_face) or (faces_unknown_count > 0)
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
                plates=detected_plates if scan_cars else None,
                camera_entity=camera_entity,
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
            "font_level": font_level,
            "font_scale": label_font_scale,
        }

        if scan_cars:
            last_result["plates"] = detected_plates
            last_result["vehicles"] = vehicle_overlays

        # Optional Cloud Gallery upload (S3)
        try:
            self._cloud_gallery_upload_sync(
                directory=save_folder,
                saved_file=saved_file,
                always_latest=always_latest,
            )
        except Exception:
            pass

        return AFRProcessResult(last_result=last_result, index_data=index_data)

    def _cloud_gallery_upload_sync(self, directory: Path, saved_file: Optional[str], always_latest: bool) -> None:
        """Upload latest artifacts to S3 (sync, called inside executor)."""
        bucket = (self._s3_bucket or "").strip()
        if not bucket or self._s3_client is None:
            return

        # Gate by options (defaults: enabled if bucket is set)
        if not bool(self._opt.get(CONF_CLOUD_GALLERY_ENABLED, True)):
            return

        # IMPORTANT:
        # By default we DO NOT upload scan artifacts (recognition_*.jpg / latest / index)
        # to S3. The S3 integration is primarily used for Face Gallery sync
        # (training_cache + gallery_store + manifest) handled in face_gallery_s3.py.
        # Enable this only if you explicitly want to store scan snapshots in S3.
        if not bool(self._opt.get(CONF_CLOUD_SCAN_UPLOAD_ENABLED, False)):
            return

        prefix = (self._opt.get(CONF_CLOUD_GALLERY_PREFIX) or self._s3_prefix or AFR_SCAN_DIRNAME).strip("/")
        if not prefix:
            prefix = AFR_SCAN_DIRNAME

        # Upload index (if present)
        index_path = directory / "recognition_index.json"
        if index_path.exists():
            _s3_upload_file_sync(self._s3_client, bucket, f"{prefix}/recognition_index.json", index_path)

        # Upload saved snapshot
        if saved_file:
            img_path = directory / saved_file
            if img_path.exists():
                _s3_upload_file_sync(self._s3_client, bucket, f"{prefix}/{saved_file}", img_path)

        # Upload latest image (if enabled)
        if always_latest:
            latest_path = directory / "recognition_latest.jpg"
            if latest_path.exists():
                _s3_upload_file_sync(self._s3_client, bucket, f"{prefix}/recognition_latest.jpg", latest_path)

    # --------------------------
    # helpers
    # --------------------------
    def _usage_increment(self, scans_delta: int = 0, aws_calls_delta: int = 0) -> None:
        try:
            store = self.hass.data.get(DOMAIN, {}).get("usage_store")
            if store:
                store.increment(scans_delta=scans_delta, aws_calls_delta=aws_calls_delta)
                return

            data = self.hass.data.setdefault(DOMAIN, {})
            usage = data.setdefault(
                "usage",
                {
                    "month": None,
                    "scans_month": 0,
                    "aws_calls_month": 0,
                    "last_month_scans": 0,
                    "last_month_api_calls": 0,
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

    def _detect_text_on_image(self, image_bytes: bytes) -> dict | None:
        try:
            resp = self._rekognition.detect_text(Image={"Bytes": image_bytes})
            return resp
        except botocore.exceptions.ClientError as e:
            _LOGGER.error("detect_text error: %s", e)
            return None
        except Exception as e:
            _LOGGER.error("detect_text generic error: %s", e)
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
        persons_without_recognized_face: list,
        vehicle_overlays: list[dict] | None = None,
    ) -> Optional[str]:
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            _LOGGER.error("save_image: cannot ensure directory exists: %s", e)
            return None

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

        occupied_labels: list[tuple[int, int, int, int]] = []

        # --- Vehicles (FUCHSIA) ---
        if vehicle_overlays:
            for vo in vehicle_overlays:
                vb = vo.get("bounding_box") or {}
                if not vb:
                    continue

                text = str(vo.get("text") or "").strip() or "vehicle"

                img = draw_box_scaled(
                    img,
                    (vb["y_min"], vb["x_min"], vb["y_max"], vb["x_max"]),
                    img.width,
                    img.height,
                    text=text,
                    color=FUCHSIA,
                    font_scale=label_font_scale,
                    occupied_labels=occupied_labels,
                )


        targets_conf = self._opt.get("targets_confidence") or {}
        default_min = float(self._opt.get("default_min_confidence", 10.0) or 10.0)
        try:
            person_min_conf = float(targets_conf.get("person", default_min))
        except Exception:
            person_min_conf = default_min

        try:
            min_area = float(min_red_area or 0.0)
        except Exception:
            min_area = 0.0

        persons = [o for o in (self._targets_found or []) if o.get("name") == "person"]

        recognized_person_ids = map_recognized_faces_to_person_ids(persons, (self._faces or []))

        red_candidates: list[tuple[float, float, dict, bool]] = []
        for p in persons:
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

            is_recognized = id(p) in recognized_person_ids
            red_candidates.append((area, conf, pb, is_recognized))

        red_candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)

        limit = int(max_red_boxes or 0)
        if limit <= 0:
            limit = len(red_candidates)

        for _, __, pb, is_recognized in red_candidates[:limit]:
            img = draw_box_scaled(
                img,
                (pb["y_min"], pb["x_min"], pb["y_max"], pb["x_max"]),
                img.width,
                img.height,
                text="" if is_recognized else "person",
                color=RED,
                font_scale=label_font_scale,
                occupied_labels=occupied_labels,
            )

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
                occupied_labels=occupied_labels,
            )

        # NOTE (compat/UX):
        # - We ALWAYS write the latest snapshot to recognition_latest.jpg.
        # - If save_timestamped is enabled, we ALSO write recognition_YYYYmmdd_HHMMSS.<ext>
        #   and update recognition_index.json with those timestamped filenames.
        # - We no longer generate recognition.jpg (legacy name) because it creates confusion
        #   and breaks panel assumptions.

        ext = (save_format or "jpg").lower()
        if ext not in ("jpg", "png"):
            ext = "jpg"

        rgb = None
        try:
            # Prepare RGB once for JPEG outputs (latest is always JPEG).
            rgb = img.convert("RGB")
        except Exception as e:
            _LOGGER.error("save_image: cannot convert to RGB: %s", e)
            return None

        # 1) Always write latest (JPEG)
        try:
            rgb.save(
                directory / "recognition_latest.jpg",
                format="JPEG",
                quality=85,
                subsampling=2,
            )
        except Exception as e:
            _LOGGER.warning("save_image: cannot write latest file: %s", e)
            # If we cannot write the latest file, there's no point continuing.
            return None

        saved_name: str = "recognition_latest.jpg"

        # 2) Optionally write timestamped snapshot
        if save_timestamped:
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recognition_{stamp}.{ext}"
            save_path = directory / filename

            try:
                if ext == "jpg":
                    # Reuse the same RGB buffer (already computed)
                    rgb.save(save_path, format="JPEG", quality=85, subsampling=2)
                else:
                    img.save(save_path, format="PNG", optimize=True)
                saved_name = save_path.name
            except Exception as e:
                _LOGGER.error("save_image: error saving %s: %s", save_path, e)
                # Keep latest; just skip timestamped.
                saved_name = "recognition_latest.jpg"

        # Cleanup only timestamped files
        _cleanup_old_recognition_files(directory, keep=max_saved, prefix="recognition_")

        return saved_name
