# ===== DETAS PAN GLOBAL FIX START =====
# PAN servo bozuk bölge değişkenleri.
# Bu değerler eksik kalırsa /servo/pan ve /servo/center 500 hatası verir.

PAN_BAD_ZONE_ENABLED = True

PAN_BAD_MIN = 1300
PAN_BAD_MAX = 1800

PAN_SAFE_LEFT = 1200
PAN_SAFE_RIGHT = 1900

PAN_BAD_ZONE_MIN = PAN_BAD_MIN
PAN_BAD_ZONE_MAX = PAN_BAD_MAX
PAN_BAD_ZONE_SAFE_LEFT = PAN_SAFE_LEFT
PAN_BAD_ZONE_SAFE_RIGHT = PAN_SAFE_RIGHT

PAN_CENTER_PWM = 1500
TILT_CENTER_PWM = 1500
# ===== DETAS PAN GLOBAL FIX END =====


# ===== PAN BAD ZONE FALLBACK START =====
# PAN servoda bozuk bölge koruması için eksik kalırsa varsayılan değerler.
# Bu blok, NameError hatasını engeller.

try:
    PAN_BAD_ZONE_ENABLED
except NameError:
    PAN_BAD_ZONE_ENABLED = True

try:
    PAN_BAD_ZONE_MIN
except NameError:
    PAN_BAD_ZONE_MIN = 1300

try:
    PAN_BAD_ZONE_MAX
except NameError:
    PAN_BAD_ZONE_MAX = 1800

try:
    PAN_BAD_ZONE_SAFE_LEFT
except NameError:
    PAN_BAD_ZONE_SAFE_LEFT = 1200

try:
    PAN_BAD_ZONE_SAFE_RIGHT
except NameError:
    PAN_BAD_ZONE_SAFE_RIGHT = 1900

try:
    PAN_CENTER_PWM
except NameError:
    PAN_CENTER_PWM = 1500

try:
    TILT_CENTER_PWM
except NameError:
    TILT_CENTER_PWM = 1500
# ===== PAN BAD ZONE FALLBACK END =====


"""DETAS Orange Cube MAVLink, servo ve otomatik gorev servisi."""

import threading
import time

import config

from config import (
    AUTO_ARM_COOLDOWN,
    AUTO_MISSION_CHECK_INTERVAL,
    MAVLINK_BAUD,
    MAVLINK_DISCONNECT_TIMEOUT,
    MAVLINK_HEARTBEAT_TIMEOUT,
    MAVLINK_PORT,
    MAVLINK_RECONNECT_DELAY,
    MAVLINK_SOURCE_SYSTEM,
    MAVLINK_STREAM_RATE,
    PAN_CENTER,
    PAN_MAX,
    PAN_MIN,
    SERVO_DEFAULT_MAX,
    SERVO_DEFAULT_MIN,
    SERVO_MOVE_DELAY,
    SERVO_MOVE_STEP,
    SERVO_PAN,
    SERVO_PWM_DEADBAND,
    SERVO_TILT,
    TILT_CENTER,
    TILT_MAX,
    TILT_MIN,
)
from services.logger_service import add_log
from services.state import state

try:
    from pymavlink import mavutil

    MAVLINK_AVAILABLE = True
except Exception as exc:
    mavutil = None
    MAVLINK_AVAILABLE = False
    _MAVLINK_IMPORT_ERROR = exc


_mavlink_lock = threading.RLock()
_mavlink_master = None
_last_servo_commands = {}

_scan_lock = threading.Lock()
_scan_job_id = 0

_thread_lock = threading.Lock()
_mavlink_thread = None
_auto_mission_thread = None

_auto_motor_spin_sent = False
_earthquake_event_active = False
_earthquake_event_active = False
_earthquake_event_active = False
_motor_test_thread = None
_motor_test_lock = threading.Lock()


def _set_mavlink_master(master):
    global _mavlink_master

    with _mavlink_lock:
        if master is not _mavlink_master:
            _last_servo_commands.clear()
        _mavlink_master = master


def get_mavlink_master():
    with _mavlink_lock:
        return _mavlink_master


def mavlink_armed_status(msg):
    if not MAVLINK_AVAILABLE:
        return False

    armed_flag = mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
    return bool(msg.base_mode & armed_flag)


def is_autopilot_heartbeat(msg):
    """Mission Planner ve GCS heartbeat mesajlarini filtreler."""
    if not MAVLINK_AVAILABLE:
        return False

    autopilot = getattr(msg, "autopilot", None)
    src_component = msg.get_srcComponent()

    return (
        autopilot == mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA
        or src_component == mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1
    )


def process_mavlink_message(msg):
    """Bir MAVLink mesajini merkezi state'e uygular."""
    msg_type = msg.get_type()

    if msg_type == "BAD_DATA":
        return False

    if msg_type == "HEARTBEAT":
        if not is_autopilot_heartbeat(msg):
            return False

        try:
            mode = mavutil.mode_string_v10(msg)
        except Exception:
            mode = "BILINMIYOR"

        state.update(
            cube_connected=True,
            cube_last_heartbeat=time.time(),
            cube_mode=mode,
            cube_armed=mavlink_armed_status(msg),
        )

    elif msg_type == "ATTITUDE":
        state.update(
            cube_roll=round(msg.roll * 57.2958, 1),
            cube_pitch=round(msg.pitch * 57.2958, 1),
            cube_yaw=round(msg.yaw * 57.2958, 1),
        )

    elif msg_type == "VFR_HUD":
        state.update(
            cube_altitude=round(msg.alt, 1),
            cube_groundspeed=round(msg.groundspeed, 1),
            cube_heading=int(msg.heading),
            cube_throttle=int(msg.throttle),
        )

    elif msg_type == "SYS_STATUS":
        state.update(
            cube_battery_voltage=round(msg.voltage_battery / 1000.0, 2),
            cube_battery_current=round(msg.current_battery / 100.0, 2),
        )

    elif msg_type == "GPS_RAW_INT":
        state.update(
            cube_gps_fix=int(msg.fix_type),
            cube_satellites=int(msg.satellites_visible),
            cube_eph=int(msg.eph),
        )

    elif msg_type == "COMMAND_ACK":
        if int(getattr(msg, "result", -1)) == 0:
            return True

        add_log(f"MAVLink komut reddedildi, ACK sonucu: {msg.result}")
        return False
    else:
        return False

    return True


def mavlink_worker():
    """Cube baglantisini acip MAVLink mesajlarini surekli okur."""
    if not MAVLINK_AVAILABLE:
        add_log(f"MAVLink icin pymavlink yok: {_MAVLINK_IMPORT_ERROR}")
        state.update(cube_connected=False)
        return

    while True:
        master = None

        try:
            add_log(f"Cube MAVLink aciliyor: {MAVLINK_PORT} @ {MAVLINK_BAUD}")

            master = mavutil.mavlink_connection(
                MAVLINK_PORT,
                baud=MAVLINK_BAUD,
                autoreconnect=True,
                source_system=MAVLINK_SOURCE_SYSTEM,
            )
            _set_mavlink_master(master)

            heartbeat = master.wait_heartbeat(timeout=MAVLINK_HEARTBEAT_TIMEOUT)

            if heartbeat is None:
                state.update(cube_connected=False)
                add_log("Cube MAVLink heartbeat yok")
                _set_mavlink_master(None)
                time.sleep(MAVLINK_RECONNECT_DELAY)
                continue

            # wait_heartbeat GCS mesaji dondurebilir; ARM state'i yalnizca
            # process_mavlink_message icindeki autopilot filtresi gunceller.
            process_mavlink_message(heartbeat)
            add_log("Cube MAVLink baglandi")

            try:
                master.mav.request_data_stream_send(
                    master.target_system,
                    master.target_component,
                    mavutil.mavlink.MAV_DATA_STREAM_ALL,
                    MAVLINK_STREAM_RATE,
                    1,
                )
            except Exception as exc:
                add_log(f"MAVLink stream istegi hatasi: {exc}")

            while True:
                msg = master.recv_match(blocking=True, timeout=2)

                if msg is None:
                    heartbeat_time = state.cube_last_heartbeat

                    if (
                        heartbeat_time
                        and time.time() - heartbeat_time > MAVLINK_DISCONNECT_TIMEOUT
                    ):
                        state.update(cube_connected=False)
                    continue

                process_mavlink_message(msg)

        except Exception as exc:
            state.update(cube_connected=False)
            add_log(f"Cube MAVLink hata: {exc}")
        finally:
            if get_mavlink_master() is master:
                _set_mavlink_master(None)

        time.sleep(MAVLINK_RECONNECT_DELAY)


def start_mavlink_thread():
    """MAVLink okuma thread'ini bir kez baslatir."""
    global _mavlink_thread

    with _thread_lock:
        if _mavlink_thread is not None and _mavlink_thread.is_alive():
            return _mavlink_thread

        _mavlink_thread = threading.Thread(
            target=mavlink_worker,
            name="detas-mavlink",
            daemon=True,
        )
        _mavlink_thread.start()
        return _mavlink_thread


def send_arm_command(arm=True):
    """Cube'a ARM veya DISARM komutu gonderir."""
    if not MAVLINK_AVAILABLE:
        return False, "pymavlink yok"

    with _mavlink_lock:
        master = _mavlink_master

        if master is None:
            return False, "MAVLink master yok"

        try:
            target_system = getattr(master, "target_system", 1) or 1

            # Mission Planner / GCS component degil, autopilot component hedeflenir.
            target_component = mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1

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
                0,
            )

            message = "ARM komutu gönderildi" if arm else "DISARM komutu gönderildi"
            return True, message

        except Exception as exc:
            return False, str(exc)


def clamp_servo_pwm(servo_number, pwm):
    pwm = int(pwm)

    if servo_number == SERVO_PAN:
        return max(PAN_MIN, min(PAN_MAX, pwm))

    if servo_number == SERVO_TILT:
        return max(TILT_MIN, min(TILT_MAX, pwm))

    return max(SERVO_DEFAULT_MIN, min(SERVO_DEFAULT_MAX, pwm))


def _pan_bad_low():
    return clamp_servo_pwm(SERVO_PAN, PAN_BAD_MIN - PAN_BAD_MARGIN)


def _pan_bad_high():
    return clamp_servo_pwm(SERVO_PAN, PAN_BAD_MAX + PAN_BAD_MARGIN)


def _is_pan_bad_zone(pwm):
    return PAN_BAD_ZONE_ENABLED and PAN_BAD_MIN <= int(pwm) <= PAN_BAD_MAX


def _safe_servo_target(servo_number, pwm):
    """Hedef PWM yasak bölgedeyse en yakın güvenli kenara çeker."""
    pwm = clamp_servo_pwm(servo_number, pwm)

    if servo_number == SERVO_PAN and _is_pan_bad_zone(pwm):
        low = _pan_bad_low()
        high = _pan_bad_high()

        if abs(pwm - low) <= abs(high - pwm):
            return low

        return high

    return pwm


def _servo_state_pwm(servo_number):
    if servo_number == SERVO_PAN:
        return int(state.servo_pan)

    if servo_number == SERVO_TILT:
        return int(state.servo_tilt)

    return int(_last_servo_commands.get(servo_number, 1500))


def _update_servo_state(servo_number, pwm):
    if servo_number == SERVO_PAN:
        state.update(servo_pan=int(pwm))
    elif servo_number == SERVO_TILT:
        state.update(servo_tilt=int(pwm))


def start_new_servo_job():
    global _scan_job_id

    with _scan_lock:
        _scan_job_id += 1
        return _scan_job_id


def is_servo_job_active(job_id):
    with _scan_lock:
        return job_id == _scan_job_id


def _sleep_with_cancel(seconds, job_id=None):
    end_time = time.time() + float(seconds)

    while time.time() < end_time:
        if job_id is not None and not is_servo_job_active(job_id):
            return False

        time.sleep(min(0.02, max(0.0, end_time - time.time())))

    return True


def send_servo_pwm(servo_number, pwm, force=False):
    """Cube AUX çıkışına MAV_CMD_DO_SET_SERVO komutu gönderir.

    PAN için 1320-1800 aralığında durmayı engeller.
    Aynı PWM değerini sürekli tekrar göndermez.
    """
    if not MAVLINK_AVAILABLE:
        return False, "pymavlink yok"

    pwm = _safe_servo_target(servo_number, pwm)

    with _servo_command_lock:
        last_pwm = _last_servo_commands.get(servo_number)

        if (
            not force
            and last_pwm is not None
            and abs(last_pwm - pwm) <= max(SERVO_PWM_DEADBAND, 10)
        ):
            _update_servo_state(servo_number, pwm)
            return True, "SKIP_SAME_PWM"

        last_time = _last_servo_sent_time.get(servo_number, 0.0)
        wait_time = SERVO_MIN_COMMAND_INTERVAL - (time.time() - last_time)

        if wait_time > 0:
            time.sleep(wait_time)

        with _mavlink_lock:
            master = _mavlink_master

            if master is None:
                return False, "MAVLink bağlantısı yok"

            try:
                target_system = getattr(master, "target_system", 1) or 1

                # GCS/Mission Planner component değil, autopilot component hedeflenir.
                target_component = mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1

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
                    0,
                )

                _last_servo_commands[servo_number] = pwm
                _last_servo_sent_time[servo_number] = time.time()
                _update_servo_state(servo_number, pwm)

                return True, "OK"

            except Exception as exc:
                return False, str(exc)


def _basic_pwm_path(start_pwm, end_pwm, step):
    start_pwm = int(start_pwm)
    end_pwm = int(end_pwm)
    step = max(1, abs(int(step)))

    if start_pwm == end_pwm:
        return [start_pwm]

    if start_pwm < end_pwm:
        values = list(range(start_pwm, end_pwm + 1, step))
        if values[-1] != end_pwm:
            values.append(end_pwm)
        return values

    values = list(range(start_pwm, end_pwm - 1, -step))
    if values[-1] != end_pwm:
        values.append(end_pwm)
    return values


def _servo_path_avoiding_bad_zone(servo_number, start_pwm, end_pwm, step):
    """PAN hareketinde titreşim bölgesini yavaş yavaş gezmez, hızlı atlar."""
    start_pwm = _safe_servo_target(servo_number, start_pwm)
    end_pwm = _safe_servo_target(servo_number, end_pwm)

    if servo_number != SERVO_PAN or not PAN_BAD_ZONE_ENABLED:
        return _basic_pwm_path(start_pwm, end_pwm, step)

    low = _pan_bad_low()
    high = _pan_bad_high()

    # Soldan sağa giderken kötü bölgeyi atla
    if start_pwm < low and end_pwm > high:
        part1 = _basic_pwm_path(start_pwm, low, step)
        part2 = _basic_pwm_path(high, end_pwm, step)
        return part1 + [high] + part2[1:]

    # Sağdan sola giderken kötü bölgeyi atla
    if start_pwm > high and end_pwm < low:
        part1 = _basic_pwm_path(start_pwm, high, step)
        part2 = _basic_pwm_path(low, end_pwm, step)
        return part1 + [low] + part2[1:]

    return _basic_pwm_path(start_pwm, end_pwm, step)


def smooth_servo_move(
    servo_number,
    start_pwm,
    end_pwm,
    step=SERVO_MOVE_STEP,
    delay=SERVO_MOVE_DELAY,
    job_id=None,
):
    start_pwm = _safe_servo_target(servo_number, start_pwm)
    end_pwm = _safe_servo_target(servo_number, end_pwm)
    step = max(1, abs(int(step)))
    delay = max(0.02, float(delay))

    values = _servo_path_avoiding_bad_zone(servo_number, start_pwm, end_pwm, step)

    for pwm in values:
        if job_id is not None and not is_servo_job_active(job_id):
            return False

        ok, _ = send_servo_pwm(servo_number, pwm)

        if not ok:
            return False

        if not _sleep_with_cancel(delay, job_id):
            return False

    return True


def _start_servo_action(target, name):
    threading.Thread(target=target, name=name, daemon=True).start()


def servo_pan(pwm):
    """Slider PAN komutu. Kötü PWM bölgesinde durdurmaz."""
    job_id = start_new_servo_job()
    target_pwm = _safe_servo_target(SERVO_PAN, pwm)
    start_pwm = _safe_servo_target(SERVO_PAN, state.servo_pan)

    def move():
        try:
            smooth_servo_move(
                SERVO_PAN,
                start_pwm,
                target_pwm,
                step=35,
                delay=0.035,
                job_id=job_id,
            )
        except Exception as exc:
            add_log(f"Slider PAN hata: {exc}")

    _start_servo_action(move, "detas-slider-pan")

    return {
        "ok": True,
        "message": "PAN slider hareketi başlatıldı",
        "servo": "pan",
        "pwm": target_pwm,
    }


def servo_tilt(pwm):
    """TILT için normal slider hareketi."""
    job_id = start_new_servo_job()
    target_pwm = clamp_servo_pwm(SERVO_TILT, pwm)
    start_pwm = clamp_servo_pwm(SERVO_TILT, state.servo_tilt)

    def move():
        try:
            smooth_servo_move(
                SERVO_TILT,
                start_pwm,
                target_pwm,
                step=25,
                delay=0.045,
                job_id=job_id,
            )
        except Exception as exc:
            add_log(f"Slider TILT hata: {exc}")

    _start_servo_action(move, "detas-slider-tilt")

    return {
        "ok": True,
        "message": "TILT slider hareketi başlatıldı",
        "servo": "tilt",
        "pwm": target_pwm,
    }


def servo_center():
    job_id = start_new_servo_job()

    def center():
        try:
            # PAN_CENTER kötü bölgeye çok yakınsa güvenli hedefe çekilir.
            pan_target = _safe_servo_target(SERVO_PAN, PAN_CENTER)
            tilt_target = clamp_servo_pwm(SERVO_TILT, TILT_CENTER)

            if not smooth_servo_move(
                SERVO_PAN,
                state.servo_pan,
                pan_target,
                step=35,
                delay=0.035,
                job_id=job_id,
            ):
                return

            if not _sleep_with_cancel(0.15, job_id):
                return

            smooth_servo_move(
                SERVO_TILT,
                state.servo_tilt,
                tilt_target,
                step=25,
                delay=0.045,
                job_id=job_id,
            )

            add_log("Servo merkez/güvenli konuma alındı")

        except Exception as exc:
            add_log(f"Servo merkez hata: {exc}")

    _start_servo_action(center, "detas-servo-center")

    return {
        "ok": True,
        "mode": "center",
        "pan": _safe_servo_target(SERVO_PAN, PAN_CENTER),
        "tilt": TILT_CENTER,
    }


def servo_scan():
    return servo_scan_pan_slow()


def servo_scan_pan_slow():
    job_id = start_new_servo_job()

    def scan():
        try:
            if not smooth_servo_move(
                SERVO_PAN,
                state.servo_pan,
                PAN_MIN,
                step=35,
                delay=0.035,
                job_id=job_id,
            ):
                return

            if not _sleep_with_cancel(0.2, job_id):
                return

            if not smooth_servo_move(
                SERVO_PAN,
                PAN_MIN,
                PAN_MAX,
                step=35,
                delay=0.035,
                job_id=job_id,
            ):
                return

            if not _sleep_with_cancel(0.2, job_id):
                return

            smooth_servo_move(
                SERVO_PAN,
                PAN_MAX,
                _safe_servo_target(SERVO_PAN, PAN_CENTER),
                step=35,
                delay=0.035,
                job_id=job_id,
            )
        except Exception as exc:
            add_log(f"Pan tarama hata: {exc}")

    _start_servo_action(scan, "detas-servo-pan-scan")
    return {"ok": True, "mode": "pan_slow_scan"}


def servo_scan_tilt_slow():
    job_id = start_new_servo_job()

    def scan():
        try:
            if not smooth_servo_move(
                SERVO_TILT,
                state.servo_tilt,
                TILT_MIN,
                step=25,
                delay=0.05,
                job_id=job_id,
            ):
                return

            if not _sleep_with_cancel(0.25, job_id):
                return

            if not smooth_servo_move(
                SERVO_TILT,
                TILT_MIN,
                TILT_MAX,
                step=25,
                delay=0.05,
                job_id=job_id,
            ):
                return

            if not _sleep_with_cancel(0.25, job_id):
                return

            smooth_servo_move(
                SERVO_TILT,
                TILT_MAX,
                TILT_CENTER,
                step=25,
                delay=0.05,
                job_id=job_id,
            )
        except Exception as exc:
            add_log(f"Tilt tarama hata: {exc}")

    _start_servo_action(scan, "detas-servo-tilt-scan")
    return {"ok": True, "mode": "tilt_slow_scan"}


def servo_scan_full_slow():
    job_id = start_new_servo_job()

    def scan():
        try:
            moves = (
                (SERVO_PAN, state.servo_pan, PAN_MIN, 35, 0.035),
                (SERVO_PAN, PAN_MIN, PAN_MAX, 35, 0.035),
                (SERVO_PAN, PAN_MAX, _safe_servo_target(SERVO_PAN, PAN_CENTER), 35, 0.035),
                (SERVO_TILT, state.servo_tilt, TILT_MIN, 25, 0.05),
                (SERVO_TILT, TILT_MIN, TILT_MAX, 25, 0.05),
                (SERVO_TILT, TILT_MAX, TILT_CENTER, 25, 0.05),
            )

            for servo_number, start_pwm, end_pwm, step, delay in moves:
                if not smooth_servo_move(
                    servo_number,
                    start_pwm,
                    end_pwm,
                    step=step,
                    delay=delay,
                    job_id=job_id,
                ):
                    return

                if not _sleep_with_cancel(0.2, job_id):
                    return

        except Exception as exc:
            add_log(f"Tam tarama hata: {exc}")

    _start_servo_action(scan, "detas-servo-full-scan")
    return {"ok": True, "mode": "full_slow_scan"}


def servo_up():
    start_new_servo_job()
    ok, message = send_servo_pwm(SERVO_TILT, TILT_MAX)
    return {"ok": ok, "message": message, "tilt": state.servo_tilt}


def servo_down():
    start_new_servo_job()
    ok, message = send_servo_pwm(SERVO_TILT, TILT_MIN)
    return {"ok": ok, "message": message, "tilt": state.servo_tilt}


def servo_left():
    start_new_servo_job()
    ok, message = send_servo_pwm(SERVO_PAN, PAN_MIN)
    return {"ok": ok, "message": message, "pan": state.servo_pan}


def servo_right():
    start_new_servo_job()
    ok, message = send_servo_pwm(SERVO_PAN, PAN_MAX)
    return {"ok": ok, "message": message, "pan": state.servo_pan}


def servo_stop():
    start_new_servo_job()
    add_log("Servo tarama durduruldu")
    return {
        "ok": True,
        "mode": "stop",
        "pan": state.servo_pan,
        "tilt": state.servo_tilt,
    }



# -------------------------------------------------
# OTOMATIK MOTOR TEST / PERVANESIZ DUSUK GUC DONUS
# -------------------------------------------------

def send_motor_test_command(motor_number, throttle_percent=None, duration_sec=None):
    """ArduPilot MAV_CMD_DO_MOTOR_TEST komutu gönderir.

    Bu komut sadece pervaneler takılı değilken düşük güç test için kullanılmalıdır.
    """
    if not MAVLINK_AVAILABLE:
        return False, "pymavlink yok"

    throttle_percent = int(throttle_percent if throttle_percent is not None else getattr(config, "MOTOR_TEST_THROTTLE_PERCENT", 7))
    duration_sec = float(duration_sec if duration_sec is not None else getattr(config, "MOTOR_TEST_DURATION_SEC", 2.0))

    throttle_percent = max(5, min(35, throttle_percent))
    duration_sec = max(0.5, min(5.0, duration_sec))

    with _mavlink_lock:
        master = _mavlink_master

        if master is None:
            return False, "MAVLink master yok"

        try:
            target_system = getattr(master, "target_system", 1) or 1
            target_component = mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1

            # MAV_CMD_DO_MOTOR_TEST parametreleri:
            # p1: motor numarası, p2: throttle type 0 = yüzde, p3: throttle,
            # p4: süre, p5: motor sayısı, p6-p7 kullanılmıyor.
            master.mav.command_long_send(
                target_system,
                target_component,
                mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST,
                0,
                int(motor_number),
                0,
                throttle_percent,
                duration_sec,
                1,
                0,
                0,
            )

            return True, f"Motor {motor_number} test komutu gönderildi"

        except Exception as exc:
            return False, str(exc)


def start_motor_spin_test(reason="deprem"):
    """Motorları sırayla düşük güçte döndürür.

    Aynı anda ikinci motor testi başlatılmaz.
    """
    global _motor_test_thread

    if not getattr(config, "AUTO_MOTOR_SPIN_TEST_ON_EARTHQUAKE", False):
        return {"ok": False, "message": "Motor test modu config'te kapalı"}

    with _motor_test_lock:
        if _motor_test_thread is not None and _motor_test_thread.is_alive():
            return {"ok": True, "message": "Motor test zaten çalışıyor"}

        def worker():
            try:
                motor_count = int(getattr(config, "MOTOR_TEST_MOTOR_COUNT", 4))
                throttle = int(getattr(config, "MOTOR_TEST_THROTTLE_PERCENT", 7))
                duration = float(getattr(config, "MOTOR_TEST_DURATION_SEC", 2.0))
                gap = float(getattr(config, "MOTOR_TEST_GAP_SEC", 0.4))

                add_log(f"Motor test başladı: sebep={reason}, güç=%{throttle}")

                for motor_no in range(1, motor_count + 1):
                    snapshot = state.snapshot()

                    if snapshot["auto_mission_stopped"]:
                        add_log("Motor test durduruldu: görev stop aktif")
                        break

                    if not snapshot["cube_connected"]:
                        add_log("Motor test iptal: Cube bağlantısı yok")
                        break

                    ok, message = send_motor_test_command(
                        motor_number=motor_no,
                        throttle_percent=throttle,
                        duration_sec=duration,
                    )

                    if ok:
                        add_log(f"Motor {motor_no} düşük güç test")
                    else:
                        add_log(f"Motor {motor_no} test hatası: {message}")

                    time.sleep(duration + gap)

                add_log("Motor test tamamlandı")

            except Exception as exc:
                add_log(f"Motor test worker hata: {exc}")

        _motor_test_thread = threading.Thread(
            target=worker,
            name="detas-motor-test",
            daemon=True,
        )
        _motor_test_thread.start()

    return {"ok": True, "message": "Motor test başlatıldı"}


def mission_arm():
    """Panelden manuel ARM komutu."""
    state.update(
        auto_mission_enabled=True,
        auto_mission_stopped=False,
        mission_status="MANUEL ARM",
    )

    ok, message = send_arm_command(True)

    if ok:
        add_log("Panelden manuel ARM komutu gönderildi")
    else:
        add_log(f"Manuel ARM hatası: {message}")

    return {"ok": ok, "message": message, "mission_status": state.mission_status}


def mission_motor_test():
    """Panel/curl üzerinden manuel motor test başlatmak için servis fonksiyonu."""
    return start_motor_spin_test(reason="manuel")


def mission_stop():
    global _auto_motor_spin_sent
    global _earthquake_event_active
    global _earthquake_event_active
    _auto_motor_spin_sent = False
    state.update(
        auto_mission_enabled=False,
        auto_mission_stopped=True,
        auto_arm_sent=False,
        mission_status="DURDURULDU",
    )
    ok, message = send_arm_command(False)
    add_log("Motorlari durdur komutu verildi")
    return {"ok": ok, "message": message, "mission_status": "DURDURULDU"}


def mission_reset():
    global _auto_motor_spin_sent
    global _earthquake_event_active
    global _earthquake_event_active
    _auto_motor_spin_sent = False
    state.update(
        auto_mission_enabled=True,
        auto_mission_stopped=False,
        auto_arm_sent=False,
        mission_status="BEKLEMEDE", 
    )
    add_log("Otomatik gorev sistemi sifirlandi")
    return {"ok": True, "mission_status": "BEKLEMEDE"}


def is_earthquake_triggered():
    """Yeni deprem tetik kontrolü.

    Önemli:
    - Otomatik ARM için max_movement kullanılmaz.
    - max_movement yüksek kaldığı için sistem tek seferden sonra kilitlenebiliyordu.
    - Burada sadece anlık movement veya istasyonun deprem=1 bilgisi dikkate alınır.
    """
    snapshot = state.snapshot()
    threshold = float(snapshot["threshold"] or 0)
    movement = float(snapshot["movement"] or 0)

    return (
        snapshot["deprem"] == 1
        or (
            threshold > 0
            and movement >= threshold
        )
    )


def auto_mission_worker():
    """Deprem algılanınca ARM gönderir, ARM olunca motor test başlatır.

    Tek seferlik kalmaması için deprem normale düşünce bayrakları sıfırlar.
    Böylece ikinci/üçüncü deprem olayında yeniden ARM + motor test çalışır.
    """
    global _auto_motor_spin_sent
    global _earthquake_event_active

    add_log("Otomatik deprem görev kontrolü aktif")

    while True:
        try:
            snapshot = state.snapshot()
            armed = snapshot["cube_armed"]
            earthquake = is_earthquake_triggered()

            # Deprem sinyali normale döndüyse yeni olay için sistemi hazırla
            if not earthquake:
                if _earthquake_event_active:
                    add_log("Deprem sinyali normale döndü: sistem yeni olay için hazır")

                _earthquake_event_active = False
                _auto_motor_spin_sent = False

                if not armed and not snapshot["auto_mission_stopped"]:
                    state.update(
                        mission_status="BEKLEMEDE",
                        auto_arm_sent=False,
                    )

            if snapshot["auto_mission_stopped"]:
                mission_status = "DURDURULUYOR" if armed else "DURDURULDU"
                state.update(mission_status=mission_status)

            elif earthquake and snapshot["auto_mission_enabled"]:
                _earthquake_event_active = True

                if armed:
                    state.update(mission_status="GÖREVDE - MOTOR HAZIR")

                    if (
                        getattr(config, "AUTO_MOTOR_SPIN_TEST_ON_EARTHQUAKE", False)
                        and not _auto_motor_spin_sent
                    ):
                        _auto_motor_spin_sent = True
                        start_motor_spin_test(reason="deprem")

                elif snapshot["cube_connected"]:
                    now = time.time()

                    if (
                        snapshot["auto_arm_on_earthquake"]
                        and not snapshot["auto_arm_sent"]
                        and now - snapshot["last_auto_arm_time"] > AUTO_ARM_COOLDOWN
                    ):
                        state.update(mission_status="DEPREM ALGILANDI - ARM")
                        ok, message = send_arm_command(True)
                        state.update(auto_arm_sent=True, last_auto_arm_time=now)

                        if ok:
                            add_log("Deprem eşiği aşıldı: Cube ARM komutu gönderildi")
                        else:
                            add_log(f"ARM komutu başarısız: {message}")
                    else:
                        state.update(mission_status="ARM BEKLENİYOR")
                else:
                    state.update(mission_status="DEPREM ALGILANDI - CUBE YOK")

            elif armed:
                state.update(mission_status="ARMED - HAZIR")

        except Exception as exc:
            state.update(mission_status="GÖREV KONTROL HATASI")
            add_log(f"Otomatik görev hata: {exc}")

        time.sleep(AUTO_MISSION_CHECK_INTERVAL)


def start_auto_mission_thread():
    """Otomatik gorev thread'ini bir kez baslatir."""
    global _auto_mission_thread

    with _thread_lock:
        if _auto_mission_thread is not None and _auto_mission_thread.is_alive():
            return _auto_mission_thread

        _auto_mission_thread = threading.Thread(
            target=auto_mission_worker,
            name="detas-auto-mission",
            daemon=True,
        )
        _auto_mission_thread.start()
        return _auto_mission_thread


# Eski app.py isimleriyle uyumluluk.
mavlink_thread = mavlink_worker
auto_mission_thread = auto_mission_worker
detas_send_arm_command = send_arm_command



# ===== DETAS REPEAT ARM OVERRIDE START =====
# Bu blok ikinci/üçüncü deprem olayında tekrar otomatik ARM atılması için eklendi.
# Eski fonksiyonları silmez; Python'da aynı isimle yeniden tanımlayıp override eder.

_repeat_earthquake_event_active = False
_repeat_last_normal_time = 0.0


def is_earthquake_triggered():
    """Otomatik ARM için sadece anlık deprem/movement kontrolü.

    max_movement kullanılmaz; çünkü max_movement yüksek kaldığında sistem
    ikinci depremi yeni olay gibi algılamıyordu.
    """
    snapshot = state.snapshot()

    try:
        threshold = float(snapshot.get("threshold", 0) or 0)
    except Exception:
        threshold = 0.0

    try:
        movement = float(snapshot.get("movement", 0) or 0)
    except Exception:
        movement = 0.0

    try:
        deprem = int(snapshot.get("deprem", 0) or 0)
    except Exception:
        deprem = 0

    return deprem == 1 or (threshold > 0 and movement >= threshold)


def auto_mission_worker():
    """Deprem algılanınca ARM gönderir.

    Deprem sinyali eşik altına düşünce sistem yeni deprem için yeniden hazırlanır.
    Böylece ilk olaydan sonra ikinci olayda tekrar ARM + motor test çalışır.
    """
    global _auto_motor_spin_sent
    global _repeat_earthquake_event_active
    global _repeat_last_normal_time

    add_log("Otomatik deprem görev kontrolü aktif - repeat override")

    while True:
        try:
            snapshot = state.snapshot()
            armed = bool(snapshot.get("cube_armed", False))
            cube_connected = bool(snapshot.get("cube_connected", False))
            earthquake = is_earthquake_triggered()
            stopped = bool(snapshot.get("auto_mission_stopped", False))
            enabled = bool(snapshot.get("auto_mission_enabled", True))
            auto_arm_on = bool(snapshot.get("auto_arm_on_earthquake", True))

            now = time.time()

            # 1) Deprem yoksa sistemi yeni olay için hazırla
            if not earthquake:
                if _repeat_earthquake_event_active:
                    add_log("Deprem sinyali normale döndü: tekrar ARM için hazır")

                _repeat_earthquake_event_active = False
                _repeat_last_normal_time = now
                _auto_motor_spin_sent = False

                if not armed and not stopped:
                    state.update(
                        mission_status="BEKLEMEDE",
                        auto_arm_sent=False,
                    )

                time.sleep(AUTO_MISSION_CHECK_INTERVAL)
                continue

            # 2) Stop aktifse hiçbir otomatik ARM atma
            if stopped:
                state.update(
                    mission_status="DURDURULUYOR" if armed else "DURDURULDU"
                )
                time.sleep(AUTO_MISSION_CHECK_INTERVAL)
                continue

            if not enabled:
                time.sleep(AUTO_MISSION_CHECK_INTERVAL)
                continue

            # 3) Yeni deprem olayı başladıysa bayrakları sıfırla
            if earthquake and not _repeat_earthquake_event_active:
                _repeat_earthquake_event_active = True
                _auto_motor_spin_sent = False

                state.update(
                    auto_arm_sent=False,
                    mission_status="YENİ DEPREM ALGILANDI",
                )

                add_log("Yeni deprem olayı algılandı: otomatik ARM hazırlanıyor")

            # 4) Cube zaten armed ise görevde kabul et ve motor testi bir kez başlat
            if armed:
                state.update(mission_status="GÖREVDE - MOTOR HAZIR")

                if (
                    getattr(config, "AUTO_MOTOR_SPIN_TEST_ON_EARTHQUAKE", False)
                    and not _auto_motor_spin_sent
                ):
                    _auto_motor_spin_sent = True
                    start_motor_spin_test(reason="deprem")

                time.sleep(AUTO_MISSION_CHECK_INTERVAL)
                continue

            # 5) Deprem var, Cube bağlı, armed değilse ARM komutu gönder
            if cube_connected and auto_arm_on:
                try:
                    last_auto_arm_time = float(snapshot.get("last_auto_arm_time", 0) or 0)
                except Exception:
                    last_auto_arm_time = 0.0

                auto_arm_sent = bool(snapshot.get("auto_arm_sent", False))

                # Yeni olayda auto_arm_sent zaten False yapılır.
                # Komut başarısız kaldıysa cooldown sonrası tekrar denemeye de izin veriyoruz.
                can_send_first = not auto_arm_sent
                can_retry = auto_arm_sent and (now - last_auto_arm_time > max(AUTO_ARM_COOLDOWN, 5.0))

                if now - last_auto_arm_time > AUTO_ARM_COOLDOWN and (can_send_first or can_retry):
                    state.update(mission_status="DEPREM ALGILANDI - ARM")
                    ok, message = send_arm_command(True)

                    state.update(
                        auto_arm_sent=True,
                        last_auto_arm_time=now,
                    )

                    if ok:
                        add_log("Deprem eşiği aşıldı: Cube ARM komutu gönderildi")
                    else:
                        add_log(f"ARM komutu başarısız: {message}")
                else:
                    state.update(mission_status="ARM BEKLENİYOR")

            elif not cube_connected:
                state.update(mission_status="DEPREM ALGILANDI - CUBE YOK")

        except Exception as exc:
            state.update(mission_status="GÖREV KONTROL HATASI")
            add_log(f"Otomatik görev hata: {exc}")

        time.sleep(AUTO_MISSION_CHECK_INTERVAL)


def mission_stop():
    """Panelden motorları durdur / DISARM."""
    global _auto_motor_spin_sent
    global _repeat_earthquake_event_active

    _auto_motor_spin_sent = False
    _repeat_earthquake_event_active = False

    state.update(
        auto_mission_enabled=False,
        auto_mission_stopped=True,
        auto_arm_sent=False,
        mission_status="DURDURULDU",
    )

    ok, message = send_arm_command(False)

    if ok:
        add_log("Motorları durdur / DISARM komutu verildi")
    else:
        add_log(f"DISARM komutu hatası: {message}")

    return {
        "ok": ok,
        "message": message,
        "mission_status": state.mission_status,
    }


def mission_reset():
    """Otomatik görev sistemini yeniden hazır hale getirir."""
    global _auto_motor_spin_sent
    global _repeat_earthquake_event_active

    _auto_motor_spin_sent = False
    _repeat_earthquake_event_active = False

    state.update(
        auto_mission_enabled=True,
        auto_mission_stopped=False,
        auto_arm_sent=False,
        mission_status="BEKLEMEDE",
    )

    add_log("Otomatik görev sistemi sıfırlandı")

    return {
        "ok": True,
        "mission_status": state.mission_status,
    }

# ===== DETAS REPEAT ARM OVERRIDE END =====


# ===== DETAS SERVO CLEAN OVERRIDE START =====
# Bu bölüm pan-tilt servo kontrolünü sadeleştirir.
# Eski PAN_BAD_MIN / PAN_BAD_ZONE değişkenlerine bağımlı değildir.

import time as _detas_time
import threading as _detas_threading

try:
    from pymavlink import mavutil as _detas_mavutil
except Exception:
    _detas_mavutil = None

DETAS_PAN_SERVO = 9       # Orange Cube AUX OUT 1
DETAS_TILT_SERVO = 11     # Orange Cube AUX OUT 3

DETAS_MAVLINK_PORT = "/dev/ttyAMA4"
DETAS_MAVLINK_BAUD = 57600

_detas_servo_master = None
_detas_servo_lock = _detas_threading.Lock()
_detas_scan_stop = _detas_threading.Event()
_detas_scan_thread = None


def _detas_log(msg):
    try:
        add_log(str(msg))
    except Exception:
        print("[DETAS SERVO]", msg)


def _detas_pwm(value):
    try:
        value = int(value)
    except Exception:
        value = 1500

    if value < 1000:
        value = 1000
    if value > 2000:
        value = 2000

    return value


def _detas_find_existing_master():
    """
    mavlink_service.py içinde daha önce açılmış MAVLink bağlantısını bulur.
    Değişken adı master, mavlink_connection, vehicle vs. ne olursa olsun arar.
    """
    for name, obj in list(globals().items()):
        if name.startswith("_detas"):
            continue

        try:
            if hasattr(obj, "mav") and hasattr(obj.mav, "command_long_send"):
                ts = getattr(obj, "target_system", 0)
                if ts:
                    return obj
        except Exception:
            pass

    return None


def _detas_get_master():
    """
    Önce mevcut MAVLink bağlantısını kullanır.
    Bulamazsa kendisi bağlantı açmayı dener.
    """
    global _detas_servo_master

    master = _detas_find_existing_master()
    if master is not None:
        return master

    if _detas_servo_master is not None:
        return _detas_servo_master

    if _detas_mavutil is None:
        raise RuntimeError("pymavlink yüklü değil")

    _detas_log("Servo için MAVLink bağlantısı açılıyor")

    _detas_servo_master = _detas_mavutil.mavlink_connection(
        DETAS_MAVLINK_PORT,
        baud=DETAS_MAVLINK_BAUD
    )

    _detas_servo_master.wait_heartbeat(timeout=10)

    _detas_log("Servo MAVLink bağlantısı hazır")

    return _detas_servo_master


def detas_send_servo_pwm(servo_number, pwm):
    """
    En temel çalışan servo komutu.
    MAV_CMD_DO_SET_SERVO gönderir.
    """
    pwm = _detas_pwm(pwm)
    servo_number = int(servo_number)

    with _detas_servo_lock:
        master = _detas_get_master()

        target_system = getattr(master, "target_system", 1) or 1
        target_component = getattr(master, "target_component", 1) or 1

        master.mav.command_long_send(
            target_system,
            target_component,
            _detas_mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
            0,
            servo_number,
            pwm,
            0,
            0,
            0,
            0,
            0
        )

    _detas_log(f"SERVO{servo_number} PWM gönderildi: {pwm}")

    return {
        "ok": True,
        "servo_number": servo_number,
        "pwm": pwm
    }


def detas_set_pan(pwm):
    return detas_send_servo_pwm(DETAS_PAN_SERVO, pwm)


def detas_set_tilt(pwm):
    return detas_send_servo_pwm(DETAS_TILT_SERVO, pwm)


def detas_servo_center():
    _detas_scan_stop.set()
    detas_set_pan(1500)
    _detas_time.sleep(0.15)
    detas_set_tilt(1500)

    return {
        "ok": True,
        "mode": "center",
        "pan": 1500,
        "tilt": 1500
    }


def detas_servo_stop():
    _detas_scan_stop.set()

    return {
        "ok": True,
        "mode": "stop"
    }


def _detas_scan_worker(mode):
    _detas_scan_stop.clear()

    try:
        if mode == "pan":
            while not _detas_scan_stop.is_set():
                detas_set_pan(1200)
                _detas_time.sleep(1.2)

                if _detas_scan_stop.is_set():
                    break

                detas_set_pan(1900)
                _detas_time.sleep(1.2)

        elif mode == "tilt":
            while not _detas_scan_stop.is_set():
                detas_set_tilt(1200)
                _detas_time.sleep(1.2)

                if _detas_scan_stop.is_set():
                    break

                detas_set_tilt(1800)
                _detas_time.sleep(1.2)

        elif mode == "full":
            while not _detas_scan_stop.is_set():
                detas_set_pan(1200)
                detas_set_tilt(1200)
                _detas_time.sleep(1.2)

                if _detas_scan_stop.is_set():
                    break

                detas_set_pan(1900)
                detas_set_tilt(1800)
                _detas_time.sleep(1.2)

    except Exception as e:
        _detas_log(f"Tarama hatası: {e}")


def _detas_start_scan(mode):
    global _detas_scan_thread

    _detas_scan_stop.set()
    _detas_time.sleep(0.15)
    _detas_scan_stop.clear()

    _detas_scan_thread = _detas_threading.Thread(
        target=_detas_scan_worker,
        args=(mode,),
        daemon=True
    )
    _detas_scan_thread.start()

    return {
        "ok": True,
        "mode": mode
    }


def detas_scan_pan_slow():
    return _detas_start_scan("pan")


def detas_scan_tilt_slow():
    return _detas_start_scan("tilt")


def detas_scan_full_slow():
    return _detas_start_scan("full")


# Eski route veya servis kodu bu isimleri çağırıyorsa onlar da temiz fonksiyonlara bağlansın.
send_servo_pwm = detas_send_servo_pwm
set_servo_pwm = detas_send_servo_pwm
move_pan = detas_set_pan
move_tilt = detas_set_tilt
servo_center = detas_servo_center
center_servos = detas_servo_center
stop_servo_scan = detas_servo_stop
scan_pan_slow = detas_scan_pan_slow
scan_tilt_slow = detas_scan_tilt_slow
scan_full_slow = detas_scan_full_slow

# ===== DETAS SERVO CLEAN OVERRIDE END =====


# ===== DETAS SERVO LIMIT OVERRIDE V2 START =====
# Mission Planner değerlerine göre temiz servo limitleri:
# SERVO9  PAN  AUX1  MIN=450  MAX=2500  TRIM=1500
# SERVO11 TILT AUX3  MIN=650  MAX=2000  TRIM=1300

import time as _limit_time
import threading as _limit_threading

try:
    from pymavlink import mavutil as _limit_mavutil
except Exception:
    _limit_mavutil = None

DETAS_PAN_SERVO = 9
DETAS_TILT_SERVO = 11

PAN_MIN_PWM = 450
PAN_MAX_PWM = 2500
PAN_CENTER_PWM = 1500

TILT_MIN_PWM = 650
TILT_MAX_PWM = 2000
TILT_CENTER_PWM = 1300

PAN_LEFT_PWM = PAN_MIN_PWM
PAN_RIGHT_PWM = PAN_MAX_PWM

TILT_UP_PWM = TILT_MIN_PWM
TILT_DOWN_PWM = TILT_MAX_PWM

DETAS_MAVLINK_PORT = "/dev/ttyAMA4"
DETAS_MAVLINK_BAUD = 57600

_limit_servo_master = None
_limit_servo_lock = _limit_threading.Lock()
_limit_scan_stop = _limit_threading.Event()
_limit_scan_thread = None


def _limit_log(msg):
    try:
        add_log(str(msg))
    except Exception:
        print("[DETAS SERVO LIMIT]", msg)


def _limit_clamp(value, min_pwm, max_pwm):
    try:
        value = int(value)
    except Exception:
        value = 1500

    if value < min_pwm:
        value = min_pwm
    if value > max_pwm:
        value = max_pwm

    return value


def _limit_find_existing_master():
    for name, obj in list(globals().items()):
        if name.startswith("_limit"):
            continue

        try:
            if hasattr(obj, "mav") and hasattr(obj.mav, "command_long_send"):
                if getattr(obj, "target_system", 0):
                    return obj
        except Exception:
            pass

    return None


def _limit_get_master():
    global _limit_servo_master

    master = _limit_find_existing_master()
    if master is not None:
        return master

    if _limit_servo_master is not None:
        return _limit_servo_master

    if _limit_mavutil is None:
        raise RuntimeError("pymavlink yüklü değil")

    _limit_log("Servo için MAVLink bağlantısı açılıyor")

    _limit_servo_master = _limit_mavutil.mavlink_connection(
        DETAS_MAVLINK_PORT,
        baud=DETAS_MAVLINK_BAUD
    )

    _limit_servo_master.wait_heartbeat(timeout=10)

    _limit_log("Servo MAVLink bağlantısı hazır")

    return _limit_servo_master


def detas_send_servo_pwm(servo_number, pwm):
    servo_number = int(servo_number)

    if servo_number == DETAS_PAN_SERVO:
        pwm = _limit_clamp(pwm, PAN_MIN_PWM, PAN_MAX_PWM)
    elif servo_number == DETAS_TILT_SERVO:
        pwm = _limit_clamp(pwm, TILT_MIN_PWM, TILT_MAX_PWM)
    else:
        pwm = _limit_clamp(pwm, 800, 2200)

    with _limit_servo_lock:
        master = _limit_get_master()

        target_system = getattr(master, "target_system", 1) or 1
        target_component = getattr(master, "target_component", 1) or 1

        master.mav.command_long_send(
            target_system,
            target_component,
            _limit_mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
            0,
            servo_number,
            pwm,
            0,
            0,
            0,
            0,
            0
        )

    _limit_log(f"SERVO{servo_number} PWM gönderildi: {pwm}")

    return {
        "ok": True,
        "servo_number": servo_number,
        "pwm": pwm
    }


def detas_set_pan(pwm):
    result = detas_send_servo_pwm(DETAS_PAN_SERVO, pwm)
    result["servo"] = "pan"
    return result


def detas_set_tilt(pwm):
    result = detas_send_servo_pwm(DETAS_TILT_SERVO, pwm)
    result["servo"] = "tilt"
    return result


def detas_servo_center():
    _limit_scan_stop.set()
    detas_set_pan(PAN_CENTER_PWM)
    _limit_time.sleep(0.15)
    detas_set_tilt(TILT_CENTER_PWM)

    return {
        "ok": True,
        "mode": "center",
        "pan": PAN_CENTER_PWM,
        "tilt": TILT_CENTER_PWM
    }


def detas_servo_stop():
    _limit_scan_stop.set()

    return {
        "ok": True,
        "mode": "stop"
    }


def _limit_scan_worker(mode):
    _limit_scan_stop.clear()

    try:
        if mode == "pan":
            while not _limit_scan_stop.is_set():
                detas_set_pan(PAN_LEFT_PWM)
                _limit_time.sleep(1.2)

                if _limit_scan_stop.is_set():
                    break

                detas_set_pan(PAN_RIGHT_PWM)
                _limit_time.sleep(1.2)

        elif mode == "tilt":
            while not _limit_scan_stop.is_set():
                detas_set_tilt(TILT_UP_PWM)
                _limit_time.sleep(1.2)

                if _limit_scan_stop.is_set():
                    break

                detas_set_tilt(TILT_DOWN_PWM)
                _limit_time.sleep(1.2)

        elif mode == "full":
            while not _limit_scan_stop.is_set():
                detas_set_pan(PAN_LEFT_PWM)
                detas_set_tilt(TILT_UP_PWM)
                _limit_time.sleep(1.2)

                if _limit_scan_stop.is_set():
                    break

                detas_set_pan(PAN_RIGHT_PWM)
                detas_set_tilt(TILT_DOWN_PWM)
                _limit_time.sleep(1.2)

    except Exception as e:
        _limit_log(f"Tarama hatası: {e}")


def _limit_start_scan(mode):
    global _limit_scan_thread

    _limit_scan_stop.set()
    _limit_time.sleep(0.15)
    _limit_scan_stop.clear()

    _limit_scan_thread = _limit_threading.Thread(
        target=_limit_scan_worker,
        args=(mode,),
        daemon=True
    )
    _limit_scan_thread.start()

    return {
        "ok": True,
        "mode": mode
    }


def detas_scan_pan_slow():
    return _limit_start_scan("pan")


def detas_scan_tilt_slow():
    return _limit_start_scan("tilt")


def detas_scan_full_slow():
    return _limit_start_scan("full")


# Eski isimleri de yeni temiz fonksiyonlara bağla
send_servo_pwm = detas_send_servo_pwm
set_servo_pwm = detas_send_servo_pwm
move_pan = detas_set_pan
move_tilt = detas_set_tilt
servo_center = detas_servo_center
center_servos = detas_servo_center
stop_servo_scan = detas_servo_stop
scan_pan_slow = detas_scan_pan_slow
scan_tilt_slow = detas_scan_tilt_slow
scan_full_slow = detas_scan_full_slow

# ===== DETAS SERVO LIMIT OVERRIDE V2 END =====


# ===== DETAS SLOW SCAN OVERRIDE START =====
# Pan-Tilt tarama modlarını yavaş ve kademeli hale getirir.
# Eski hızlı uçtan uca atlama yerine servo adım adım ilerler.

import time as _slow_scan_time
import threading as _slow_scan_threading

SLOW_SCAN_PAN_STEP = 50
SLOW_SCAN_TILT_STEP = 35
SLOW_SCAN_DELAY = 0.18

_slow_scan_stop = _slow_scan_threading.Event()
_slow_scan_thread = None


def _slow_scan_log(msg):
    try:
        add_log(str(msg))
    except Exception:
        print("[DETAS SLOW SCAN]", msg)


def _slow_range(start, end, step):
    start = int(start)
    end = int(end)
    step = abs(int(step))

    if start <= end:
        value = start
        while value <= end:
            yield value
            value += step
        if value - step != end:
            yield end
    else:
        value = start
        while value >= end:
            yield value
            value -= step
        if value + step != end:
            yield end


def _slow_sleep():
    total = SLOW_SCAN_DELAY
    small = 0.03
    passed = 0

    while passed < total:
        if _slow_scan_stop.is_set():
            break

        _slow_scan_time.sleep(small)
        passed += small


def _slow_pan_sweep_once(left, right):
    for pwm in _slow_range(left, right, SLOW_SCAN_PAN_STEP):
        if _slow_scan_stop.is_set():
            break

        detas_set_pan(pwm)
        _slow_sleep()

    for pwm in _slow_range(right, left, SLOW_SCAN_PAN_STEP):
        if _slow_scan_stop.is_set():
            break

        detas_set_pan(pwm)
        _slow_sleep()


def _slow_tilt_sweep_once(up, down):
    for pwm in _slow_range(up, down, SLOW_SCAN_TILT_STEP):
        if _slow_scan_stop.is_set():
            break

        detas_set_tilt(pwm)
        _slow_sleep()

    for pwm in _slow_range(down, up, SLOW_SCAN_TILT_STEP):
        if _slow_scan_stop.is_set():
            break

        detas_set_tilt(pwm)
        _slow_sleep()


def _slow_full_sweep_once(left, right, up, down):
    # Sol üstten sağ alta doğru yumuşak çapraz tarama
    pan_values = list(_slow_range(left, right, SLOW_SCAN_PAN_STEP))
    tilt_values = list(_slow_range(up, down, max(20, SLOW_SCAN_TILT_STEP)))

    max_len = max(len(pan_values), len(tilt_values))

    for i in range(max_len):
        if _slow_scan_stop.is_set():
            break

        pan_pwm = pan_values[min(i, len(pan_values) - 1)]
        tilt_pwm = tilt_values[min(i, len(tilt_values) - 1)]

        detas_set_pan(pan_pwm)
        detas_set_tilt(tilt_pwm)
        _slow_sleep()

    # Sağ alttan sol üste dönüş
    pan_values.reverse()
    tilt_values.reverse()

    for i in range(max_len):
        if _slow_scan_stop.is_set():
            break

        pan_pwm = pan_values[min(i, len(pan_values) - 1)]
        tilt_pwm = tilt_values[min(i, len(tilt_values) - 1)]

        detas_set_pan(pan_pwm)
        detas_set_tilt(tilt_pwm)
        _slow_sleep()


def _slow_scan_worker(mode):
    try:
        _slow_scan_log(f"Yavaş tarama başladı: {mode}")

        left = globals().get("PAN_LEFT_PWM", 450)
        right = globals().get("PAN_RIGHT_PWM", 2500)
        up = globals().get("TILT_UP_PWM", 650)
        down = globals().get("TILT_DOWN_PWM", 2000)

        while not _slow_scan_stop.is_set():
            if mode == "pan":
                _slow_pan_sweep_once(left, right)

            elif mode == "tilt":
                _slow_tilt_sweep_once(up, down)

            elif mode == "full":
                _slow_full_sweep_once(left, right, up, down)

            else:
                break

    except Exception as e:
        _slow_scan_log(f"Yavaş tarama hatası: {e}")


def _slow_start_scan(mode):
    global _slow_scan_thread

    try:
        _limit_scan_stop.set()
    except Exception:
        pass

    _slow_scan_stop.set()
    _slow_scan_time.sleep(0.15)
    _slow_scan_stop.clear()

    _slow_scan_thread = _slow_scan_threading.Thread(
        target=_slow_scan_worker,
        args=(mode,),
        daemon=True
    )
    _slow_scan_thread.start()

    return {
        "ok": True,
        "mode": mode,
        "speed": "slow",
        "pan_step": SLOW_SCAN_PAN_STEP,
        "tilt_step": SLOW_SCAN_TILT_STEP,
        "delay": SLOW_SCAN_DELAY
    }


def detas_scan_pan_slow():
    return _slow_start_scan("pan")


def detas_scan_tilt_slow():
    return _slow_start_scan("tilt")


def detas_scan_full_slow():
    return _slow_start_scan("full")


def detas_servo_stop():
    try:
        _limit_scan_stop.set()
    except Exception:
        pass

    _slow_scan_stop.set()

    return {
        "ok": True,
        "mode": "stop"
    }


# Eski isimleri de yeni yavaş taramaya bağla
scan_pan_slow = detas_scan_pan_slow
scan_tilt_slow = detas_scan_tilt_slow
scan_full_slow = detas_scan_full_slow
stop_servo_scan = detas_servo_stop
servo_stop = detas_servo_stop

# ===== DETAS SLOW SCAN OVERRIDE END =====


# ===== DETAS SERVO SAFE LIMIT FINAL START =====
# Güvenli pan-tilt çalışma aralığı.
# Mission Planner uç limitleri geniş olduğu için panelde daha dar operasyon limiti kullanıyoruz.

import time as _safe_servo_time
import threading as _safe_servo_threading

try:
    from pymavlink import mavutil as _safe_mavutil
except Exception:
    _safe_mavutil = None

DETAS_PAN_SERVO = 9
DETAS_TILT_SERVO = 11

PAN_MIN_PWM = 800
PAN_MAX_PWM = 2200
PAN_CENTER_PWM = 1500

TILT_MIN_PWM = 800
TILT_MAX_PWM = 1800
TILT_CENTER_PWM = 1300

DETAS_MAVLINK_PORT = "/dev/ttyAMA4"
DETAS_MAVLINK_BAUD = 57600

_safe_servo_master = None
_safe_servo_lock = _safe_servo_threading.Lock()
_safe_scan_stop = _safe_servo_threading.Event()
_safe_scan_thread = None


def _safe_log(msg):
    try:
        add_log(str(msg))
    except Exception:
        print("[DETAS SERVO SAFE]", msg)


def _safe_clamp(value, min_pwm, max_pwm):
    try:
        value = int(value)
    except Exception:
        value = 1500

    if value < min_pwm:
        value = min_pwm

    if value > max_pwm:
        value = max_pwm

    return value


def _safe_find_master():
    for name, obj in list(globals().items()):
        if name.startswith("_safe"):
            continue

        try:
            if hasattr(obj, "mav") and hasattr(obj.mav, "command_long_send"):
                if getattr(obj, "target_system", 0):
                    return obj
        except Exception:
            pass

    return None


def _safe_get_master():
    global _safe_servo_master

    master = _safe_find_master()
    if master is not None:
        return master

    if _safe_servo_master is not None:
        return _safe_servo_master

    if _safe_mavutil is None:
        raise RuntimeError("pymavlink yüklü değil")

    _safe_log("Servo için MAVLink bağlantısı açılıyor")

    _safe_servo_master = _safe_mavutil.mavlink_connection(
        DETAS_MAVLINK_PORT,
        baud=DETAS_MAVLINK_BAUD
    )

    _safe_servo_master.wait_heartbeat(timeout=10)

    _safe_log("Servo MAVLink bağlantısı hazır")

    return _safe_servo_master


def detas_send_servo_pwm(servo_number, pwm):
    servo_number = int(servo_number)

    if servo_number == DETAS_PAN_SERVO:
        pwm = _safe_clamp(pwm, PAN_MIN_PWM, PAN_MAX_PWM)
    elif servo_number == DETAS_TILT_SERVO:
        pwm = _safe_clamp(pwm, TILT_MIN_PWM, TILT_MAX_PWM)
    else:
        pwm = _safe_clamp(pwm, 800, 2200)

    with _safe_servo_lock:
        master = _safe_get_master()

        target_system = getattr(master, "target_system", 1) or 1
        target_component = getattr(master, "target_component", 1) or 1

        master.mav.command_long_send(
            target_system,
            target_component,
            _safe_mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
            0,
            servo_number,
            pwm,
            0,
            0,
            0,
            0,
            0
        )

    _safe_log(f"SERVO{servo_number} PWM gönderildi: {pwm}")

    return {
        "ok": True,
        "servo_number": servo_number,
        "pwm": pwm
    }


def detas_set_pan(pwm):
    result = detas_send_servo_pwm(DETAS_PAN_SERVO, pwm)
    result["servo"] = "pan"
    return result


def detas_set_tilt(pwm):
    result = detas_send_servo_pwm(DETAS_TILT_SERVO, pwm)
    result["servo"] = "tilt"
    return result


def detas_servo_center():
    _safe_scan_stop.set()
    detas_set_pan(PAN_CENTER_PWM)
    _safe_servo_time.sleep(0.12)
    detas_set_tilt(TILT_CENTER_PWM)

    return {
        "ok": True,
        "mode": "center",
        "pan": PAN_CENTER_PWM,
        "tilt": TILT_CENTER_PWM
    }


def detas_servo_stop():
    _safe_scan_stop.set()
    return {
        "ok": True,
        "mode": "stop"
    }


def _safe_range(start, end, step):
    start = int(start)
    end = int(end)
    step = abs(int(step))

    if start <= end:
        x = start
        while x <= end:
            yield x
            x += step
        if x - step != end:
            yield end
    else:
        x = start
        while x >= end:
            yield x
            x -= step
        if x + step != end:
            yield end


def _safe_sleep(delay):
    passed = 0
    unit = 0.03

    while passed < delay:
        if _safe_scan_stop.is_set():
            break

        _safe_servo_time.sleep(unit)
        passed += unit


def _safe_scan_worker(mode):
    try:
        _safe_log(f"Yavaş tarama başladı: {mode}")

        pan_left = 900
        pan_right = 2100
        tilt_up = 900
        tilt_down = 1700

        pan_step = 35
        tilt_step = 30
        delay = 0.24

        while not _safe_scan_stop.is_set():
            if mode == "pan":
                for pwm in _safe_range(pan_left, pan_right, pan_step):
                    if _safe_scan_stop.is_set():
                        break
                    detas_set_pan(pwm)
                    _safe_sleep(delay)

                for pwm in _safe_range(pan_right, pan_left, pan_step):
                    if _safe_scan_stop.is_set():
                        break
                    detas_set_pan(pwm)
                    _safe_sleep(delay)

            elif mode == "tilt":
                for pwm in _safe_range(tilt_up, tilt_down, tilt_step):
                    if _safe_scan_stop.is_set():
                        break
                    detas_set_tilt(pwm)
                    _safe_sleep(delay)

                for pwm in _safe_range(tilt_down, tilt_up, tilt_step):
                    if _safe_scan_stop.is_set():
                        break
                    detas_set_tilt(pwm)
                    _safe_sleep(delay)

            elif mode == "full":
                for pan_pwm in _safe_range(pan_left, pan_right, pan_step):
                    if _safe_scan_stop.is_set():
                        break

                    detas_set_pan(pan_pwm)

                    for tilt_pwm in _safe_range(tilt_up, tilt_down, tilt_step):
                        if _safe_scan_stop.is_set():
                            break
                        detas_set_tilt(tilt_pwm)
                        _safe_sleep(0.12)

                for pan_pwm in _safe_range(pan_right, pan_left, pan_step):
                    if _safe_scan_stop.is_set():
                        break

                    detas_set_pan(pan_pwm)

                    for tilt_pwm in _safe_range(tilt_down, tilt_up, tilt_step):
                        if _safe_scan_stop.is_set():
                            break
                        detas_set_tilt(tilt_pwm)
                        _safe_sleep(0.12)

            else:
                break

    except Exception as e:
        _safe_log(f"Tarama hatası: {e}")


def _safe_start_scan(mode):
    global _safe_scan_thread

    _safe_scan_stop.set()
    _safe_servo_time.sleep(0.15)
    _safe_scan_stop.clear()

    _safe_scan_thread = _safe_servo_threading.Thread(
        target=_safe_scan_worker,
        args=(mode,),
        daemon=True
    )
    _safe_scan_thread.start()

    return {
        "ok": True,
        "mode": mode,
        "speed": "slow_safe"
    }


def detas_scan_pan_slow():
    return _safe_start_scan("pan")


def detas_scan_tilt_slow():
    return _safe_start_scan("tilt")


def detas_scan_full_slow():
    return _safe_start_scan("full")


send_servo_pwm = detas_send_servo_pwm
set_servo_pwm = detas_send_servo_pwm
move_pan = detas_set_pan
move_tilt = detas_set_tilt
servo_center = detas_servo_center
center_servos = detas_servo_center
stop_servo_scan = detas_servo_stop
servo_stop = detas_servo_stop
scan_pan_slow = detas_scan_pan_slow
scan_tilt_slow = detas_scan_tilt_slow
scan_full_slow = detas_scan_full_slow

# ===== DETAS SERVO SAFE LIMIT FINAL END =====


# ===== DETAS DISABLE AUTO MOTOR TEST AFTER QUAKE START =====
# Deprem sonrası motorları sırayla döndürme ve otomatik disarm kapalı.
# Sistem sadece ARM komutu gönderir; Cube görev/rota mantığı ayrıca yönetilir.

AUTO_ARM_ON_EARTHQUAKE = True
AUTO_MOTOR_SPIN_TEST_ON_EARTHQUAKE = False
AUTO_MOTOR_TEST_ON_EARTHQUAKE = False
AUTO_DISARM_AFTER_MOTOR_TEST = False
MOTOR_TEST_AUTO_DISARM = False
AUTO_MISSION_DISARM_AFTER_TEST = False

def detas_motor_test_disabled_after_quake(*args, **kwargs):
    try:
        add_log("Otomatik motor test devre dışı: deprem sonrası sadece ARM modu aktif")
    except Exception:
        print("Otomatik motor test devre dışı")
    return {
        "ok": True,
        "skipped": True,
        "message": "Otomatik motor test devre dışı; deprem sonrası sadece ARM gönderiliyor"
    }

# Muhtemel eski otomatik motor test fonksiyon isimlerini güvenli no-op yap.
auto_motor_spin_test = detas_motor_test_disabled_after_quake
auto_motor_test_after_earthquake = detas_motor_test_disabled_after_quake
run_auto_motor_test = detas_motor_test_disabled_after_quake
start_auto_motor_test = detas_motor_test_disabled_after_quake
earthquake_motor_test = detas_motor_test_disabled_after_quake
# ===== DETAS DISABLE AUTO MOTOR TEST AFTER QUAKE END =====

