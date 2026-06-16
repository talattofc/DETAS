import time
import threading

from services.state import state
from services.logger_service import add_log
from services import mavlink_service


# ============================================================
# DETAS TEK SERVO AYARI
# ============================================================
# Cube AUX OUT 1 = SERVO9

SERVO_NUMBER = 9

PWM_MIN = 1250
PWM_MAX = 2600

PWM_CENTER = 2400      # karşıya bakış
PWM_DOWN = 1400        # aşağı bakış

BUTTON_STEP = 100
SCAN_STEP = 100
SCAN_DELAY = 0.35

_scan_thread = None
_scan_stop = threading.Event()
_lock = threading.RLock()


# ============================================================
# STATE
# ============================================================

def _state_update(**kwargs):
    try:
        if hasattr(state, "update"):
            state.update(**kwargs)
            return
    except Exception:
        pass

    try:
        for k, v in kwargs.items():
            setattr(state, k, v)
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


def _clamp_pwm(pwm):
    try:
        pwm = int(pwm)
    except Exception:
        pwm = PWM_CENTER

    if pwm < PWM_MIN:
        pwm = PWM_MIN

    if pwm > PWM_MAX:
        pwm = PWM_MAX

    return pwm


def _current_pwm():
    data = _state_snapshot()

    for key in [
        "single_servo_pwm",
        "servo_pan",
        "pan_pwm",
        "servo_tilt",
        "tilt_pwm",
    ]:
        try:
            value = data.get(key)
            if value is not None and value != "":
                return int(value)
        except Exception:
            pass

    return PWM_CENTER


# ============================================================
# TEK SERVO KOMUTU
# ============================================================

def set_position(pwm):
    """
    Tek servo hareket komutu.
    Her zaman SERVO9 / AUX1 çıkışına PWM gönderir.
    """
    pwm = _clamp_pwm(pwm)

    with _lock:
        result = mavlink_service.send_servo_pwm(SERVO_NUMBER, pwm)

        if result.get("ok"):
            _state_update(
                single_servo_pwm=pwm,
                servo_pan=pwm,
                pan_pwm=pwm,
                current_pan_pwm=pwm,
                servo_tilt=pwm,
                tilt_pwm=pwm,
                current_tilt_pwm=pwm,
                servo_number=SERVO_NUMBER,
                servo_mode="single_aux1",
            )

        add_log(f"TEK SERVO AUX1 / SERVO9 -> {pwm}")

        return {
            **result,
            "ok": bool(result.get("ok")),
            "servo": "single_aux1",
            "servo_number": SERVO_NUMBER,
            "pwm": pwm
        }


# Slider route uyumluluğu
def servo_pan(pwm):
    return set_position(pwm)


def servo_tilt(pwm):
    return set_position(pwm)


def set_pan(pwm):
    return set_position(pwm)


def set_tilt(pwm):
    return set_position(pwm)


# ============================================================
# BUTONLAR
# ============================================================

def servo_up():
    pwm = _current_pwm() + BUTTON_STEP
    return set_position(pwm)


def servo_down():
    pwm = _current_pwm() - BUTTON_STEP
    return set_position(pwm)


def tilt_up():
    return servo_up()


def tilt_down():
    return servo_down()


def servo_center():
    stop_servo_scan()
    return set_position(PWM_CENTER)


def center_servo():
    return servo_center()


def center_servos():
    return servo_center()


def servo_left():
    return {
        "ok": True,
        "message": "Tek servo modunda sağ-sol pasif"
    }


def servo_right():
    return {
        "ok": True,
        "message": "Tek servo modunda sağ-sol pasif"
    }


def pan_left():
    return servo_left()


def pan_right():
    return servo_right()


# ============================================================
# TARAMA
# ============================================================

def _scan_loop():
    """
    Arduino testindeki mantığın Python / MAVLink karşılığı.
    1400 -> 2400 -> 1400 arası 100 PWM adımla sürekli tarar.
    """
    add_log("TEK SERVO TARAMA BAŞLADI: SERVO9 / 1400 ↔ 2400")

    _state_update(
        servo_scan_active=True,
        servo_scan_mode="single_servo_vertical_scan",
    )

    try:
        while not _scan_stop.is_set():

            # Aşağıdan karşıya: 1400 -> 2400
            for pwm in range(PWM_DOWN, PWM_CENTER + 1, SCAN_STEP):
                if _scan_stop.is_set():
                    break

                set_position(pwm)
                time.sleep(SCAN_DELAY)

            time.sleep(0.15)

            # Karşıdan aşağıya: 2400 -> 1400
            for pwm in range(PWM_CENTER, PWM_DOWN - 1, -SCAN_STEP):
                if _scan_stop.is_set():
                    break

                set_position(pwm)
                time.sleep(SCAN_DELAY)

            time.sleep(0.15)

    finally:
        _state_update(
            servo_scan_active=False,
            servo_scan_mode="stop",
        )

        add_log("TEK SERVO TARAMA DURDU")


def servo_scan():
    global _scan_thread, _scan_stop

    stop_servo_scan()
    time.sleep(0.1)

    _scan_stop = threading.Event()

    _scan_thread = threading.Thread(
        target=_scan_loop,
        daemon=True
    )
    _scan_thread.start()

    return {
        "ok": True,
        "mode": "single_servo_vertical_scan",
        "servo_number": SERVO_NUMBER,
        "range": [PWM_DOWN, PWM_CENTER],
        "step": SCAN_STEP,
        "message": "Tek servo tarama başlatıldı"
    }


def stop_servo_scan():
    global _scan_stop

    _scan_stop.set()

    _state_update(
        servo_scan_active=False,
        servo_scan_mode="stop",
    )

    add_log("Tek servo tarama stop komutu")

    return {
        "ok": True,
        "mode": "stop",
        "message": "Tek servo tarama durduruldu"
    }


def servo_stop():
    return stop_servo_scan()


def stop_servo():
    return stop_servo_scan()


# Eski route isimleri
def scan_servo():
    return servo_scan()


def start_servo_scan():
    return servo_scan()


def servo_scan_full():
    return servo_scan()


def servo_scan_pan_slow():
    return servo_scan()


def servo_scan_tilt_slow():
    return servo_scan()


def servo_scan_full_slow():
    return servo_scan()


# ============================================================
# DURUM
# ============================================================

def get_servo_status():
    data = _state_snapshot()

    return {
        "ok": True,
        "mode": "single_aux1",
        "servo_number": SERVO_NUMBER,
        "min_pwm": PWM_MIN,
        "max_pwm": PWM_MAX,
        "center_pwm": PWM_CENTER,
        "down_pwm": PWM_DOWN,
        "scan_min": PWM_DOWN,
        "scan_max": PWM_CENTER,
        "step": SCAN_STEP,
        "current_pwm": data.get("single_servo_pwm", PWM_CENTER),
        "scan_active": data.get("servo_scan_active", False),
        "scan_mode": data.get("servo_scan_mode", "stop")
    }


def get_status():
    return get_servo_status()
