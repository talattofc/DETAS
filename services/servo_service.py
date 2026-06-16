"""Orange Cube AUX1 uzerindeki tek kamera servo kontrol servisi."""

import threading
import time

from services import mavlink_service
from services.logger_service import add_log
from services.state import state


SERVO_NUMBER = 9

PWM_MIN = 1250
PWM_MAX = 2600
PWM_FORWARD = 2400
PWM_DOWN = 1400

SCAN_STEP = 50
SCAN_DELAY = 0.45
SCAN_PAUSE = 0.2

_lock = threading.RLock()
_scan_stop = threading.Event()
_scan_thread = None


def _clamp_pwm(pwm):
    try:
        pwm = int(pwm)
    except Exception:
        pwm = PWM_FORWARD

    return max(PWM_MIN, min(PWM_MAX, pwm))


def _update_state(**kwargs):
    try:
        state.update(**kwargs)
    except Exception:
        pass


def set_position(pwm):
    """SERVO9 / AUX1 cikisina tek eksenli kamera PWM komutu gonderir."""
    pwm = _clamp_pwm(pwm)

    with _lock:
        result = mavlink_service.send_servo_pwm(SERVO_NUMBER, pwm)

        if result.get("ok"):
            _update_state(
                servo_pwm=pwm,
                single_servo_pwm=pwm,
                servo_pan=pwm,
                servo_tilt=pwm,
                servo_number=SERVO_NUMBER,
                servo_mode="single_aux1_vertical",
            )

        add_log(f"SERVO9 AUX1 PWM -> {pwm}")

        return {
            **result,
            "ok": bool(result.get("ok")),
            "servo": "single_aux1_vertical",
            "servo_number": SERVO_NUMBER,
            "pwm": pwm,
        }


def servo_center():
    servo_stop()
    return set_position(PWM_FORWARD)


def _scan_values(start, end, step):
    if start <= end:
        return range(start, end + 1, step)

    return range(start, end - 1, -step)


def _scan_loop():
    add_log("SERVO9 dikey tarama basladi: 1400-2400 PWM")
    _update_state(servo_scan_active=True, servo_scan_mode="vertical_1400_2400")

    try:
        while not _scan_stop.is_set():
            for pwm in _scan_values(PWM_DOWN, PWM_FORWARD, SCAN_STEP):
                if _scan_stop.is_set():
                    break

                set_position(pwm)
                time.sleep(SCAN_DELAY)

            time.sleep(SCAN_PAUSE)

            for pwm in _scan_values(PWM_FORWARD, PWM_DOWN, SCAN_STEP):
                if _scan_stop.is_set():
                    break

                set_position(pwm)
                time.sleep(SCAN_DELAY)

            time.sleep(SCAN_PAUSE)
    finally:
        _update_state(servo_scan_active=False, servo_scan_mode="stop")
        add_log("SERVO9 dikey tarama durdu")


def servo_scan():
    global _scan_thread, _scan_stop

    servo_stop()
    time.sleep(0.1)

    _scan_stop = threading.Event()
    _scan_thread = threading.Thread(target=_scan_loop, daemon=True)
    _scan_thread.start()

    return {
        "ok": True,
        "mode": "vertical_1400_2400",
        "servo_number": SERVO_NUMBER,
        "scan_min": PWM_DOWN,
        "scan_max": PWM_FORWARD,
        "step": SCAN_STEP,
        "delay": SCAN_DELAY,
        "message": "Tek servo dikey tarama baslatildi",
    }


def servo_stop():
    _scan_stop.set()
    _update_state(servo_scan_active=False, servo_scan_mode="stop")

    return {
        "ok": True,
        "mode": "stop",
        "message": "Tek servo tarama durduruldu",
    }


def get_status():
    data = state.snapshot()

    return {
        "ok": True,
        "mode": "single_aux1_vertical",
        "servo_number": SERVO_NUMBER,
        "min_pwm": PWM_MIN,
        "max_pwm": PWM_MAX,
        "forward_pwm": PWM_FORWARD,
        "down_pwm": PWM_DOWN,
        "scan_min": PWM_DOWN,
        "scan_max": PWM_FORWARD,
        "scan_step": SCAN_STEP,
        "scan_delay": SCAN_DELAY,
        "current_pwm": data.get("servo_pwm", PWM_FORWARD),
        "scan_active": data.get("servo_scan_active", False),
        "scan_mode": data.get("servo_scan_mode", "stop"),
    }
