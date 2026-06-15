import time
import threading

from services.state import state

try:
    from services.logger_service import add_log
except Exception:
    def add_log(msg):
        print("[MISSION STATUS]", msg)


_thread_started = False
_thread_lock = threading.Lock()


def _snapshot():
    try:
        if hasattr(state, "snapshot"):
            return state.snapshot()
        if hasattr(state, "to_dict"):
            return state.to_dict()
    except Exception:
        pass

    try:
        return dict(state.__dict__)
    except Exception:
        return {}


def _update_state(**kwargs):
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


def _as_bool(value):
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value > 0

    if isinstance(value, str):
        return value.strip().lower() in [
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

    return False


def _get_float(data, key, default=0.0):
    try:
        return float(data.get(key, default))
    except Exception:
        return default


def _is_quake_active(data):
    movement = _get_float(data, "movement", 0.0)
    threshold = _get_float(data, "threshold", 1.5)

    direct_flags = [
        "deprem",
        "earthquake",
        "quake_detected",
        "earthquake_detected",
        "alarm",
        "sarsinti_alarm",
    ]

    for key in direct_flags:
        if key in data and _as_bool(data.get(key)):
            return True

    return movement >= threshold


def _is_cube_armed(data):
    for key in ["cube_armed", "armed", "is_armed"]:
        if key in data:
            return _as_bool(data.get(key))

    arm_status = str(data.get("cube_arm_status", "")).upper()

    if "ARMED" in arm_status and "DISARMED" not in arm_status:
        return True

    return False


def _worker():
    add_log("Görev durumu takip sistemi başlatıldı")

    last_status = None
    quake_latched = False
    arm_sent_latched = False
    last_quake_time = 0.0
    last_reset_time = 0.0

    while True:
        try:
            data = _snapshot()

            quake = _is_quake_active(data)
            armed = _is_cube_armed(data)
            movement = _get_float(data, "movement", 0.0)
            threshold = _get_float(data, "threshold", 1.5)

            now = time.time()

            if quake:
                quake_latched = True
                last_quake_time = now

                if armed:
                    status = "GÖREVDE"
                    arm_sent_latched = True
                else:
                    status = "ARM KOMUTU GÖNDERİLDİ"
                    arm_sent_latched = True

            else:
                if armed:
                    status = "GÖREVDE"
                else:
                    if quake_latched and now - last_quake_time < 5:
                        status = "YENİDEN HAZIRLANIYOR"
                    else:
                        status = "BEKLEMEDE"
                        quake_latched = False
                        arm_sent_latched = False
                        last_reset_time = now

            _update_state(
                mission_status=status,
                auto_mission_status=status,
                mission_ready=(status == "BEKLEMEDE"),
                mission_armed=armed,
                mission_quake_detected=quake or quake_latched,
                mission_last_movement=movement,
                mission_threshold=threshold,
            )

            if status != last_status:
                add_log(f"Görev durumu: {status}")
                last_status = status

            time.sleep(0.5)

        except Exception as e:
            add_log(f"Görev durumu takip hatası: {e}")
            time.sleep(1.0)


def start_mission_status_service():
    global _thread_started

    with _thread_lock:
        if _thread_started:
            return

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        _thread_started = True
