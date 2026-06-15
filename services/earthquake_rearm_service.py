import time
import threading

try:
    from pymavlink import mavutil
except Exception:
    mavutil = None

from services.state import state

try:
    from services.logger_service import add_log
except Exception:
    def add_log(msg):
        print("[AUTO REARM]", msg)


AUTO_REARM_INTERVAL = 0.4
AUTO_REARM_COOLDOWN = 8.0
RESET_STABLE_SECONDS = 2.0

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


def _as_bool(value):
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value > 0

    if isinstance(value, str):
        t = value.strip().lower()
        return t in [
            "true",
            "1",
            "yes",
            "evet",
            "deprem",
            "alarm",
            "aktif",
            "detected",
            "earthquake",
        ]

    return False


def _quake_active(data):
    bool_keys = [
        "deprem",
        "earthquake",
        "quake",
        "is_earthquake",
        "earthquake_detected",
        "quake_detected",
        "alarm",
        "earthquake_alarm",
        "sarsinti",
        "sarsinti_alarm",
    ]

    for key in bool_keys:
        if key in data and _as_bool(data.get(key)):
            return True

    status_keys = [
        "mission_status",
        "earthquake_status",
        "deprem_status",
        "status",
    ]

    for key in status_keys:
        value = str(data.get(key, "")).lower()
        if "deprem" in value or "earthquake" in value or "alarm" in value:
            return True

    try:
        movement = float(
            data.get("movement",
                data.get("sarsinti",
                    data.get("shake",
                        data.get("max_movement", 0)
                    )
                )
            )
        )
    except Exception:
        movement = 0.0

    try:
        threshold = float(data.get("threshold", data.get("deprem_threshold", 1.5)))
    except Exception:
        threshold = 1.5

    return movement >= threshold


def _cube_armed(data):
    for key in ["cube_armed", "armed", "is_armed"]:
        if key in data:
            return _as_bool(data.get(key))

    return False


def _find_existing_master(mavlink_service):
    for name, obj in list(vars(mavlink_service).items()):
        if name.startswith("_"):
            continue

        try:
            if hasattr(obj, "mav") and hasattr(obj.mav, "command_long_send"):
                return obj
        except Exception:
            pass

    return None


def _send_arm():
    from services import mavlink_service

    candidates = [
        "send_arm_command",
        "arm_vehicle",
        "set_arm",
        "arm",
    ]

    for name in candidates:
        fn = getattr(mavlink_service, name, None)

        if not callable(fn):
            continue

        try:
            result = fn(arm=True)
            add_log(f"Otomatik tekrar ARM gönderildi: {name}")
            return True, result
        except TypeError:
            try:
                result = fn(True)
                add_log(f"Otomatik tekrar ARM gönderildi: {name}")
                return True, result
            except Exception:
                pass
        except Exception:
            pass

    if mavutil is None:
        return False, "pymavlink yok"

    master = _find_existing_master(mavlink_service)

    if master is None:
        return False, "aktif MAVLink master bulunamadı"

    target_system = getattr(master, "target_system", 1) or 1
    target_component = getattr(master, "target_component", 1) or 1

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
        0
    )

    add_log("Otomatik tekrar ARM MAVLink ile gönderildi")
    return True, "direct_mavlink"


def _worker():
    add_log("Deprem tekrar ARM takipçisi başlatıldı")

    event_latched = False
    last_trigger_time = 0.0
    last_quake_seen = 0.0
    false_since = time.time()

    while True:
        try:
            data = _snapshot()

            quake = _quake_active(data)
            armed = _cube_armed(data)
            now = time.time()

            if quake:
                last_quake_seen = now
                false_since = None

                can_trigger_first = not event_latched
                can_trigger_retry = (not armed) and ((now - last_trigger_time) >= AUTO_REARM_COOLDOWN)

                if can_trigger_first or can_trigger_retry:
                    ok, result = _send_arm()
                    last_trigger_time = now
                    event_latched = True

                    if ok:
                        add_log("Deprem tetikleme: ARM komutu gönderildi")
                    else:
                        add_log(f"Deprem tetikleme: ARM gönderilemedi: {result}")

            else:
                if false_since is None:
                    false_since = now

                if event_latched and (now - false_since) >= RESET_STABLE_SECONDS:
                    event_latched = False
                    add_log("Deprem tetikleme sistemi yeniden hazır")

            time.sleep(AUTO_REARM_INTERVAL)

        except Exception as e:
            add_log(f"Deprem tekrar ARM takipçisi hata: {e}")
            time.sleep(1.0)


def start_earthquake_rearm_watcher():
    global _thread_started

    with _thread_lock:
        if _thread_started:
            return

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        _thread_started = True
