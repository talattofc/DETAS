"""Orange Cube otonom gorev MAVLink baglanti servisi.

Bu modul mevcut mavlink_service.py dosyasini degistirmeden, otonom gorev
akisi icin sade bir Cube durum katmani saglar.
"""

import threading
import time
from copy import deepcopy

from config import (
    AUTO_MISSION_ENABLED,
    AUTO_MISSION_MIN_BATTERY_VOLTAGE,
    AUTO_MISSION_MIN_SATELLITES,
    AUTO_MISSION_RETRIGGER_COOLDOWN_SECONDS,
    AUTO_TAKEOFF_ALTITUDE_M,
    MAVLINK_BAUD,
    MAVLINK_HEARTBEAT_TIMEOUT,
    MAVLINK_PORT,
)
from services.logger_service import add_log

try:
    from pymavlink import mavutil

    PYMAVLINK_AVAILABLE = True
except Exception as exc:
    mavutil = None
    PYMAVLINK_AVAILABLE = False
    _PYMAVLINK_IMPORT_ERROR = exc


_master = None
_reader_thread = None
_mission_thread = None
_lock = threading.RLock()
_command_lock = threading.RLock()
_mission_lock = threading.RLock()
_stop_event = threading.Event()

_status = {
    "connected": False,
    "port": MAVLINK_PORT,
    "baud": MAVLINK_BAUD,
    "mode": "BILINMIYOR",
    "armed": False,
    "battery_voltage": 0.0,
    "gps_fix": 0,
    "satellite_count": 0,
    "altitude": 0.0,
    "last_heartbeat": 0.0,
    "last_message_time": 0.0,
    "target_system": None,
    "target_component": None,
    "error": None,
    "preflight_ok": False,
    "preflight_error": None,
    "preflight_errors": [],
    "preflight_last_time": 0.0,
    "mission_running": False,
    "mission_phase": "idle",
    "mission_message": "Beklemede",
    "mission_error": None,
    "mission_started_time": 0.0,
    "mission_finished_time": 0.0,
    "last_mission_start_time": 0.0,
    "landing_mz80_connected": False,
    "landing_mz80_detected": False,
    "landing_mz80_distance_cm": None,
    "landing_proximity_level": "unknown",
    "landing_proximity_text": "Bilinmiyor",
    "landing_proximity_alert": False,
    "landing_sensor_last_time": 0.0,
}


def _set_status(**updates):
    with _lock:
        _status.update(deepcopy(updates))


def _heartbeat_age():
    last_heartbeat = _status.get("last_heartbeat") or 0.0
    if not last_heartbeat:
        return None
    return time.time() - float(last_heartbeat)


def is_connected():
    """Cube heartbeat zamanina gore baglanti durumunu dondurur."""
    with _lock:
        connected = bool(_status.get("connected"))

    age = _heartbeat_age()
    if age is not None and age > MAVLINK_HEARTBEAT_TIMEOUT:
        _set_status(connected=False, error="Heartbeat zaman asimi")
        return False

    return connected


def get_status():
    """Otonom gorev icin son Cube durum sozlugunu dondurur."""
    with _lock:
        status = deepcopy(_status)

    age = _heartbeat_age()
    status["connected"] = is_connected()
    status["heartbeat_age"] = round(age, 1) if age is not None else None
    return status


def update_landing_sensor_status(
    mz80_connected=None,
    mz80_detected=None,
    mz80_distance_cm=None,
    proximity_level=None,
    proximity_text=None,
    proximity_alert=None,
    timestamp=None,
):
    """MZ80 bilgisini otonom gorev status'una yalnizca uyari olarak tasir."""
    updates = {
        "landing_sensor_last_time": timestamp or time.time(),
    }

    if mz80_connected is not None:
        updates["landing_mz80_connected"] = bool(mz80_connected)
    if mz80_detected is not None:
        updates["landing_mz80_detected"] = bool(mz80_detected)
    if mz80_distance_cm is not None:
        updates["landing_mz80_distance_cm"] = mz80_distance_cm
    elif mz80_detected is False:
        updates["landing_mz80_distance_cm"] = None
    if proximity_level is not None:
        updates["landing_proximity_level"] = str(proximity_level)
    if proximity_text is not None:
        updates["landing_proximity_text"] = str(proximity_text)
    if proximity_alert is not None:
        updates["landing_proximity_alert"] = bool(proximity_alert)

    _set_status(**updates)
    return get_status()


def preflight_check():
    """Otonom gorev baslamadan once temel emniyet kosullarini kontrol eder."""
    status = get_status()
    errors = []

    if not AUTO_MISSION_ENABLED:
        errors.append("Otonom gorev config uzerinden kapali")

    if not status.get("connected"):
        errors.append("MAVLink baglantisi yok")

    if status.get("armed"):
        errors.append("Cube zaten ARM durumda; gorev baslatilmadi")

    gps_fix = int(status.get("gps_fix") or 0)
    if gps_fix < 3:
        errors.append(f"GPS fix yetersiz: {gps_fix}")

    satellites = int(status.get("satellite_count") or 0)
    if satellites < AUTO_MISSION_MIN_SATELLITES:
        errors.append(
            f"Uydu sayisi yetersiz: {satellites}/{AUTO_MISSION_MIN_SATELLITES}"
        )

    battery_voltage = float(status.get("battery_voltage") or 0.0)
    if battery_voltage <= AUTO_MISSION_MIN_BATTERY_VOLTAGE:
        errors.append(
            "Batarya voltaji dusuk: "
            f"{battery_voltage:.2f}V <= {AUTO_MISSION_MIN_BATTERY_VOLTAGE:.2f}V"
        )

    ok = not errors
    error_text = "; ".join(errors) if errors else None
    _set_status(
        preflight_ok=ok,
        preflight_error=error_text,
        preflight_errors=errors,
        preflight_last_time=time.time(),
        error=error_text,
    )

    if ok:
        add_log("Otonom gorev preflight OK")
    else:
        add_log(f"Otonom gorev preflight basarisiz: {error_text}")

    return ok


def _handle_heartbeat(msg):
    armed = False
    try:
        armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
    except Exception:
        armed = False

    try:
        mode = mavutil.mode_string_v10(msg)
    except Exception:
        mode = "BILINMIYOR"

    _set_status(
        connected=True,
        mode=mode,
        armed=armed,
        last_heartbeat=time.time(),
        last_message_time=time.time(),
        target_system=getattr(msg, "get_srcSystem", lambda: None)(),
        target_component=getattr(msg, "get_srcComponent", lambda: None)(),
        error=None,
    )


def _handle_sys_status(msg):
    voltage = 0.0
    try:
        raw_voltage = float(getattr(msg, "voltage_battery", 0))
        if raw_voltage > 0:
            voltage = raw_voltage / 1000.0
    except Exception:
        voltage = 0.0

    if voltage > 0:
        _set_status(battery_voltage=round(voltage, 2), last_message_time=time.time())


def _handle_battery_status(msg):
    try:
        voltages = list(getattr(msg, "voltages", []) or [])
        valid = [value for value in voltages if 0 < int(value) < 65535]
        if valid:
            _set_status(
                battery_voltage=round(sum(valid) / 1000.0, 2),
                last_message_time=time.time(),
            )
    except Exception:
        return


def _handle_gps_raw_int(msg):
    updates = {"last_message_time": time.time()}
    try:
        updates["gps_fix"] = int(getattr(msg, "fix_type", 0))
    except Exception:
        pass
    try:
        updates["satellite_count"] = int(getattr(msg, "satellites_visible", 0))
    except Exception:
        pass
    _set_status(**updates)


def _handle_global_position_int(msg):
    try:
        altitude = float(getattr(msg, "relative_alt", 0)) / 1000.0
    except Exception:
        return

    _set_status(altitude=round(altitude, 2), last_message_time=time.time())


def _handle_vfr_hud(msg):
    try:
        altitude = float(getattr(msg, "alt", 0))
    except Exception:
        return

    _set_status(altitude=round(altitude, 2), last_message_time=time.time())


def _handle_message(msg):
    msg_type = msg.get_type()
    if msg_type == "HEARTBEAT":
        _handle_heartbeat(msg)
    elif msg_type == "SYS_STATUS":
        _handle_sys_status(msg)
    elif msg_type == "BATTERY_STATUS":
        _handle_battery_status(msg)
    elif msg_type == "GPS_RAW_INT":
        _handle_gps_raw_int(msg)
    elif msg_type == "GLOBAL_POSITION_INT":
        _handle_global_position_int(msg)
    elif msg_type == "VFR_HUD":
        _handle_vfr_hud(msg)


def _reader_loop():
    while not _stop_event.is_set():
        with _lock:
            master = _master

        if master is None:
            time.sleep(0.2)
            continue

        try:
            msg = master.recv_match(blocking=True, timeout=1.0)
        except Exception as exc:
            _set_status(connected=False, error=str(exc))
            time.sleep(0.5)
            continue

        if msg is None:
            is_connected()
            continue

        _handle_message(msg)


def _start_reader_thread():
    global _reader_thread

    with _lock:
        if _reader_thread is not None and _reader_thread.is_alive():
            return

        _stop_event.clear()
        _reader_thread = threading.Thread(
            target=_reader_loop,
            name="adti-autonomous-mission-mavlink",
            daemon=True,
        )
        _reader_thread.start()


def connect(timeout=None):
    """Orange Cube MAVLink baglantisini acar ve heartbeat bekler."""
    global _master

    if not PYMAVLINK_AVAILABLE:
        error = f"pymavlink yuklu degil: {_PYMAVLINK_IMPORT_ERROR}"
        _set_status(connected=False, error=error)
        add_log(f"Otonom gorev MAVLink hatasi: {error}")
        return False

    timeout = MAVLINK_HEARTBEAT_TIMEOUT if timeout is None else float(timeout)

    with _lock:
        if _master is not None and is_connected():
            return True

    try:
        master = mavutil.mavlink_connection(
            MAVLINK_PORT,
            baud=MAVLINK_BAUD,
            autoreconnect=True,
        )
        add_log(f"Otonom gorev MAVLink baglaniyor: {MAVLINK_PORT} @ {MAVLINK_BAUD}")

        heartbeat = master.wait_heartbeat(timeout=timeout)
        if heartbeat is None:
            raise TimeoutError("Heartbeat alinamadi")

        with _lock:
            _master = master

        _handle_heartbeat(heartbeat)
        _start_reader_thread()
        add_log("Otonom gorev MAVLink baglandi")
        return True
    except Exception as exc:
        _set_status(connected=False, error=str(exc))
        add_log(f"Otonom gorev MAVLink baglanti hatasi: {exc}")
        return False


def _set_mission_phase(phase, message, error=None, running=None):
    updates = {
        "mission_phase": phase,
        "mission_message": message,
        "mission_error": error,
        "error": error,
    }
    if running is not None:
        updates["mission_running"] = bool(running)
    _set_status(**updates)
    add_log(f"Otonom gorev: {message}" if error is None else f"Otonom gorev hatasi: {message} - {error}")


def _get_master():
    with _lock:
        return _master


def _target_ids(master):
    status = get_status()
    target_system = status.get("target_system") or getattr(master, "target_system", None) or 1
    target_component = status.get("target_component") or getattr(master, "target_component", None) or 1
    return int(target_system), int(target_component)


def _set_mode(mode_name, timeout=8.0):
    mode_name = str(mode_name).upper()
    master = _get_master()
    if master is None:
        return False, "MAVLink master yok"

    try:
        mapping = master.mode_mapping()
        if mode_name not in mapping:
            return False, f"{mode_name} modu bu araçta yok"

        with _command_lock:
            master.set_mode(mapping[mode_name])

        return _wait_until(
            lambda: str(get_status().get("mode", "")).upper() == mode_name,
            timeout=timeout,
            step=0.2,
        ), None
    except Exception as exc:
        return False, str(exc)


def _arm_vehicle(timeout=10.0):
    master = _get_master()
    if master is None:
        return False, "MAVLink master yok"

    try:
        target_system, target_component = _target_ids(master)
        with _command_lock:
            master.mav.command_long_send(
                target_system,
                target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,
                1,
                0,
                0,
                0,
                0,
                0,
                0,
            )

        return _wait_until(
            lambda: bool(get_status().get("armed")),
            timeout=timeout,
            step=0.25,
        ), None
    except Exception as exc:
        return False, str(exc)


def _send_takeoff(altitude_m):
    master = _get_master()
    if master is None:
        return False, "MAVLink master yok"

    try:
        altitude_m = float(altitude_m)
        target_system, target_component = _target_ids(master)
        with _command_lock:
            master.mav.command_long_send(
                target_system,
                target_component,
                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                altitude_m,
            )
        return True, None
    except Exception as exc:
        return False, str(exc)


def _send_mission_start():
    master = _get_master()
    if master is None:
        return False, "MAVLink master yok"

    try:
        target_system, target_component = _target_ids(master)
        with _command_lock:
            master.mav.command_long_send(
                target_system,
                target_component,
                mavutil.mavlink.MAV_CMD_MISSION_START,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            )
        return True, None
    except Exception as exc:
        return False, str(exc)


def _wait_until(predicate, timeout, step=0.25):
    deadline = time.time() + float(timeout)
    while time.time() < deadline:
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(step)
    return False


def _wait_for_takeoff_altitude(target_altitude_m, timeout=90.0):
    target_altitude_m = float(target_altitude_m)
    approach_altitude = max(1.0, target_altitude_m * 0.85)

    def reached():
        altitude = float(get_status().get("altitude") or 0.0)
        _set_status(mission_message=f"Kalkis: {altitude:.1f}/{target_altitude_m:.1f} m")
        return altitude >= approach_altitude

    return _wait_until(reached, timeout=timeout, step=0.5)


def _auto_survey_mission_loop():
    try:
        target_altitude = float(AUTO_TAKEOFF_ALTITUDE_M)

        _set_mission_phase("guided", "GUIDED moda geciliyor", running=True)
        ok, error = _set_mode("GUIDED")
        if not ok:
            raise RuntimeError(error or "GUIDED moda gecilemedi")

        _set_mission_phase("arming", "ARM ediliyor", running=True)
        ok, error = _arm_vehicle()
        if not ok:
            raise RuntimeError(error or "ARM basarisiz")

        _set_mission_phase(
            "takeoff",
            f"{target_altitude:.1f} m irtifaya kalkis komutu gonderiliyor",
            running=True,
        )
        ok, error = _send_takeoff(target_altitude)
        if not ok:
            raise RuntimeError(error or "Takeoff komutu gonderilemedi")

        _set_mission_phase("takeoff_wait", "Hedef irtifaya yaklasmasi bekleniyor", running=True)
        if not _wait_for_takeoff_altitude(target_altitude):
            raise TimeoutError("Takeoff hedef irtifasina zamaninda yaklasamadi")

        _set_mission_phase("auto", "AUTO moda geciliyor", running=True)
        ok, error = _set_mode("AUTO")
        if not ok:
            raise RuntimeError(error or "AUTO moda gecilemedi")

        _set_mission_phase("mission_start", "Mission start komutu gonderiliyor", running=True)
        ok, error = _send_mission_start()
        if not ok:
            raise RuntimeError(error or "Mission start komutu gonderilemedi")

        _set_status(mission_finished_time=time.time())
        _set_mission_phase("started", "Otonom tarama gorevi baslatildi", running=False)
    except Exception as exc:
        _set_status(mission_finished_time=time.time())
        _set_mission_phase("error", "Otonom gorev durdu", error=str(exc), running=False)


def start_auto_survey_mission():
    """Preflight sonrasi GUIDED takeoff + AUTO mission start akisini baslatir."""
    global _mission_thread

    now = time.time()
    with _mission_lock:
        if _mission_thread is not None and _mission_thread.is_alive():
            message = "Otonom gorev zaten calisiyor"
            _set_mission_phase("busy", message, running=True)
            return {"ok": False, "error": message, "status": get_status()}

        last_start = float(_status.get("last_mission_start_time") or 0.0)
        cooldown_left = AUTO_MISSION_RETRIGGER_COOLDOWN_SECONDS - (now - last_start)
        if last_start > 0 and cooldown_left > 0:
            message = f"Tekrar tetikleme beklemede: {cooldown_left:.0f} sn"
            _set_mission_phase("cooldown", message, error=message, running=False)
            return {"ok": False, "error": message, "status": get_status()}

        if not preflight_check():
            return {
                "ok": False,
                "error": get_status().get("preflight_error"),
                "status": get_status(),
            }

        _set_status(
            mission_running=True,
            mission_phase="starting",
            mission_message="Otonom gorev baslatiliyor",
            mission_error=None,
            mission_started_time=now,
            mission_finished_time=0.0,
            last_mission_start_time=now,
        )

        _mission_thread = threading.Thread(
            target=_auto_survey_mission_loop,
            name="adti-auto-survey-mission",
            daemon=True,
        )
        _mission_thread.start()

    add_log("Otonom tarama gorevi thread'i baslatildi")
    return {"ok": True, "status": get_status()}
