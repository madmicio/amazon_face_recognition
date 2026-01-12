from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    # data
    CONF_AWS_ACCESS_KEY_ID,
    CONF_AWS_SECRET_ACCESS_KEY,
    CONF_REGION_NAME,
    CONF_COLLECTION_ID,
    # options
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
    CONF_MAX_RED_BOXES,
    CONF_MIN_RED_BOX_AREA,
    CONF_MIN_RED_BOX_AREA_PCT,
    CONF_AWS_API_COST,
    CONF_DEFAULT_MIN_CONFIDENCE,
    CONF_TARGETS_CONFIDENCE,
    CONF_EXCLUDE_TARGETS,
    CONF_EXCLUDED_OBJECT_LABELS,
    CONF_LABEL_FONT_LEVEL,
    DEFAULT_LABEL_FONT_LEVEL,

    
    # defaults
    DEFAULT_REGION,
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
    DEFAULT_MIN_RED_BOX_AREA_PCT,
    DEFAULT_MAX_RED_BOXES,
    DEFAULT_MIN_RED_BOX_AREA,
    DEFAULT_AWS_API_COST,
    DEFAULT_DEFAULT_MIN_CONFIDENCE,
    DEFAULT_TARGETS_CONFIDENCE,
    DEFAULT_EXCLUDE_TARGETS,
    DEFAULT_EXCLUDED_OBJECT_LABELS,
    SUPPORTED_REGIONS,
)


def _clamp01(v: float) -> float:
    try:
        v = float(v)
    except Exception:
        v = 0.0
    return max(0.0, min(1.0, v))


def _to_list_of_str(v) -> list[str]:
    """Normalize various UI values into list[str]."""
    if v is None:
        return []
    if isinstance(v, str):
        v = v.strip()
        return [v] if v else []
    if isinstance(v, list):
        out: list[str] = []
        for x in v:
            s = str(x).strip()
            if s:
                out.append(s)
        return out
    # ObjectSelector may return dict in some cases - ignore
    return []


def _to_dict(v) -> dict:
    """Normalize UI value into dict."""
    return v if isinstance(v, dict) else {}


def _normalize_sources(v) -> list[str]:
    """Normalize camera entity list."""
    if v is None:
        return []
    if isinstance(v, str):
        v = [v]
    if isinstance(v, list):
        out = []
        for x in v:
            s = str(x).strip()
            if s:
                out.append(s)
        return out
    return []


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors: dict[str, str] = {}

        schema = vol.Schema(
            {
                vol.Required(CONF_AWS_ACCESS_KEY_ID): str,
                vol.Required(CONF_AWS_SECRET_ACCESS_KEY): str,
                vol.Required(CONF_REGION_NAME, default=DEFAULT_REGION): vol.In(SUPPORTED_REGIONS),
                vol.Optional(CONF_COLLECTION_ID, default="homeassistant_faces"): str,
            }
        )

        if user_input is not None:
            collection = (user_input.get(CONF_COLLECTION_ID) or "").strip()
            unique_id = f"{user_input[CONF_REGION_NAME]}::{collection}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="Amazon Face Recognition",
                data=user_input,
            )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        opt = dict(self.config_entry.options or {})

        # Normalize existing options (so defaults shown in UI are consistent)
        opt[CONF_SOURCES] = _normalize_sources(opt.get(CONF_SOURCES, []))

        # IMPORTANT: default excluded labels is EMPTY list
        # If key is missing, show DEFAULT_EXCLUDED_OBJECT_LABELS (should be [])
        if CONF_EXCLUDED_OBJECT_LABELS not in opt:
            opt[CONF_EXCLUDED_OBJECT_LABELS] = list(DEFAULT_EXCLUDED_OBJECT_LABELS or [])

        if user_input is not None:
            # --- normalize & enforce keys even when empty ---
            user_input[CONF_SOURCES] = _normalize_sources(user_input.get(CONF_SOURCES, opt.get(CONF_SOURCES, [])))

            # ROI clamp
            user_input[CONF_ROI_Y_MIN] = _clamp01(user_input.get(CONF_ROI_Y_MIN, opt.get(CONF_ROI_Y_MIN, DEFAULT_ROI_Y_MIN)))
            user_input[CONF_ROI_X_MIN] = _clamp01(user_input.get(CONF_ROI_X_MIN, opt.get(CONF_ROI_X_MIN, DEFAULT_ROI_X_MIN)))
            user_input[CONF_ROI_Y_MAX] = _clamp01(user_input.get(CONF_ROI_Y_MAX, opt.get(CONF_ROI_Y_MAX, DEFAULT_ROI_Y_MAX)))
            user_input[CONF_ROI_X_MAX] = _clamp01(user_input.get(CONF_ROI_X_MAX, opt.get(CONF_ROI_X_MAX, DEFAULT_ROI_X_MAX)))

            # Ensure list fields are always present (even when empty)
            user_input[CONF_EXCLUDE_TARGETS] = _to_list_of_str(user_input.get(CONF_EXCLUDE_TARGETS))
            user_input[CONF_EXCLUDED_OBJECT_LABELS] = _to_list_of_str(user_input.get(CONF_EXCLUDED_OBJECT_LABELS))

            # Ensure dict field
            user_input[CONF_TARGETS_CONFIDENCE] = _to_dict(user_input.get(CONF_TARGETS_CONFIDENCE))

            # Clean bucket empty -> remove (optional)
            if (user_input.get(CONF_S3_BUCKET) or "").strip() == "":
                user_input.pop(CONF_S3_BUCKET, None)

            # ✅ THE KEY FIX:
            # Some selectors omit the key when empty. Force-save empty lists.
            user_input.setdefault(CONF_EXCLUDED_OBJECT_LABELS, [])
            user_input.setdefault(CONF_EXCLUDE_TARGETS, [])

            # Convert percent (1..100) -> float (0.01..1.00) stored in CONF_MIN_RED_BOX_AREA
            pct = user_input.pop(CONF_MIN_RED_BOX_AREA_PCT, None)

            try:
                pct_i = int(pct) if pct is not None else int(
                    round(100 * float(opt.get(CONF_MIN_RED_BOX_AREA, DEFAULT_MIN_RED_BOX_AREA) or 0.03))
                )
            except Exception:
                pct_i = int(DEFAULT_MIN_RED_BOX_AREA_PCT)

            pct_i = max(1, min(100, pct_i))
            user_input[CONF_MIN_RED_BOX_AREA] = pct_i / 100.0


            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                # Cameras
                vol.Optional(
                    CONF_SOURCES,
                    default=opt.get(CONF_SOURCES, []),
                ): selector.selector({"entity": {"domain": "camera", "multiple": True}}),

                # ROI / Scale
                vol.Optional(CONF_ROI_Y_MIN, default=opt.get(CONF_ROI_Y_MIN, DEFAULT_ROI_Y_MIN)): vol.Coerce(float),
                vol.Optional(CONF_ROI_X_MIN, default=opt.get(CONF_ROI_X_MIN, DEFAULT_ROI_X_MIN)): vol.Coerce(float),
                vol.Optional(CONF_ROI_Y_MAX, default=opt.get(CONF_ROI_Y_MAX, DEFAULT_ROI_Y_MAX)): vol.Coerce(float),
                vol.Optional(CONF_ROI_X_MAX, default=opt.get(CONF_ROI_X_MAX, DEFAULT_ROI_X_MAX)): vol.Coerce(float),
                vol.Optional(CONF_SCALE, default=opt.get(CONF_SCALE, DEFAULT_SCALE)): vol.All(
                    vol.Coerce(float), vol.Range(min=0.1, max=1.0)
                ),

                # Saving
                vol.Optional(CONF_SAVE_FILE_FOLDER, default=opt.get(CONF_SAVE_FILE_FOLDER, "/config/www/snapshots/")): str,
                vol.Optional(CONF_MAX_SAVED_FILES, default=opt.get(CONF_MAX_SAVED_FILES, DEFAULT_MAX_SAVED_FILES)): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=500)
                ),
                vol.Optional(CONF_SAVE_FILE_FORMAT, default=opt.get(CONF_SAVE_FILE_FORMAT, DEFAULT_SAVE_FILE_FORMAT)): vol.In(["jpg", "png"]),
                vol.Optional(CONF_SAVE_TIMESTAMPED_FILE, default=opt.get(CONF_SAVE_TIMESTAMPED_FILE, DEFAULT_SAVE_TIMESTAMPED_FILE)): bool,
                vol.Optional(CONF_ALWAYS_SAVE_LATEST_FILE, default=opt.get(CONF_ALWAYS_SAVE_LATEST_FILE, DEFAULT_ALWAYS_SAVE_LATEST_FILE)): bool,
                vol.Optional(CONF_SHOW_BOXES, default=opt.get(CONF_SHOW_BOXES, DEFAULT_SHOW_BOXES)): bool,
                vol.Optional(CONF_S3_BUCKET, default=opt.get(CONF_S3_BUCKET, "")): str,

                # Overlays
                # Overlays (user-friendly)
                vol.Optional(
                    CONF_LABEL_FONT_LEVEL,
                    default=int(opt.get(CONF_LABEL_FONT_LEVEL, DEFAULT_LABEL_FONT_LEVEL)),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=20,
                        step=1,
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),

                vol.Optional(CONF_MAX_RED_BOXES, default=opt.get(CONF_MAX_RED_BOXES, DEFAULT_MAX_RED_BOXES)): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=50)
                ),
                # Min red box area (UI as percent 1..100)
                vol.Optional(
                    CONF_MIN_RED_BOX_AREA_PCT,
                    default=int(
                        round(
                            100
                            * float(opt.get(CONF_MIN_RED_BOX_AREA, DEFAULT_MIN_RED_BOX_AREA) or 0.03)
                        )
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=100,
                        step=1,
                        mode=selector.NumberSelectorMode.SLIDER,
                        unit_of_measurement="%",
                    )
                ),


                # Filtering
                vol.Optional(CONF_DEFAULT_MIN_CONFIDENCE, default=opt.get(CONF_DEFAULT_MIN_CONFIDENCE, DEFAULT_DEFAULT_MIN_CONFIDENCE)): vol.All(
                    vol.Coerce(float), vol.Range(min=0.0, max=100.0)
                ),

                # JSON editors (UI-safe)
                vol.Optional(
                    CONF_TARGETS_CONFIDENCE,
                    default=_to_dict(opt.get(CONF_TARGETS_CONFIDENCE, DEFAULT_TARGETS_CONFIDENCE)),
                ): selector.ObjectSelector(),

                vol.Optional(
                    CONF_EXCLUDE_TARGETS,
                    default=_to_list_of_str(opt.get(CONF_EXCLUDE_TARGETS, DEFAULT_EXCLUDE_TARGETS)),
                ): selector.ObjectSelector(),

                # ✅ This is the one you care about
                vol.Optional(
                    CONF_EXCLUDED_OBJECT_LABELS,
                    default=_to_list_of_str(opt.get(CONF_EXCLUDED_OBJECT_LABELS, DEFAULT_EXCLUDED_OBJECT_LABELS)),
                ): selector.ObjectSelector(),

                # Costs
                vol.Optional(CONF_AWS_API_COST, default=opt.get(CONF_AWS_API_COST, DEFAULT_AWS_API_COST)): vol.All(
                    vol.Coerce(float), vol.Range(min=0.0, max=1.0)
                ),

            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
