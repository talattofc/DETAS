import time
import math
import threading

try:
    from pymavlink import mavutil
except Exception:
    mavutil = None

try:
    import config
except Exception:
    config = None

from services.state import state
from services.landing_sensor_service import update_sharp_distance

try:
    from services.logger_service import add_log
except Exception:
    def add_log(message):
        print("[MAVLINK]", message)


# ============================================================
# AYARLAR
# ============================================================

MAVLINK_PORT = getattr(config, "MAVLINK_PORT", "/dev/ttyAMA4") if config else "/dev/ttyAMA4"
MAVLINK_BAUD = getattr(config, "MAVLINK_BAUD", 57600) if config else 57600

PAN_SERVO_NUMBER = getattr(config, "PAN_SERVO_NUMBER", 9) if config else 9
TILT_SERVO_NUMBER = getattr(config, "TILT_SERVO_NUMBER", 11) if config else 11

PAN_MIN_PWM = 1250
PAN_MAX_PWM = 2600
PAN_CENTER_PWM = 2400

TILT_MIN_PWM = 650
TILT_MAX_PWM = 2000
TILT_CENTER_PWM = 1300

SERVO_STEP_PWM = 100

AUTO_ARM_ON_EARTHQUAKE = True
AUTO_MOTOR_TEST_ON_EARTHQUAKE = False
AUTO_DISARM_AFTER_MOTOR_TEST = False

MOTOR_TEST_THROTTLE_PERCENT = 22
MOTOR_TEST_DURATION_SEC = 1.0
MOTOR_TEST_PAUSE_SEC = 0.5
MOTOR_TEST_MOTOR_COUNT = 4
<<<<<<< HEAD
=======
<<<<<<< HEAD
SHARP_ADC_FIELD = getattr(config, "SHARP_ADC_FIELD", "adc1") if config else "adc1"
=======
>>>>>>> 82cd033 (orange cube entegrasyonu otopilot)
>>>>>>> b896abad72cec15526c5edf83a4468593bc2771f
AUTO_MISSION_SEQUENCE_ENABLED = getattr(config, "AUTO_MISSION_SEQUENCE_ENABLED", True) if config else True
AUTO_MISSION_EARTHQUAKE_CONFIRM_SEC = getattr(config, "AUTO_MISSION_EARTHQUAKE_CONFIRM_SEC", 3.0) if config else 3.0
AUTO_MISSION_EARTHQUAKE_GAP_TOLERANCE_SEC = getattr(config, "AUTO_MISSION_EARTHQUAKE_GAP_TOLERANCE_SEC", 0.8) if config else 0.8
AUTO_MISSION_TAKEOFF_ALTITUDE_M = getattr(config, "AUTO_MISSION_TAKEOFF_ALTITUDE_M", 3.0) if config else 3.0
AUTO_MISSION_TAKEOFF_SETTLE_SEC = getattr(config, "AUTO_MISSION_TAKEOFF_SETTLE_SEC", 8.0) if config else 8.0
AUTO_MISSION_SCAN_DURATION_SEC = getattr(config, "AUTO_MISSION_SCAN_DURATION_SEC", 45.0) if config else 45.0
AUTO_MISSION_SCAN_MIN_ALTITUDE_M = getattr(config, "AUTO_MISSION_SCAN_MIN_ALTITUDE_M", 1.5) if config else 1.5
AUTO_MISSION_LAND_AFTER_SCAN = getattr(config, "AUTO_MISSION_LAND_AFTER_SCAN", True) if config else True
<<<<<<< HEAD
AUTO_MISSION_RTL_ON_STOP = getattr(config, "AUTO_MISSION_RTL_ON_STOP", True) if config else True
=======
<<<<<<< HEAD
=======
AUTO_MISSION_RTL_ON_STOP = getattr(config, "AUTO_MISSION_RTL_ON_STOP", True) if config else True
>>>>>>> 82cd033 (orange cube entegrasyonu otopilot)
>>>>>>> b896abad72cec15526c5edf83a4468593bc2771f


# ============================================================
# GLOBAL DURUM
# ============================================================

_master = None
_master_lock = threading.RLock()
_command_lock = threading.RLock()

_reader_thread_started = False
_auto_mission_thread_started = False
_stop_threads = threading.Event()

_fc_sysid = None
_fc_compid = None

_last_heartbeat_time = 0.0
_last_stream_request_time = 0.0
_last_ack = None
_last_status_text = ""

_auto_event_latched = False
_last_auto_arm_time = 0.0
_last_quake_clear_time = 0.0
_quake_candidate_start_time = 0.0
_quake_last_seen_time = 0.0
_auto_sequence_phase = "idle"
_auto_sequence_started_time = 0.0
_auto_takeoff_sent_time = 0.0
_auto_scan_started_time = 0.0
_auto_landing_started_time = 0.0


# ============================================================
# STATE YARDIMCILARI
# ============================================================

def _state_update(**kwargs):
    try:
        if hasattr(state, "update"):
            state.update(**kwargs)
            return
    except Exception:
        pass

    try:
        for key, value in kwargs.items():
            setattr(state, key, value)
    except Exception:
        pass


def _state_snapshot():
    try:
        if hasattr(state, "snapshot"):
            return state.snapshot()
    except Exception:
        pass

    try:
        if hasattr(state, "to_dict"):
            return state.to_dict()
    except Exception:
        pass

    try:
        return dict(state.__dict__)
    except Exception:
        return {}


def _as_bool(value):
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value > 0

    text = str(value or "").strip().lower()

    return text in [
        "true",
        "1",
        "yes",
        "evet",
        "armed",
        "arm",
        "aktif",
        "bağlı",
        "bagli",
    ]


def _get_float(data, key, default=0.0):
    try:
        return float(data.get(key, default))
    except Exception:
        return default


def _round(value, digits=2):
    try:
        return round(float(value), digits)
    except Exception:
        return 0.0


def _deg(rad):
    try:
        return math.degrees(float(rad))
    except Exception:
        return 0.0


def _set_arm_state(armed, source="heartbeat"):
    armed = bool(armed)

    _state_update(
        cube_armed=armed,
        armed=armed,
        is_armed=armed,
        arm=armed,
        cube_arm_status="ARMED" if armed else "DISARMED",
        arm_status="ARMED" if armed else "DISARMED",
        cube_arm_source=source,
        cube_arm_last_update=time.time()
    )


# ============================================================
# MAVLINK BAĞLANTI
# ============================================================

def connect_mavlink():
    global _master, _last_heartbeat_time

    if mavutil is None:
        raise RuntimeError("pymavlink yüklü değil")

    with _master_lock:
        if _master is not None:
            return _master

        add_log(f"MAVLink bağlantısı açılıyor: {MAVLINK_PORT} @ {MAVLINK_BAUD}")

        master = mavutil.mavlink_connection(
            MAVLINK_PORT,
            baud=MAVLINK_BAUD,
            autoreconnect=True,
            source_system=255,
            source_component=190
        )

        master.wait_heartbeat(timeout=15)

        _master = master
        _last_heartbeat_time = time.time()

        _state_update(
            cube_connected=True,
            mavlink_connected=True,
            cube_last_heartbeat_age=0.0
        )

        add_log("MAVLink bağlantısı hazır")

        request_mavlink_data_streams(master)

        return _master


def get_master():
    with _master_lock:
        if _master is None:
            return connect_mavlink()

        return _master


def close_mavlink():
    global _master

    with _master_lock:
        try:
            if _master is not None:
                _master.close()
        except Exception:
            pass

        _master = None

    _state_update(
        cube_connected=False,
        mavlink_connected=False
    )


def is_connected():
    return _master is not None


def _target_ids(master=None):
    if master is None:
        master = get_master()

    if _fc_sysid is not None:
        return int(_fc_sysid), int(_fc_compid or 1)

    target_system = getattr(master, "target_system", 1) or 1
    return int(target_system), 1


# ============================================================
# MAVLINK VERİ AKIŞI
# ============================================================

def request_mavlink_data_streams(master=None):
    if mavutil is None:
        return False

    try:
        if master is None:
            master = get_master()

        target_system, target_component = _target_ids(master)

        streams = [
            mavutil.mavlink.MAV_DATA_STREAM_ALL,
            mavutil.mavlink.MAV_DATA_STREAM_EXTENDED_STATUS,
            mavutil.mavlink.MAV_DATA_STREAM_POSITION,
            mavutil.mavlink.MAV_DATA_STREAM_EXTRA1,
            mavutil.mavlink.MAV_DATA_STREAM_EXTRA2,
            mavutil.mavlink.MAV_DATA_STREAM_EXTRA3,
            mavutil.mavlink.MAV_DATA_STREAM_RC_CHANNELS,
        ]

        for stream_id in streams:
            master.mav.request_data_stream_send(
                target_system,
                target_component,
                stream_id,
                5,
                1
            )
            time.sleep(0.02)

        message_rates = {
            mavutil.mavlink.MAVLINK_MSG_ID_SYS_STATUS: 2,
            mavutil.mavlink.MAVLINK_MSG_ID_BATTERY_STATUS: 2,
            mavutil.mavlink.MAVLINK_MSG_ID_GPS_RAW_INT: 2,
            mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT: 5,
            mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE: 10,
            mavutil.mavlink.MAVLINK_MSG_ID_VFR_HUD: 5,
            mavutil.mavlink.MAVLINK_MSG_ID_RC_CHANNELS: 2,
        }

        for const_name, hz in (
            ("MAVLINK_MSG_ID_DISTANCE_SENSOR", 10),
            ("MAVLINK_MSG_ID_RANGEFINDER", 10),
            ("MAVLINK_MSG_ID_RAW_IMU", 2),
            ("MAVLINK_MSG_ID_SCALED_IMU2", 2),
        ):
            msg_id = getattr(mavutil.mavlink, const_name, None)
            if msg_id is not None:
                message_rates[msg_id] = hz

        for msg_id, hz in message_rates.items():
            interval_us = int(1_000_000 / hz)

            master.mav.command_long_send(
                target_system,
                target_component,
                mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                0,
                msg_id,
                interval_us,
                0,
                0,
                0,
                0,
                0
            )
            time.sleep(0.02)

        add_log("MAVLink veri akışı istendi")
        return True

    except Exception as e:
        add_log(f"MAVLink veri akışı isteme hatası: {e}")
        return False


# ============================================================
# HEARTBEAT FİLTRESİ
# ============================================================

def _is_flight_controller_heartbeat(msg):
    """
    ARM durumunu sadece gerçek uçuş kontrolcüsü heartbeat mesajı günceller.
    Mission Planner / GCS / companion / kamera / gimbal heartbeat mesajları yok sayılır.
    """
    global _fc_sysid, _fc_compid

    try:
        msg_type = int(msg.type)
    except Exception:
        msg_type = None

    try:
        autopilot = int(msg.autopilot)
    except Exception:
        autopilot = None

    try:
        sysid = int(msg.get_srcSystem())
        compid = int(msg.get_srcComponent())
    except Exception:
        sysid = None
        compid = None

    try:
        if msg_type == mavutil.mavlink.MAV_TYPE_GCS:
            return False
    except Exception:
        pass

    try:
        if autopilot == mavutil.mavlink.MAV_AUTOPILOT_INVALID:
            return False
    except Exception:
        pass

    # Autopilot component normalde 1'dir.
    if compid != 1:
        return False

    # İlk doğru heartbeat geldiğinde flight controller kaynağını kilitle.
    if _fc_sysid is None:
        _fc_sysid = sysid
        _fc_compid = compid

        _state_update(
            cube_heartbeat_system=sysid,
            cube_heartbeat_component=compid
        )

        add_log(f"Flight controller heartbeat kaynağı kilitlendi: sys={sysid}, comp={compid}")

        return True

    # Sonrasında sadece aynı kaynaktan gelen heartbeat kabul edilir.
    return sysid == _fc_sysid and compid == _fc_compid


# ============================================================
# MESAJ PARSE
# ============================================================

def _handle_heartbeat(msg):
    global _last_heartbeat_time

    if not _is_flight_controller_heartbeat(msg):
        return

    _last_heartbeat_time = time.time()

    try:
        armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
    except Exception:
        armed = False

    try:
        mode = mavutil.mode_string_v10(msg)
    except Exception:
        mode = "-"

    _set_arm_state(armed, source="heartbeat")

    _state_update(
        cube_connected=True,
        mavlink_connected=True,
        cube_mode=mode,
        mode=mode,
        cube_last_heartbeat_age=0.0
    )


def _handle_sys_status(msg):
    try:
        voltage_mv = int(getattr(msg, "voltage_battery", 0))
    except Exception:
        voltage_mv = 0

    try:
        current_ca = int(getattr(msg, "current_battery", 0))
    except Exception:
        current_ca = 0

    voltage = 0.0
    current = 0.0

    if voltage_mv not in [0, 65535]:
        voltage = voltage_mv / 1000.0

    if current_ca not in [-1, 0, 65535]:
        current = current_ca / 100.0

    updates = {}

    if voltage > 0:
        updates["cube_battery_voltage"] = _round(voltage, 2)
        updates["battery_voltage"] = _round(voltage, 2)

    if current > 0:
        updates["cube_battery_current"] = _round(current, 2)
        updates["battery_current"] = _round(current, 2)

    if updates:
        _state_update(**updates)


def _handle_battery_status(msg):
    voltage = 0.0

    try:
        cells = [int(v) for v in list(msg.voltages) if int(v) not in [0, 65535]]
        if cells:
            voltage = sum(cells) / 1000.0
    except Exception:
        voltage = 0.0

    try:
        current_ca = int(getattr(msg, "current_battery", 0))
    except Exception:
        current_ca = 0

    current = 0.0

    if current_ca not in [-1, 0, 65535]:
        current = current_ca / 100.0

    updates = {}

    if voltage > 0:
        updates["cube_battery_voltage"] = _round(voltage, 2)
        updates["battery_voltage"] = _round(voltage, 2)

    if current > 0:
        updates["cube_battery_current"] = _round(current, 2)
        updates["battery_current"] = _round(current, 2)

    if updates:
        _state_update(**updates)


def _handle_gps_raw_int(msg):
    try:
        gps_fix = int(msg.fix_type)
    except Exception:
        gps_fix = 0

    try:
        satellites = int(msg.satellites_visible)
    except Exception:
        satellites = 0

    try:
        eph = float(msg.eph) / 100.0
    except Exception:
        eph = 0.0

    updates = {
        "cube_gps_fix": gps_fix,
        "gps_fix": gps_fix,
        "cube_satellites": satellites,
        "satellites": satellites,
        "cube_eph": _round(eph, 2),
    }

    try:
        if msg.lat != 0 and msg.lon != 0:
            lat = msg.lat / 1e7
            lon = msg.lon / 1e7
            updates["cube_lat"] = lat
            updates["cube_lng"] = lon
            updates["cube_latitude"] = lat
            updates["cube_longitude"] = lon
            updates["lat"] = lat
            updates["lng"] = lon
    except Exception:
        pass

    _state_update(**updates)


def _handle_global_position_int(msg):
    updates = {}

    try:
        alt = msg.relative_alt / 1000.0
        updates["cube_altitude"] = _round(alt, 2)
        updates["altitude"] = _round(alt, 2)
    except Exception:
        pass

    try:
        if msg.lat != 0 and msg.lon != 0:
            lat = msg.lat / 1e7
            lon = msg.lon / 1e7
            updates["cube_lat"] = lat
            updates["cube_lng"] = lon
            updates["cube_latitude"] = lat
            updates["cube_longitude"] = lon
            updates["lat"] = lat
            updates["lng"] = lon
    except Exception:
        pass

    try:
        vx = msg.vx / 100.0
        vy = msg.vy / 100.0
        speed = math.sqrt(vx * vx + vy * vy)
        updates["cube_groundspeed"] = _round(speed, 2)
        updates["groundspeed"] = _round(speed, 2)
    except Exception:
        pass

    try:
        if msg.hdg not in [65535, -1]:
            heading = msg.hdg / 100.0
            updates["cube_heading"] = _round(heading, 1)
            updates["heading"] = _round(heading, 1)
    except Exception:
        pass

    if updates:
        _state_update(**updates)


def _handle_attitude(msg):
    roll = _round(_deg(getattr(msg, "roll", 0)), 2)
    pitch = _round(_deg(getattr(msg, "pitch", 0)), 2)
    yaw = _round(_deg(getattr(msg, "yaw", 0)), 2)

    _state_update(
        cube_roll=roll,
        cube_pitch=pitch,
        cube_yaw=yaw,
        roll=roll,
        pitch=pitch,
        yaw=yaw
    )


def _handle_vfr_hud(msg):
    _state_update(
        cube_altitude=_round(getattr(msg, "alt", 0), 2),
        altitude=_round(getattr(msg, "alt", 0), 2),
        cube_groundspeed=_round(getattr(msg, "groundspeed", 0), 2),
        groundspeed=_round(getattr(msg, "groundspeed", 0), 2),
        cube_heading=_round(getattr(msg, "heading", 0), 1),
        heading=_round(getattr(msg, "heading", 0), 1),
        cube_throttle=_round(getattr(msg, "throttle", 0), 1),
        throttle=_round(getattr(msg, "throttle", 0), 1)
    )


def _handle_distance_sensor(msg):
    try:
        current_cm = float(getattr(msg, "current_distance"))
    except Exception:
        return

    if current_cm <= 0:
        return

    update_sharp_distance(distance_cm=current_cm, source="DISTANCE_SENSOR")


def _handle_rangefinder(msg):
    try:
        distance_m = float(getattr(msg, "distance"))
    except Exception:
        return

    if distance_m <= 0:
        return

    voltage = None
    try:
        voltage = float(getattr(msg, "voltage"))
    except Exception:
        voltage = None

    update_sharp_distance(
        distance_cm=distance_m * 100.0,
        voltage=voltage,
        source="RANGEFINDER",
    )


def _handle_adc_like(msg):
    fields = {}
    try:
        fields = msg.to_dict()
    except Exception:
        for key in ("adc1", "adc2", "adc3", "adc4", "adc5", "adc6", "analog1", "analog2"):
            if hasattr(msg, key):
                fields[key] = getattr(msg, key)

    if not fields:
        return

    raw = None
    for key in (SHARP_ADC_FIELD, "adc1", "adc2", "analog1", "analog2"):
        if key in fields:
            raw = fields[key]
            break

    if raw is None:
        return

    update_sharp_distance(raw=raw, source=msg.get_type())


def _handle_rc_channels(msg):
    updates = {}

    for i in range(1, 9):
        key = f"chan{i}_raw"
        if hasattr(msg, key):
            updates[f"rc_ch{i}"] = getattr(msg, key)

    if updates:
        _state_update(**updates)


def _handle_statustext(msg):
    global _last_status_text

    try:
        text = str(msg.text)
    except Exception:
        text = str(msg)

    _last_status_text = text

    _state_update(
        cube_last_status_text=text,
        cube_status_text=text
    )

    add_log(f"Cube: {text}")


def _handle_command_ack(msg):
    global _last_ack

    try:
        command = int(msg.command)
        result = int(msg.result)
    except Exception:
        return

    _last_ack = {
        "command": command,
        "result": result,
        "time": time.time()
    }

    _state_update(
        cube_last_command=command,
        cube_last_command_result=result
    )


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
    elif msg_type == "ATTITUDE":
        _handle_attitude(msg)
    elif msg_type == "VFR_HUD":
        _handle_vfr_hud(msg)
    elif msg_type == "DISTANCE_SENSOR":
        _handle_distance_sensor(msg)
    elif msg_type == "RANGEFINDER":
        _handle_rangefinder(msg)
    elif msg_type in ("RAW_IMU", "SCALED_IMU2", "ADC_CHANNELS", "ANALOG_DATA"):
        _handle_adc_like(msg)
    elif msg_type == "RC_CHANNELS":
        _handle_rc_channels(msg)
    elif msg_type == "STATUSTEXT":
        _handle_statustext(msg)
    elif msg_type == "COMMAND_ACK":
        _handle_command_ack(msg)


# ============================================================
# OKUMA THREAD
# ============================================================

def mavlink_reader_loop():
    global _last_stream_request_time

    add_log("MAVLink okuma thread'i başlatıldı")

    while not _stop_threads.is_set():
        try:
            master = get_master()

            msg = master.recv_match(blocking=True, timeout=1)

            if msg is not None:
                _handle_message(msg)

            now = time.time()

            if now - _last_stream_request_time > 8:
                request_mavlink_data_streams(master)
                _last_stream_request_time = now

            age = now - _last_heartbeat_time if _last_heartbeat_time else 999

            _state_update(
                cube_last_heartbeat_age=_round(age, 1),
                cube_connected=(age < 5),
                mavlink_connected=(age < 5)
            )

            if age >= 10:
                add_log("MAVLink heartbeat gecikti, bağlantı yenileniyor")
                close_mavlink()
                time.sleep(1)

        except Exception as e:
            add_log(f"MAVLink okuma hatası: {e}")
            close_mavlink()
            time.sleep(2)


def start_mavlink_thread():
    global _reader_thread_started

    if _reader_thread_started:
        return

    t = threading.Thread(target=mavlink_reader_loop, daemon=True)
    t.start()

    _reader_thread_started = True


# ============================================================
# ACK
# ============================================================

def _clear_ack():
    global _last_ack
    _last_ack = None


def _wait_ack(command, timeout=3.0):
    start = time.time()

    while time.time() - start < timeout:
        ack = dict(_last_ack) if _last_ack else None

        if ack and ack.get("command") == command:
            return ack

        time.sleep(0.05)

    return None


# ============================================================
# ARM / DISARM / MODE
# ============================================================

def _cube_connected():
    data = _state_snapshot()
    return _as_bool(data.get("cube_connected") or data.get("mavlink_connected"))


def _active_mission_phase():
    data = _state_snapshot()
    phase = str(data.get("auto_sequence_phase", _auto_sequence_phase) or "").lower()
    status = str(data.get("mission_status", "") or "").upper()

<<<<<<< HEAD
    if phase in ("confirmed", "takeoff", "scan", "landing", "mission", "auto", "mission_start"):
=======
    if phase in ("confirmed", "takeoff", "scan", "landing"):
>>>>>>> b896abad72cec15526c5edf83a4468593bc2771f
        return True
    if _as_bool(data.get("auto_landing_active")):
        return True
    return any(token in status for token in ("OTONOM", "TARAMA", "KALKIŞ", "INIS", "İNİŞ"))


def _in_air_for_disarm_guard():
    data = _state_snapshot()
    altitude = _get_float(data, "cube_altitude", 0.0)
    throttle = _get_float(data, "cube_throttle", 0.0)

    if _active_mission_phase():
        return True
    if altitude > 0.5:
        return True
    if _cube_armed() and throttle > 5:
        return True
    return False


def send_arm_command(arm=True):
    if mavutil is None:
        return {"ok": False, "error": "pymavlink yüklü değil"}

    if not arm and _in_air_for_disarm_guard():
        message = "Havadayken DISARM engellendi"
        _state_update(mission_status=message)
        add_log(message)
        return {"ok": False, "arm": False, "error": message, "blocked": True}

    with _command_lock:
        try:
            master = get_master()
            target_system, target_component = _target_ids(master)

            _clear_ack()

            master.mav.command_long_send(
                target_system,
                target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,
                1 if arm else 0,
                0,
                0,
                0,
                0,
                0,
                0
            )

            add_log("ARM komutu gönderildi" if arm else "DISARM komutu gönderildi")

            ack = _wait_ack(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, timeout=3.0)
            result = ack.get("result") if ack else None

            if result == 0:
                _set_arm_state(bool(arm), source="command_ack")

            _state_update(
                cube_last_arm_command="ARM" if arm else "DISARM",
                cube_arm_command_sent=bool(arm)
            )

            return {
                "ok": result == 0,
                "arm": bool(arm),
                "ack_result": result,
                "message": "ARM komutu gönderildi" if arm else "DISARM komutu gönderildi"
            }

        except Exception as e:
            add_log(f"ARM/DISARM komutu hatası: {e}")
            return {"ok": False, "arm": bool(arm), "error": str(e)}


def send_disarm_command():
    return send_arm_command(False)


def send_rtl_command():
    result = set_mode("RTL")
    if result.get("ok"):
        _state_update(
            mission_status="Görev iptal edildi, RTL başlatıldı",
            auto_sequence_phase="rtl",
        )
        add_log("Görev iptal edildi, RTL başlatıldı")
    return result


def set_mode(mode_name):
    if mavutil is None:
        return {"ok": False, "error": "pymavlink yüklü değil"}

    mode_name = str(mode_name).upper()

    with _command_lock:
        try:
            master = get_master()
            mapping = master.mode_mapping()

            if mode_name not in mapping:
                return {
                    "ok": False,
                    "error": f"Mod bulunamadı: {mode_name}",
                    "available_modes": list(mapping.keys())
                }

            mode_id = mapping[mode_name]
            master.set_mode(mode_id)

            add_log(f"Uçuş modu komutu gönderildi: {mode_name}")

            return {"ok": True, "mode": mode_name, "mode_id": mode_id}

        except Exception as e:
            add_log(f"Mod değiştirme hatası: {e}")
            return {"ok": False, "error": str(e)}


def set_stabilize_mode():
    return set_mode("STABILIZE")


def set_alt_hold_mode():
    return set_mode("ALT_HOLD")


def set_loiter_mode():
    return set_mode("LOITER")


def send_guided_descent_velocity(vz_down_mps):
    """GUIDED modda asagi yonlu hiz istegi gonderir; pozitif z NED'de asagidir."""
    if mavutil is None:
        return {"ok": False, "error": "pymavlink yüklü değil"}

    try:
        vz_down_mps = max(0.0, min(float(vz_down_mps), 1.5))
    except Exception:
        vz_down_mps = 0.0

    with _command_lock:
        try:
            master = get_master()
            target_system, target_component = _target_ids(master)
            mavlink = mavutil.mavlink

            type_mask = (
                getattr(mavlink, "POSITION_TARGET_TYPEMASK_X_IGNORE", 1)
                | getattr(mavlink, "POSITION_TARGET_TYPEMASK_Y_IGNORE", 2)
                | getattr(mavlink, "POSITION_TARGET_TYPEMASK_Z_IGNORE", 4)
                | getattr(mavlink, "POSITION_TARGET_TYPEMASK_AX_IGNORE", 64)
                | getattr(mavlink, "POSITION_TARGET_TYPEMASK_AY_IGNORE", 128)
                | getattr(mavlink, "POSITION_TARGET_TYPEMASK_AZ_IGNORE", 256)
                | getattr(mavlink, "POSITION_TARGET_TYPEMASK_YAW_IGNORE", 1024)
                | getattr(mavlink, "POSITION_TARGET_TYPEMASK_YAW_RATE_IGNORE", 2048)
            )
            frame = getattr(mavlink, "MAV_FRAME_BODY_NED", mavlink.MAV_FRAME_LOCAL_NED)

            master.mav.set_position_target_local_ned_send(
                int(time.time() * 1000) & 0xFFFFFFFF,
                target_system,
                target_component,
                frame,
                type_mask,
                0,
                0,
                0,
                0,
                0,
                vz_down_mps,
                0,
                0,
                0,
                0,
                0,
            )
            return {"ok": True, "vz_down_mps": vz_down_mps}
        except Exception as e:
            add_log(f"GUIDED inis hiz komutu hatasi: {e}")
            return {"ok": False, "error": str(e), "vz_down_mps": vz_down_mps}


def stop_guided_velocity():
    return send_guided_descent_velocity(0.0)


def send_takeoff_command(altitude_m=None):
    if mavutil is None:
        return {"ok": False, "error": "pymavlink yüklü değil"}

    try:
        altitude_m = float(altitude_m if altitude_m is not None else AUTO_MISSION_TAKEOFF_ALTITUDE_M)
    except Exception:
        altitude_m = AUTO_MISSION_TAKEOFF_ALTITUDE_M

    altitude_m = max(1.0, min(altitude_m, 20.0))

    with _command_lock:
        try:
            master = get_master()
            target_system, target_component = _target_ids(master)
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
            add_log(f"Otonom kalkis komutu gonderildi: {altitude_m:.1f} m")
            return {"ok": True, "altitude_m": altitude_m}
        except Exception as e:
            add_log(f"Otonom kalkis komutu hatasi: {e}")
            return {"ok": False, "error": str(e), "altitude_m": altitude_m}


<<<<<<< HEAD
def send_mission_start_command():
    if mavutil is None:
        return {"ok": False, "error": "pymavlink yüklü değil"}

    with _command_lock:
        try:
            master = get_master()
            target_system, target_component = _target_ids(master)
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
            add_log("AUTO mission start komutu gonderildi")
            return {"ok": True, "message": "AUTO mission start komutu gonderildi"}
        except Exception as e:
            add_log(f"AUTO mission start komutu hatasi: {e}")
            return {"ok": False, "error": str(e)}


=======
>>>>>>> b896abad72cec15526c5edf83a4468593bc2771f
# ============================================================
# SERVO
# ============================================================

def _clamp_pwm(value, min_pwm, max_pwm, fallback):
    try:
        value = int(value)
    except Exception:
        value = fallback

    return max(min_pwm, min(max_pwm, value))


def send_servo_pwm(servo_number, pwm):
    if mavutil is None:
        return {"ok": False, "error": "pymavlink yüklü değil"}

    servo_number = int(servo_number)

    if servo_number == PAN_SERVO_NUMBER:
        pwm = _clamp_pwm(pwm, PAN_MIN_PWM, PAN_MAX_PWM, PAN_CENTER_PWM)
    elif servo_number == TILT_SERVO_NUMBER:
        pwm = _clamp_pwm(pwm, TILT_MIN_PWM, TILT_MAX_PWM, TILT_CENTER_PWM)
    else:
        pwm = _clamp_pwm(pwm, 800, 2200, 1500)

    with _command_lock:
        try:
            master = get_master()
            target_system, target_component = _target_ids(master)

            master.mav.command_long_send(
                target_system,
                target_component,
                mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
                0,
                servo_number,
                pwm,
                0,
                0,
                0,
                0,
                0
            )

            if servo_number == PAN_SERVO_NUMBER:
                _state_update(servo_pan=pwm, pan_pwm=pwm)
            elif servo_number == TILT_SERVO_NUMBER:
                _state_update(servo_tilt=pwm, tilt_pwm=pwm)

            return {"ok": True, "servo_number": servo_number, "pwm": pwm}

        except Exception as e:
            add_log(f"Servo PWM hatası: {e}")
            return {"ok": False, "servo_number": servo_number, "pwm": pwm, "error": str(e)}


# ============================================================
# MOTOR TEST
# ============================================================

def run_motor_test(throttle_percent=None, duration=None):
    if mavutil is None:
        return {"ok": False, "error": "pymavlink yüklü değil"}

    throttle_percent = int(throttle_percent or MOTOR_TEST_THROTTLE_PERCENT)
    duration = float(duration or MOTOR_TEST_DURATION_SEC)

    throttle_percent = max(5, min(35, throttle_percent))

    with _command_lock:
        try:
            master = get_master()
            target_system, target_component = _target_ids(master)

            add_log(f"Manuel motor test başlatıldı: %{throttle_percent}")

            for motor_id in range(1, MOTOR_TEST_MOTOR_COUNT + 1):
                master.mav.command_long_send(
                    target_system,
                    target_component,
                    mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST,
                    0,
                    motor_id,
                    0,
                    throttle_percent,
                    duration,
                    0,
                    0,
                    0
                )

                add_log(f"Motor test: motor {motor_id}")
                time.sleep(duration + MOTOR_TEST_PAUSE_SEC)

            add_log("Manuel motor test tamamlandı")

            return {
                "ok": True,
                "message": "Motor test tamamlandı",
                "throttle_percent": throttle_percent
            }

        except Exception as e:
            add_log(f"Motor test hatası: {e}")
            return {"ok": False, "error": str(e)}


# ============================================================
# DEPREM SONRASI OTOMATİK ARM
# ============================================================

def _quake_active():
    data = _state_snapshot()

    movement = _get_float(data, "movement", 0.0)
    threshold = _get_float(data, "threshold", 1.5)

    if movement >= threshold:
        return True

    for key in [
        "deprem",
        "earthquake",
        "quake_detected",
        "earthquake_detected",
        "alarm",
        "sarsinti_alarm",
    ]:
        if key in data and _as_bool(data.get(key)):
            return True

    return False


def _cube_armed():
    data = _state_snapshot()

    if "cube_armed" in data:
        return _as_bool(data.get("cube_armed"))

    if "armed" in data:
        return _as_bool(data.get("armed"))

    status = str(data.get("cube_arm_status", "")).upper()

    return status == "ARMED"


def _set_auto_sequence_phase(phase, status=None, error=None):
    global _auto_sequence_phase

    _auto_sequence_phase = phase
    _state_update(
        auto_sequence_phase=phase,
        auto_sequence_error=error,
        mission_status=status or phase,
    )


def _quake_confirmed(quake, now):
    global _quake_candidate_start_time, _quake_last_seen_time

    if quake:
        _quake_last_seen_time = now
        if _quake_candidate_start_time <= 0:
            _quake_candidate_start_time = now
            _state_update(mission_status="DEPREM DOĞRULANIYOR")
        return (now - _quake_candidate_start_time) >= float(AUTO_MISSION_EARTHQUAKE_CONFIRM_SEC)

    if _quake_last_seen_time and (now - _quake_last_seen_time) <= float(AUTO_MISSION_EARTHQUAKE_GAP_TOLERANCE_SEC):
        return (now - _quake_candidate_start_time) >= float(AUTO_MISSION_EARTHQUAKE_CONFIRM_SEC)

    _quake_candidate_start_time = 0.0
    _quake_last_seen_time = 0.0
    return False


def _start_servo_scan_for_mission():
    try:
        from services import servo_service

        return servo_service.servo_scan()
    except Exception as exc:
        add_log(f"Otonom tarama baslatma hatasi: {exc}")
        return {"ok": False, "error": str(exc)}


def _stop_servo_scan_for_mission():
    try:
        from services import servo_service

        return servo_service.servo_stop()
    except Exception as exc:
        add_log(f"Otonom tarama durdurma hatasi: {exc}")
        return {"ok": False, "error": str(exc)}


def _start_auto_landing_for_mission():
    try:
        from services.auto_landing_service import start_auto_landing

        return start_auto_landing()
    except Exception as exc:
        add_log(f"Otonom inis baslatma hatasi: {exc}")
        return {"ok": False, "error": str(exc)}


def _stop_auto_landing_for_mission():
    try:
        from services.auto_landing_service import stop_auto_landing

        return stop_auto_landing()
    except Exception:
        return {"ok": False}


def _start_autonomous_takeoff(now):
    global _auto_takeoff_sent_time, _auto_sequence_started_time

    _auto_sequence_started_time = now
    _state_update(
        auto_sequence_started_time=now,
        auto_mission_enabled=True,
        auto_mission_stopped=False,
<<<<<<< HEAD
        mission_status="AUTO GÖREV HAZIRLANIYOR",
    )

    mode_result = set_mode("AUTO")
    if not mode_result.get("ok"):
        _set_auto_sequence_phase("error", "AUTO MOD HATASI", mode_result.get("error"))
        add_log(f"Auto gorev durdu: {mode_result}")
=======
        mission_status="OTONOM KALKIŞ HAZIRLANIYOR",
    )

    mode_result = set_mode("GUIDED")
    if not mode_result.get("ok"):
        _set_auto_sequence_phase("error", "GUIDED MOD HATASI", mode_result.get("error"))
        add_log(f"Otonom kalkis durdu: {mode_result}")
>>>>>>> b896abad72cec15526c5edf83a4468593bc2771f
        return False

    if not _cube_armed():
        arm_result = send_arm_command(True)
        if not arm_result.get("ok"):
            _set_auto_sequence_phase("error", "ARM HATASI", arm_result.get("error") or str(arm_result))
<<<<<<< HEAD
            add_log(f"Auto gorev ARM hatasi: {arm_result}")
            return False

    mission_result = send_mission_start_command()
    if not mission_result.get("ok"):
        _set_auto_sequence_phase("error", "MISSION START HATASI", mission_result.get("error"))
        return False

    _auto_takeoff_sent_time = now
    _set_auto_sequence_phase("mission", "AUTO GÖREV BAŞLATILDI")
=======
            add_log(f"Otonom kalkis ARM hatasi: {arm_result}")
            return False

    takeoff_result = send_takeoff_command(AUTO_MISSION_TAKEOFF_ALTITUDE_M)
    if not takeoff_result.get("ok"):
        _set_auto_sequence_phase("error", "KALKIŞ HATASI", takeoff_result.get("error"))
        return False

    _auto_takeoff_sent_time = now
    _set_auto_sequence_phase("takeoff", "OTONOM KALKIŞ")
>>>>>>> b896abad72cec15526c5edf83a4468593bc2771f
    return True


def _run_auto_sequence(now):
    global _auto_scan_started_time, _auto_landing_started_time

    data = _state_snapshot()
    altitude = _get_float(data, "cube_altitude", 0.0)

    if _auto_sequence_phase == "takeoff":
        settled = (now - _auto_takeoff_sent_time) >= float(AUTO_MISSION_TAKEOFF_SETTLE_SEC)
        high_enough = altitude >= float(AUTO_MISSION_SCAN_MIN_ALTITUDE_M)

        if settled or high_enough:
            result = _start_servo_scan_for_mission()
            _auto_scan_started_time = now
            _set_auto_sequence_phase("scan", "ŞERİT TARAMA")
            add_log(f"Otonom serit tarama basladi: {result}")
        return

    if _auto_sequence_phase == "scan":
        elapsed = now - _auto_scan_started_time
        _state_update(mission_status=f"ŞERİT TARAMA {elapsed:.0f}s")

        if elapsed >= float(AUTO_MISSION_SCAN_DURATION_SEC):
            _stop_servo_scan_for_mission()

            if AUTO_MISSION_LAND_AFTER_SCAN:
                result = _start_auto_landing_for_mission()
                _auto_landing_started_time = now
                _set_auto_sequence_phase("landing", "OTONOM İNİŞ")
                add_log(f"Otonom inis basladi: {result}")
            else:
                _set_auto_sequence_phase("complete", "TARAMA TAMAMLANDI")
        return

    if _auto_sequence_phase == "landing":
        landing_active = bool(data.get("auto_landing_active"))
        landing_status = str(data.get("auto_landing_status") or "Otonom iniş")
        _state_update(mission_status=f"OTONOM İNİŞ - {landing_status}")

        if not landing_active and (now - _auto_landing_started_time) > 2.0:
            _set_auto_sequence_phase("complete", "GÖREV TAMAMLANDI")


def auto_mission_loop():
    global _auto_event_latched, _last_auto_arm_time, _last_quake_clear_time

    add_log("Otomatik deprem görev thread'i başlatıldı")

    while not _stop_threads.is_set():
        try:
            quake = _quake_active()
            armed = _cube_armed()
            now = time.time()

            if AUTO_MISSION_SEQUENCE_ENABLED and _auto_sequence_phase in ("takeoff", "scan", "landing"):
                _run_auto_sequence(now)
                time.sleep(0.4)
                continue

            confirmed = _quake_confirmed(quake, now)

            if confirmed:
                _last_quake_clear_time = 0.0

                first_trigger = not _auto_event_latched
                retry_allowed = (not armed) and (now - _last_auto_arm_time > 8)

                if AUTO_MISSION_SEQUENCE_ENABLED and first_trigger:
                    _auto_event_latched = True
                    _last_auto_arm_time = now
                    _set_auto_sequence_phase("confirmed", "DEPREM DOĞRULANDI")
                    add_log("Deprem doğrulandı, otonom görev başlıyor")
                    _start_autonomous_takeoff(now)
                elif AUTO_ARM_ON_EARTHQUAKE and (first_trigger or retry_allowed):
                    result = send_arm_command(True)
                    _last_auto_arm_time = now
                    _auto_event_latched = True

                    _state_update(
                        auto_arm_sent=True,
                        auto_mission_enabled=True,
                        auto_mission_stopped=False,
                        mission_status="ARM KOMUTU GÖNDERİLDİ"
                    )

                    add_log(f"Deprem tetikleme ARM sonucu: {result}")

            else:
                if _auto_event_latched:
                    if _last_quake_clear_time == 0.0:
                        _last_quake_clear_time = now

                    if now - _last_quake_clear_time >= 2.0:
                        if _auto_sequence_phase in ("idle", "confirmed", "complete", "error"):
                            _auto_event_latched = False
                            _state_update(auto_arm_sent=False)
                            add_log("Deprem tetikleme sistemi tekrar hazır")

            time.sleep(0.4)

        except Exception as e:
            add_log(f"Otomatik deprem ARM hatası: {e}")
            time.sleep(1)


def start_auto_mission_thread():
    global _auto_mission_thread_started

    if _auto_mission_thread_started:
        return

    t = threading.Thread(target=auto_mission_loop, daemon=True)
    t.start()

    _auto_mission_thread_started = True


# ============================================================
# PUBLIC API - APP.PY / ROUTES UYUMLULUĞU
# ============================================================

def start_service():
    start_mavlink_thread()
    start_auto_mission_thread()


def stop_service():
    _stop_threads.set()
    close_mavlink()


def mission_arm():
    return send_arm_command(True)


def mission_stop():
    _stop_servo_scan_for_mission()
    _stop_auto_landing_for_mission()
<<<<<<< HEAD
=======
<<<<<<< HEAD
    _state_update(
        auto_mission_stopped=True,
        auto_sequence_phase="stopped",
        mission_status="DURDURULDU",
    )
    return send_arm_command(False)
=======
>>>>>>> b896abad72cec15526c5edf83a4468593bc2771f

    rtl_result = None
    mission_active = _active_mission_phase()
    should_rtl = AUTO_MISSION_RTL_ON_STOP and _cube_connected() and (mission_active or _cube_armed())
    if should_rtl:
        rtl_result = send_rtl_command()

    status = "Görev iptal edildi, RTL başlatıldı" if should_rtl and rtl_result and rtl_result.get("ok") else "DURDURULDU"
    _state_update(
        auto_mission_stopped=True,
        auto_sequence_phase="stopped",
        mission_status=status,
    )
    return {
        "ok": True if rtl_result is None else bool(rtl_result.get("ok")),
        "message": status,
        "rtl_sent": bool(rtl_result and rtl_result.get("ok")),
        "rtl_result": rtl_result,
    }
<<<<<<< HEAD
=======
>>>>>>> 82cd033 (orange cube entegrasyonu otopilot)
>>>>>>> b896abad72cec15526c5edf83a4468593bc2771f


def mission_disarm():
    return send_arm_command(False)


def mission_reset():
    global _auto_event_latched, _last_auto_arm_time, _last_quake_clear_time
    global _quake_candidate_start_time, _quake_last_seen_time
    global _auto_sequence_phase, _auto_sequence_started_time, _auto_takeoff_sent_time
    global _auto_scan_started_time, _auto_landing_started_time

    _auto_event_latched = False
    _last_auto_arm_time = 0.0
    _last_quake_clear_time = 0.0
    _quake_candidate_start_time = 0.0
    _quake_last_seen_time = 0.0
    _auto_sequence_phase = "idle"
    _auto_sequence_started_time = 0.0
    _auto_takeoff_sent_time = 0.0
    _auto_scan_started_time = 0.0
    _auto_landing_started_time = 0.0

    _stop_servo_scan_for_mission()
    _stop_auto_landing_for_mission()
<<<<<<< HEAD
=======
<<<<<<< HEAD
=======
>>>>>>> b896abad72cec15526c5edf83a4468593bc2771f

    rtl_result = None
    mission_active = _active_mission_phase()
    should_rtl = AUTO_MISSION_RTL_ON_STOP and _cube_connected() and (mission_active or _cube_armed())
    if should_rtl:
        rtl_result = send_rtl_command()

    status = "Görev iptal edildi, RTL başlatıldı" if should_rtl and rtl_result and rtl_result.get("ok") else "BEKLEMEDE"
<<<<<<< HEAD
=======
>>>>>>> 82cd033 (orange cube entegrasyonu otopilot)
>>>>>>> b896abad72cec15526c5edf83a4468593bc2771f

    _state_update(
        mission_status=status,
        auto_arm_sent=False,
        auto_mission_stopped=False,
        auto_mission_enabled=True,
        auto_sequence_phase="idle",
        auto_sequence_started_time=0.0,
        auto_sequence_error=None,
    )

    add_log(status if should_rtl else "Görev durumu sıfırlandı")

    return {
        "ok": True if rtl_result is None else bool(rtl_result.get("ok")),
        "message": status,
        "rtl_sent": bool(rtl_result and rtl_result.get("ok")),
        "rtl_result": rtl_result,
    }


def arm():
    return send_arm_command(True)


def disarm():
    return send_arm_command(False)


def manual_arm():
    return send_arm_command(True)


def manual_disarm():
    return send_arm_command(False)


def arm_motors():
    return send_arm_command(True)


def disarm_motors():
    return send_arm_command(False)


def stop_mission():
    return mission_stop()


def reset_mission():
    return mission_reset()


def mission_motor_test():
    return run_motor_test()


def motor_test_route():
    return run_motor_test()


def motor_test():
    return run_motor_test()


def start_motor_test():
    return run_motor_test()


def manual_motor_test():
    return run_motor_test()


def get_status():
    return _state_snapshot()


def get_mavlink_status():
    return _state_snapshot()


def get_cube_status():
    return _state_snapshot()


def mavlink_status():
    return _state_snapshot()


if __name__ == "__main__":
    start_service()
    while True:
        time.sleep(1)
