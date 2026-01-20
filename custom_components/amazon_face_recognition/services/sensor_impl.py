# custom_components/amazon_face_recognition/sensor.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from ..const import DOMAIN, CONF_SCAN_CARS

from ..const import (
    DOMAIN,
    CONF_SCAN_CARS,
    EVENT_UPDATED,
    EVENT_FACES_UPDATED,
    EVENT_PLATES_UPDATED,
)


@dataclass(frozen=True, kw_only=True)
class AFRSensorEntityDescription(SensorEntityDescription):
    pass


SENSORS = [
    AFRSensorEntityDescription(key="status", name="Status", icon="mdi:face-recognition"),
    AFRSensorEntityDescription(key="last_recognized", name="Last Recognized", icon="mdi:account"),
    AFRSensorEntityDescription(key="persons_in_collection", name="Persons In Collection", icon="mdi:account-multiple"),
    AFRSensorEntityDescription(key="aws_calls_month", name="AWS Calls This Month", icon="mdi:cloud-outline"),
    AFRSensorEntityDescription(key="last_car_plate_scan", name="Last Car Plate Scan", icon="mdi:car-info"),

]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([AFRSensor(hass, entry, d) for d in SENSORS], update_before_add=True)


class AFRSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, desc: AFRSensorEntityDescription) -> None:
        self.hass = hass
        self.entity_description = desc
        self._entry_id = entry.entry_id
        self._entry_options = dict(entry.options or {})
        self._attr_unique_id = f"{entry.unique_id}-{desc.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Amazon Rekognition",
            "model": "Face Recognition",
        }

        self._unsub: list[Callable[[], None]] = []

        # ---- solo per last_recognized ----
        self._transient_state: str = "idle"
        self._reset_unsub: Optional[Callable[[], None]] = None
        self._last_persons_scanned: list[str] = []

    def _domain_data(self) -> dict:
        return self.hass.data.get(DOMAIN, {}) or {}
    
    def _plates_mapping(self) -> dict[str, str]:
        """Ritorna mapping plate->name salvato dal panel (se presente)."""
        data = self._domain_data()
        plates = (data.get("plates") or {})
        items = plates.get("items") if isinstance(plates, dict) else {}
        if not isinstance(items, dict):
            return {}
        # Normalizza chiavi in UPPER
        out: dict[str, str] = {}
        for k, v in items.items():
            pk = str(k or "").strip().upper()
            nv = str(v or "").strip()
            if pk and nv:
                out[pk] = nv
        return out

    def _compute_last_car_plate_state(self) -> tuple[str, dict[str, Any]]:
        """
        Stato:
        - off  : se scan_cars disattivo
        - idle : se attivo ma nessuna targa ancora
        - altro: nomi (se mappati) o targhe
        """
        scan_cars = bool((self.hass.data.get(DOMAIN, {}) or {}).get("entry_options", {}).get(self._entry_id, {}).get(CONF_SCAN_CARS, False))
        # fallback: se non hai entry_options in hass.data, usa entry.options direttamente (vedi punto 3 sotto)
        # Questo verrà sovrascritto subito sotto in __init__ con self._entry_options
        scan_cars = bool(getattr(self, "_entry_options", {}).get(CONF_SCAN_CARS, scan_cars))

        if not scan_cars:
            return "off", {}

        data = self._domain_data()
        last = data.get("last_result", {}) or {}

        plates = last.get("plates") or last.get("detected_plates") or []
        if not plates:
            return "idle", {}

        mapping = self._plates_mapping()

        resolved: list[str] = []
        seen: set[str] = set()  # dedup mantenendo ordine
        for it in plates:
            p = str((it or {}).get("plate") or "").strip().upper()
            if not p or p in seen:
                continue
            seen.add(p)
            resolved.append(mapping.get(p) or p)

        state = ", ".join(resolved) if resolved else "idle"

        attrs: dict[str, Any] = {
            "timestamp": last.get("timestamp"),
            "camera_entity": last.get("camera_entity"),
            "detected_plates": plates,
            "resolved": resolved,
            "mapped": {p: mapping[p] for p in seen if p in mapping},
        }
        return state, attrs


    def _get_processor(self):
        data = self._domain_data()
        return (data.get("processors") or {}).get(self._entry_id)
    
    def _write_state_safe(self) -> None:
        """Chiama async_write_ha_state sempre nel thread dell'event loop."""
        if not self.hass:
            return

        def _do():
            try:
                self.async_write_ha_state()
            except Exception:
                pass

        # Se siamo già nel loop, call_soon va bene; se siamo in thread worker, call_soon_threadsafe è obbligatorio
        try:
            self.hass.loop.call_soon_threadsafe(_do)
        except Exception:
            _do()


    async def async_added_to_hass(self) -> None:
        """Aggiorna i sensori quando arrivano eventi dal processor."""
        await super().async_added_to_hass()

        @callback
        def _refresh(_event) -> None:
            self._write_state_safe()

        # refresh base per tutti i sensori
        self._unsub.append(self.hass.bus.async_listen(EVENT_UPDATED, _refresh))
        self._unsub.append(self.hass.bus.async_listen(EVENT_FACES_UPDATED, _refresh))
        self._unsub.append(self.hass.bus.async_listen(EVENT_PLATES_UPDATED, _refresh))


        # logica speciale SOLO per last_recognized
        if self.entity_description.key == "last_recognized":

            async def _handle_update(_event) -> None:
                data = self._domain_data()
                last = data.get("last_result", {}) or {}

                recognized = last.get("recognized") or []
                if isinstance(recognized, str):
                    recognized = [recognized]
                recognized = [str(x).strip() for x in recognized if str(x).strip()]

                unknown = bool(last.get("unknown_person_found"))

                # alert = true quando SOLO sconosciuti
                derived_alert = bool(unknown and len(recognized) == 0)
                alert = bool(last.get("alert") or derived_alert)

                # ✅ persistente fino alla scansione successiva
                if unknown and len(recognized) == 0:
                    self._last_persons_scanned = ["unknown person"]
                else:
                    self._last_persons_scanned = recognized


                # ✅ stato transiente (15s)
                if derived_alert:
                    self._transient_state = "unknown person"
                elif recognized:
                    self._transient_state = ", ".join(recognized)
                else:
                    self._transient_state = "idle"

                self._write_state_safe()

                # reset timer precedente
                if self._reset_unsub:
                    try:
                        self._reset_unsub()
                    except Exception:
                        pass
                    self._reset_unsub = None

                def _reset(_now) -> None:
                    def _do_reset():
                        self._transient_state = "idle"
                        self._reset_unsub = None
                        self.async_write_ha_state()

                    # Esegue tutto nel loop, anche la mutation dello stato
                    try:
                        self.hass.loop.call_soon_threadsafe(_do_reset)
                    except Exception:
                        _do_reset()


                self._reset_unsub = async_call_later(self.hass, 15, _reset)

            self._unsub.append(self.hass.bus.async_listen(EVENT_UPDATED, _handle_update))

    async def async_will_remove_from_hass(self) -> None:
        for u in self._unsub:
            try:
                u()
            except Exception:
                pass
        self._unsub = []

        if self._reset_unsub:
            try:
                self._reset_unsub()
            except Exception:
                pass
            self._reset_unsub = None

        await super().async_will_remove_from_hass()

    @property
    def native_value(self):
        """Valore principale (stato) del sensore."""
        data = self._domain_data()
        last = data.get("last_result", {}) or {}
        faces_index = data.get("faces_index", {}) or {}
        usage = data.get("usage", {}) or {}

        k = self.entity_description.key

        if k == "status":
            return "ok" if last else "idle"

        if k == "last_recognized":
            # ✅ stato che dura 15s, poi idle
            return self._transient_state or "idle"

        if k == "persons_in_collection":
            persons = faces_index.get("persons") or {}
            return len(persons)

        if k == "aws_calls_month":
            return int(usage.get("aws_calls_month") or 0)
        
        if k == "last_car_plate_scan":
            state, _attrs = self._compute_last_car_plate_state()
            return state


        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._domain_data()
        last = data.get("last_result", {}) or {}
        faces_index = data.get("faces_index", {}) or {}
        usage = data.get("usage", {}) or {}

        k = self.entity_description.key

        if k == "last_recognized":
            recognized = last.get("recognized") or []
            if isinstance(recognized, str):
                recognized = [recognized]
            recognized = [str(x).strip() for x in recognized if str(x).strip()]
            unknown = bool(last.get("unknown_person_found"))
            derived_alert = bool(unknown and len(recognized) == 0)
            aligned_last_scanned = ["unknown person"] if derived_alert else self._last_persons_scanned


            return {
                "last_persons_scanned": aligned_last_scanned,
                "timestamp": last.get("timestamp"),
                "file": last.get("file"),
                "image_url": last.get("image_url"),
                "latest_url": last.get("latest_url"),
                "objects": last.get("objects") or {},
                "camera_entity": last.get("camera_entity"),
                "unknown_person_found": unknown,
                # ✅ alert vero quando SOLO sconosciuti
                "alert": bool(last.get("alert") or derived_alert),
            }

        if k == "persons_in_collection":
            persons = faces_index.get("persons") or {}
            total_faces = 0
            for v in persons.values():
                if isinstance(v, dict):
                    total_faces += int(v.get("count") or 0)

            return {
                "persons": persons,
                "updated_at": faces_index.get("updated_at"),
                "total_faces": total_faces,
            }

        if k == "aws_calls_month":
            current_month_api_call = int(usage.get("aws_calls_month") or 0)
            last_month_api_call = int(usage.get("last_month_api_calls") or 0)

            current_month_scans = int(usage.get("scans_month") or 0)
            last_month_scans = int(usage.get("last_month_scans") or 0)

            aws_api_cost = 0.0
            proc = self._get_processor()
            if proc is not None:
                try:
                    aws_api_cost = float((getattr(proc, "_opt", {}) or {}).get("aws_api_cost") or 0.0)
                except (TypeError, ValueError):
                    aws_api_cost = 0.0

            current_month_cost = round(current_month_api_call * aws_api_cost, 6)
            last_month_cost = round(last_month_api_call * aws_api_cost, 6)
        
            if k == "last_car_plate_scan":
                _state, attrs = self._compute_last_car_plate_state()
                return attrs


            return {
                "month": usage.get("month"),
                "last_month_scans": last_month_scans,
                "current_month_scans": current_month_scans,
                "current_month_api_call": current_month_api_call,
                "last_month_api_call": last_month_api_call,
                "aws_api_cost": aws_api_cost,
                "current_month_cost": f"{current_month_cost:.2f}$",
                "last_month_cost": f"{last_month_cost:.2f}$",
            }
        
            


        return {}
