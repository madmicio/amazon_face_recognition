from pathlib import Path

FONT_PATH = Path(__file__).resolve().parent / "fonts" / "DejaVuSans.ttf"


DOMAIN = "amazon_face_recognition"

# Events
EVENT_UPDATED = "amazon_face_recognition_updated"
EVENT_FACES_UPDATED = f"{DOMAIN}.faces_updated"

# WS types
WS_GET_LAST_RESULT = f"{DOMAIN}/get_last_result"
WS_GET_INDEX = f"{DOMAIN}/get_index"
WS_SUBSCRIBE_UPDATES = f"{DOMAIN}/subscribe_updates"
WS_GET_FACES_INDEX = f"{DOMAIN}/get_faces_index"
WS_SUBSCRIBE_FACES = f"{DOMAIN}/subscribe_faces"

# ConfigEntry data keys (step user)
CONF_AWS_ACCESS_KEY_ID = "aws_access_key_id"
CONF_AWS_SECRET_ACCESS_KEY = "aws_secret_access_key"
CONF_REGION_NAME = "region_name"
CONF_COLLECTION_ID = "collection_id"

# Folder under /config/www used to store the (local) gallery / annotated snapshots.
# NOTE: this folder is exposed by Home Assistant as /local/<AFR_SCAN_DIRNAME>.
#
# IMPORTANT:
# - This folder is for *snapshots/annotated images*.
# - Training images (used for indexing faces) are stored under /config/<TRAINING_ROOT_DIRNAME>/training_cache.
AFR_SCAN_DIRNAME = "amazon_face_recognition_scan"

# Folder under /config used to store training cache (images uploaded for indexing).
TRAINING_ROOT_DIRNAME = "amazon_face_gallery"

# Optional Cloud Gallery (S3)
CONF_CLOUD_GALLERY_ENABLED = "cloud_gallery_enabled"
CONF_CLOUD_GALLERY_PREFIX = "cloud_gallery_prefix"
CONF_CLOUD_GALLERY_SYNC_ON_STARTUP = "cloud_gallery_sync_on_startup"

# If enabled, the integration will also upload the *scan* artifacts produced by
# the service `amazon_face_recognition.scan` (recognition_*.jpg,
# recognition_latest.jpg, recognition_index.json) to S3 under cloud_gallery_prefix.
#
# Face gallery sync (training_cache + gallery_store + manifest) is handled by
# face_gallery_s3.py and is NOT affected by this flag.
CONF_CLOUD_SCAN_UPLOAD_ENABLED = "cloud_scan_upload_enabled"


CONF_SCALE = "scale"

CONF_SAVE_FILE_FOLDER = "save_file_folder"
CONF_MAX_SAVED_FILES = "max_saved_files"
CONF_SAVE_FILE_FORMAT = "save_file_format"
CONF_SAVE_TIMESTAMPED_FILE = "save_timestamped_file"
CONF_ALWAYS_SAVE_LATEST_FILE = "always_save_latest_file"
CONF_SHOW_BOXES = "show_boxes"
CONF_S3_BUCKET = "s3_bucket"

CONF_MAX_RED_BOXES = "max_red_boxes"
CONF_MIN_RED_BOX_AREA = "min_red_box_area"
CONF_MIN_RED_BOX_AREA_PCT = "min_red_box_area_pct"

CONF_AWS_API_COST = "aws_api_cost"

# Filtering (NEW mode)
CONF_DEFAULT_MIN_CONFIDENCE = "default_min_confidence"
CONF_TARGETS_CONFIDENCE = "targets_confidence"  # dict: label->min_conf
CONF_EXCLUDE_TARGETS = "exclude_targets"        # list[str]
CONF_EXCLUDED_OBJECT_LABELS = "excluded_object_labels"  # list[str]
CONF_LABEL_FONT_LEVEL = "label_font_level"
CONF_SCAN_CARS = "scan_cars"

# --- Vehicle / Plate scan tuning ---
CONF_VEHICLE_AREA_ABS_MIN = "vehicle_area_abs_min"
CONF_MAX_VEHICLES_TO_SCAN = "max_vehicles_to_scan"






# Defaults
DEFAULT_REGION = "eu-west-1"

DEFAULT_LABEL_FONT_LEVEL = 6
DEFAULT_SCALE = 1.0

DEFAULT_MAX_SAVED_FILES = 10
DEFAULT_SAVE_FILE_FORMAT = "jpg"
DEFAULT_SAVE_TIMESTAMPED_FILE = True
DEFAULT_ALWAYS_SAVE_LATEST_FILE = True
DEFAULT_SHOW_BOXES = True

DEFAULT_MAX_RED_BOXES = 6
DEFAULT_MIN_RED_BOX_AREA = 0.03
DEFAULT_MIN_RED_BOX_AREA_PCT = 3

DEFAULT_AWS_API_COST = 0.001

DEFAULT_DEFAULT_MIN_CONFIDENCE = 10.0
DEFAULT_TARGETS_CONFIDENCE = {}
DEFAULT_EXCLUDE_TARGETS = []



EXCLUDED_OBJECT_LABELS: list[str] = []
DEFAULT_EXCLUDED_OBJECT_LABELS: list[str] = []

# --- Vehicle / Plate scan tuning ---
DEFAULT_VEHICLE_AREA_ABS_MIN = 0.01     # 1% dell'immagine
DEFAULT_MAX_VEHICLES_TO_SCAN = 6

# Extra events (image_processing platform)
EVENT_OBJECT_DETECTED = f"{DOMAIN}.object_detected"
EVENT_FACE_DETECTED = f"{DOMAIN}.face_detected"
EVENT_GALLERY_UPDATED = f"{DOMAIN}.gallery_updated"

# Saved file attribute key used in events
SAVED_FILE = "saved_file"

# Overlay colors
RED = (255, 0, 0)
YELLOW = (255, 255, 0)

# Vehicles overlay
FUCHSIA = (255, 0, 255)

# --- Plates (targa -> nome) ---
EVENT_PLATES_UPDATED = f"{DOMAIN}.plates_updated"
EVENT_ROI_UPDATED = f"{DOMAIN}.roi_updated"

WS_GET_PLATES = f"{DOMAIN}/get_plates"
WS_SET_PLATES = f"{DOMAIN}/set_plates"
WS_SUBSCRIBE_PLATES = f"{DOMAIN}/subscribe_plates"

# ROI (managed via panel + websocket, stored in entry.options['roi_by_camera'])
WS_GET_ROI = f"{DOMAIN}/get_roi"
WS_SET_ROI = f"{DOMAIN}/set_roi"
WS_SUBSCRIBE_ROI = f"{DOMAIN}/subscribe_roi"

# const.py

SUPPORTED_REGIONS = [
    "us-east-1", "us-east-2", "us-west-1", "us-west-2", "ca-central-1",
    "eu-west-1", "eu-central-1", "eu-west-2", "eu-west-3",
    "ap-southeast-1", "ap-southeast-2", "ap-northeast-2", "ap-northeast-1",
    "ap-south-1", "sa-east-1",
]

WS_GET_GALLERY = f"{DOMAIN}/get_gallery"
WS_SUBSCRIBE_GALLERY = f"{DOMAIN}/subscribe_gallery"

# Face gallery (training_cache) S3 sync
WS_SYNC_FACE_GALLERY = f"{DOMAIN}/sync_face_gallery"