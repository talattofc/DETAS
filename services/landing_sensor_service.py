<<<<<<< HEAD
"""Inis yaklasma sensorleri: MZ80 GPIO ve Sharp analog mesafe."""
=======
"""Inis yaklasma sensoru: MZ80 GPIO."""
>>>>>>> 82cd033 (orange cube entegrasyonu otopilot)

import math
import threading
import time

from config import (
    LANDING_DANGER_DISTANCE_CM,
    LANDING_MZ80_ACTIVE_LOW,
    LANDING_MZ80_DETECT_DISTANCE_CM,
    LANDING_MZ80_GPIO_PIN,
    LANDING_MZ80_READ_INTERVAL,
    LANDING_WARNING_DISTANCE_CM,
<<<<<<< HEAD
    SHARP_ADC_MAX_RAW,
    SHARP_ADC_MAX_VOLTAGE,
    SHARP_GP2Y0A41_MAX_VALID_CM,
    SHARP_GP2Y0A41_MIN_VALID_CM,
=======
>>>>>>> 82cd033 (orange cube entegrasyonu otopilot)
)
from services.logger_service import add_log
from services.state import state

try:
<<<<<<< HEAD
=======
    from services.autonomous_mission_service import update_landing_sensor_status
except Exception:
    update_landing_sensor_status = None

try:
>>>>>>> 82cd033 (orange cube entegrasyonu otopilot)
    from gpiozero import DigitalInputDevice

    GPIOZERO_AVAILABLE = True
except Exception as exc:
    DigitalInputDevice = None
    GPIOZERO_AVAILABLE = False
    _GPIO_IMPORT_ERROR = exc


_thread_lock = threading.Lock()
_landing_thread = None
_last_mz80_log_state = None
_last_proximity_level = None


def _round_or_none(value, digits=1):
    try:
        if value is None:
            return None
        value = float(value)
        if not math.isfinite(value):
            return None
        return round(value, digits)
    except Exception:
        return None


<<<<<<< HEAD
def sharp_voltage_to_cm(voltage):
    """GP2Y0A41SK0F icin yaklasik 4-30 cm donusumu."""
    try:
        voltage = float(voltage)
    except Exception:
        return None

    if voltage <= 0.05:
        return None

    # GP2Y0A41SK0F pratik kalibrasyon egrisi; sahada katsayi gerekirse config'e tasinir.
    distance = 12.08 * (voltage ** -1.058)
    if distance < SHARP_GP2Y0A41_MIN_VALID_CM or distance > SHARP_GP2Y0A41_MAX_VALID_CM:
        return None
    return distance


def sharp_raw_to_voltage(raw_value):
    try:
        raw = float(raw_value)
    except Exception:
        return None

    if raw <= 0:
        return None

    # Bazı MAVLink alanlari mV tasiyabilir, bazilari ADC count tasir.
    if raw > SHARP_ADC_MAX_RAW and raw <= 5000:
        return raw / 1000.0

    return (raw / SHARP_ADC_MAX_RAW) * SHARP_ADC_MAX_VOLTAGE


def _compute_proximity(mz80_detected=None, sharp_cm=None):
    distances = []
    if mz80_detected:
        distances.append(float(LANDING_MZ80_DETECT_DISTANCE_CM))
    if sharp_cm is not None:
        distances.append(float(sharp_cm))
=======
def _compute_proximity(mz80_detected=None):
    distances = []
    if mz80_detected:
        distances.append(float(LANDING_MZ80_DETECT_DISTANCE_CM))
>>>>>>> 82cd033 (orange cube entegrasyonu otopilot)

    nearest = min(distances) if distances else None

    if nearest is None:
        return None, "unknown", "Bilinmiyor", False
    if nearest <= LANDING_DANGER_DISTANCE_CM:
        return nearest, "danger", "Yere cok yakin", True
    if nearest <= LANDING_WARNING_DISTANCE_CM:
        return nearest, "warn", "Yere yaklasiyor", True
    return nearest, "safe", "Guvenli", False


def _update_landing_state(**updates):
    global _last_proximity_level

    snapshot = state.snapshot()
    mz80_detected = updates.get("landing_mz80_detected", snapshot.get("landing_mz80_detected"))
<<<<<<< HEAD
    sharp_cm = updates.get("landing_sharp_distance_cm", snapshot.get("landing_sharp_distance_cm"))
    nearest, level, text, alert = _compute_proximity(mz80_detected, sharp_cm)
=======
    nearest, level, text, alert = _compute_proximity(mz80_detected)
>>>>>>> 82cd033 (orange cube entegrasyonu otopilot)

    payload = {
        **updates,
        "landing_nearest_distance_cm": _round_or_none(nearest, 1),
        "landing_proximity_level": level,
        "landing_proximity_text": text,
        "landing_proximity_alert": alert,
        "landing_proximity_last_time": time.time(),
    }
    state.update(**payload)

<<<<<<< HEAD
=======
    if update_landing_sensor_status is not None:
        try:
            update_landing_sensor_status(
                mz80_connected=payload.get("landing_mz80_connected"),
                mz80_detected=payload.get("landing_mz80_detected"),
                mz80_distance_cm=payload.get("landing_mz80_distance_cm"),
                proximity_level=level,
                proximity_text=text,
                proximity_alert=alert,
                timestamp=payload["landing_proximity_last_time"],
            )
        except Exception:
            pass

>>>>>>> 82cd033 (orange cube entegrasyonu otopilot)
    if level != _last_proximity_level and level in ("warn", "danger"):
        add_log(f"Inis sensor uyarisi: {text} ({payload['landing_nearest_distance_cm']} cm)")
    _last_proximity_level = level


<<<<<<< HEAD
def update_sharp_distance(distance_cm=None, voltage=None, raw=None, source="mavlink"):
    if distance_cm is None and voltage is None and raw is not None:
        voltage = sharp_raw_to_voltage(raw)

    if distance_cm is None and voltage is not None:
        distance_cm = sharp_voltage_to_cm(voltage)

    updates = {
        "landing_sharp_connected": distance_cm is not None or voltage is not None or raw is not None,
        "landing_sharp_distance_cm": _round_or_none(distance_cm, 1),
        "landing_sharp_voltage": _round_or_none(voltage, 3),
        "landing_sharp_raw": _round_or_none(raw, 1),
        "landing_sharp_source": source,
        "landing_sharp_last_time": time.time(),
    }
    _update_landing_state(**updates)
    return updates


=======
>>>>>>> 82cd033 (orange cube entegrasyonu otopilot)
def _read_mz80_loop():
    global _last_mz80_log_state

    if not GPIOZERO_AVAILABLE:
        add_log(f"MZ80 GPIO okunamadi: {_GPIO_IMPORT_ERROR}")
        state.update(landing_mz80_connected=False)
        return

    device = None
    try:
        device = DigitalInputDevice(LANDING_MZ80_GPIO_PIN, pull_up=False)
        add_log(f"MZ80 GPIO{LANDING_MZ80_GPIO_PIN} aktif")

        while True:
            raw_active = bool(device.value)
            detected = (not raw_active) if LANDING_MZ80_ACTIVE_LOW else raw_active
            distance = LANDING_MZ80_DETECT_DISTANCE_CM if detected else None

            _update_landing_state(
                landing_mz80_connected=True,
                landing_mz80_detected=detected,
                landing_mz80_distance_cm=_round_or_none(distance, 1),
                landing_mz80_last_time=time.time(),
            )

            if detected != _last_mz80_log_state:
                add_log(f"MZ80 {'engel/yakin zemin algiladi' if detected else 'serbest'}")
                _last_mz80_log_state = detected

            time.sleep(LANDING_MZ80_READ_INTERVAL)
    except Exception as exc:
        add_log(f"MZ80 GPIO hatasi: {exc}")
        state.update(landing_mz80_connected=False)
    finally:
        try:
            if device is not None:
                device.close()
        except Exception:
            pass


def start_landing_sensor_thread():
    global _landing_thread

    with _thread_lock:
        if _landing_thread is not None and _landing_thread.is_alive():
            return _landing_thread

        _landing_thread = threading.Thread(
            target=_read_mz80_loop,
            name="adti-landing-sensors",
            daemon=True,
        )
        _landing_thread.start()
        return _landing_thread
