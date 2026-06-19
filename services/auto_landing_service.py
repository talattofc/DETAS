<<<<<<< HEAD
=======
<<<<<<< HEAD
=======
<<<<<<< HEAD
"""MZ80 ve Sharp mesafe verisiyle Cube uzerinden kontrollu inis yardimi."""

import threading
import time

import config
from services import mavlink_service
=======
>>>>>>> b896abad72cec15526c5edf83a4468593bc2771f
>>>>>>> f0d59af20d4cf5734ccecd4ca8398321ce4993b1
"""MZ80 yaklasma uyarisi servisi.

Bu servis MZ80 bilgisini yalnizca uyari/status olarak kullanir. Motor, throttle,
DISARM veya dogrudan inis kontrolu yapmaz.
"""

<<<<<<< HEAD
=======
<<<<<<< HEAD
=======
>>>>>>> 82cd033 (orange cube entegrasyonu otopilot)
>>>>>>> b896abad72cec15526c5edf83a4468593bc2771f
>>>>>>> f0d59af20d4cf5734ccecd4ca8398321ce4993b1
from services.logger_service import add_log
from services.state import state


<<<<<<< HEAD
=======
<<<<<<< HEAD
=======
<<<<<<< HEAD
_thread_lock = threading.RLock()
_worker_thread = None
_stop_event = threading.Event()


def _state_update(**kwargs):
    try:
        state.update(**kwargs)
    except Exception:
        pass


=======
>>>>>>> 82cd033 (orange cube entegrasyonu otopilot)
>>>>>>> b896abad72cec15526c5edf83a4468593bc2771f
>>>>>>> f0d59af20d4cf5734ccecd4ca8398321ce4993b1
def _snapshot():
    try:
        return state.snapshot()
    except Exception:
        return {}


<<<<<<< HEAD
=======
<<<<<<< HEAD
=======
<<<<<<< HEAD
def _sensor_is_fresh(data, now):
    last_time = float(data.get("landing_proximity_last_time") or 0.0)
    if last_time <= 0:
        return False
    return (now - last_time) <= float(config.AUTO_LANDING_SENSOR_TIMEOUT_SEC)


def _distance_cm(data):
    try:
        value = data.get("landing_nearest_distance_cm")
        if value is None:
            return None
        value = float(value)
        return value if value > 0 else None
    except Exception:
        return None


def _speed_for_distance(distance_cm):
    if distance_cm is None:
        return 0.0, "sensor_wait"

    if distance_cm <= float(config.AUTO_LANDING_HOLD_BELOW_CM):
        return 0.0, "hold"
    if distance_cm <= float(config.AUTO_LANDING_FINAL_BELOW_CM):
        return float(config.AUTO_LANDING_FINAL_DESCENT_MPS), "final"
    if distance_cm <= float(config.AUTO_LANDING_SLOW_BELOW_CM):
        return float(config.AUTO_LANDING_SLOW_DESCENT_MPS), "slow"
    return float(config.AUTO_LANDING_FAST_DESCENT_MPS), "descent"


def _phase_text(phase, distance_cm=None):
    distance = "-" if distance_cm is None else f"{distance_cm:.1f} cm"
    if phase == "sensor_wait":
        return "Sensor bekleniyor"
    if phase == "hold":
        return f"Tutma mesafesi ({distance})"
    if phase == "final":
        return f"Son yavas inis ({distance})"
    if phase == "slow":
        return f"Yavas inis ({distance})"
    if phase == "descent":
        return f"Kontrollu inis ({distance})"
    return "Hazir"


def _set_idle(status="Kapali", error=None):
=======
>>>>>>> b896abad72cec15526c5edf83a4468593bc2771f
>>>>>>> f0d59af20d4cf5734ccecd4ca8398321ce4993b1
def _state_update(**kwargs):
    try:
        state.update(**kwargs)
    except Exception:
        pass


def _warning_message():
    data = _snapshot()
    detected = bool(data.get("landing_mz80_detected"))
    try:
        distance = float(data.get("landing_mz80_distance_cm") or 0.0)
    except Exception:
        distance = 0.0

    if detected and distance:
        return f"MZ80 yere yaklasma uyarisi: {distance:.0f} cm icinde"
    if detected:
        return "MZ80 yere yaklasma uyarisi"
    return "MZ80 uyari modu aktif"


def start_auto_landing():
    """Geriye uyumluluk icin var; inis kontrolu baslatmaz, sadece uyari modu yazar."""
    message = _warning_message()
    _state_update(
        auto_landing_enabled=False,
        auto_landing_active=False,
        auto_landing_phase="warning_only",
        auto_landing_status=message,
        auto_landing_target_speed_mps=0.0,
        auto_landing_error=None,
    )
    add_log(f"{message}; otomatik inis kontrolu devre disi")
    return {
        "ok": True,
        "message": "MZ80 sadece uyari modunda; inis kontrolu gonderilmedi",
        "warning": message,
    }


def stop_auto_landing():
    """Uyari modunu pasife alir; herhangi bir ucus komutu gondermez."""
<<<<<<< HEAD
=======
<<<<<<< HEAD
=======
>>>>>>> 82cd033 (orange cube entegrasyonu otopilot)
>>>>>>> b896abad72cec15526c5edf83a4468593bc2771f
>>>>>>> f0d59af20d4cf5734ccecd4ca8398321ce4993b1
    _state_update(
        auto_landing_enabled=False,
        auto_landing_active=False,
        auto_landing_phase="idle",
<<<<<<< HEAD
=======
<<<<<<< HEAD
=======
<<<<<<< HEAD
        auto_landing_status=status,
        auto_landing_target_speed_mps=0.0,
        auto_landing_error=error,
    )


def _worker():
    started_mode = False

    try:
        _state_update(
            auto_landing_enabled=True,
            auto_landing_active=True,
            auto_landing_phase="starting",
            auto_landing_status="Baslatiliyor",
            auto_landing_error=None,
        )

        data = _snapshot()
        if config.AUTO_LANDING_REQUIRE_ARMED and not bool(data.get("cube_armed")):
            _set_idle("ARM degil", "Otomatik inis icin arac ARM olmali")
            add_log("Otomatik inis baslamadi: arac ARM degil")
            return

        if not bool(data.get("cube_connected")):
            _set_idle("Cube yok", "Cube MAVLink baglantisi yok")
            add_log("Otomatik inis baslamadi: Cube bagli degil")
            return

        if str(config.AUTO_LANDING_CONTROL_MODE).upper() == "GUIDED_VELOCITY":
            result = mavlink_service.set_mode(config.AUTO_LANDING_START_MODE)
            started_mode = bool(result.get("ok"))
            if not started_mode:
                _set_idle("Mod hatasi", result.get("error") or "GUIDED moda gecilemedi")
                add_log(f"Otomatik inis baslamadi: {result}")
                return

        add_log("Otomatik inis yardimi basladi")

        while not _stop_event.is_set():
            now = time.time()
            data = _snapshot()

            if not bool(data.get("cube_connected")):
                _set_idle("Cube baglantisi koptu", "Cube MAVLink baglantisi yok")
                add_log("Otomatik inis durdu: Cube baglantisi yok")
                break

            if config.AUTO_LANDING_REQUIRE_ARMED and not bool(data.get("cube_armed")):
                _set_idle("DISARM", "Arac DISARM oldu")
                add_log("Otomatik inis durdu: arac DISARM oldu")
                break

            distance = _distance_cm(data)
            sensor_ok = _sensor_is_fresh(data, now)

            if config.AUTO_LANDING_REQUIRE_SENSOR and not sensor_ok:
                mavlink_service.stop_guided_velocity()
                _state_update(
                    auto_landing_phase="sensor_wait",
                    auto_landing_status="Sensor bekleniyor",
                    auto_landing_target_speed_mps=0.0,
                    auto_landing_last_command_time=now,
                    auto_landing_error=None,
                )
                time.sleep(float(config.AUTO_LANDING_COMMAND_INTERVAL_SEC))
                continue

            speed, phase = _speed_for_distance(distance)
            status = _phase_text(phase, distance)

            if phase == "hold":
                mavlink_service.stop_guided_velocity()
                hold_result = mavlink_service.set_mode(config.AUTO_LANDING_HOLD_MODE)
                if not hold_result.get("ok"):
                    add_log(f"Otomatik inis tutma modu hatasi: {hold_result}")

                if (
                    config.AUTO_LANDING_DISARM_ON_TOUCHDOWN
                    and distance is not None
                    and distance <= float(config.AUTO_LANDING_TOUCHDOWN_BELOW_CM)
                ):
                    mavlink_service.send_disarm_command()
                    status = "Dokunma mesafesi, DISARM gonderildi"

                _state_update(
                    auto_landing_phase=phase,
                    auto_landing_status=status,
                    auto_landing_target_speed_mps=0.0,
                    auto_landing_last_command_time=now,
                )
                add_log(f"Otomatik inis tutma: {status}")
                break

            command = mavlink_service.send_guided_descent_velocity(speed)
            _state_update(
                auto_landing_phase=phase,
                auto_landing_status=status,
                auto_landing_target_speed_mps=speed,
                auto_landing_last_command_time=now,
                auto_landing_error=None if command.get("ok") else command.get("error"),
            )

            time.sleep(float(config.AUTO_LANDING_COMMAND_INTERVAL_SEC))

    except Exception as exc:
        _set_idle("Hata", str(exc))
        add_log(f"Otomatik inis hatasi: {exc}")
    finally:
        try:
            mavlink_service.stop_guided_velocity()
        except Exception:
            pass

        if _stop_event.is_set():
            try:
                if started_mode:
                    mavlink_service.set_mode(config.AUTO_LANDING_HOLD_MODE)
            except Exception:
                pass
            _set_idle("Durduruldu")
            add_log("Otomatik inis yardimi durduruldu")
        else:
            _state_update(auto_landing_active=False, auto_landing_enabled=False)


def start_auto_landing():
    global _worker_thread

    with _thread_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return {"ok": True, "message": "Otomatik inis zaten aktif"}

        _stop_event.clear()
        _worker_thread = threading.Thread(
            target=_worker,
            name="adti-auto-landing",
            daemon=True,
        )
        _worker_thread.start()
        return {"ok": True, "message": "Otomatik inis baslatildi"}


def stop_auto_landing():
    _stop_event.set()
    try:
        mavlink_service.stop_guided_velocity()
    except Exception:
        pass
    _state_update(
        auto_landing_enabled=False,
        auto_landing_active=False,
        auto_landing_phase="stopping",
        auto_landing_status="Durduruluyor",
        auto_landing_target_speed_mps=0.0,
    )
    return {"ok": True, "message": "Otomatik inis durduruluyor"}
=======
>>>>>>> b896abad72cec15526c5edf83a4468593bc2771f
>>>>>>> f0d59af20d4cf5734ccecd4ca8398321ce4993b1
        auto_landing_status="Kapali",
        auto_landing_target_speed_mps=0.0,
        auto_landing_error=None,
    )
    add_log("MZ80 uyari modu kapatildi; ucus komutu gonderilmedi")
    return {"ok": True, "message": "MZ80 uyari modu kapatildi"}
<<<<<<< HEAD
=======
<<<<<<< HEAD
=======
>>>>>>> 82cd033 (orange cube entegrasyonu otopilot)
>>>>>>> b896abad72cec15526c5edf83a4468593bc2771f
>>>>>>> f0d59af20d4cf5734ccecd4ca8398321ce4993b1


def get_auto_landing_status():
    data = _snapshot()
    return {
        "ok": True,
        "auto_landing_enabled": data.get("auto_landing_enabled"),
        "auto_landing_active": data.get("auto_landing_active"),
        "auto_landing_phase": data.get("auto_landing_phase"),
        "auto_landing_status": data.get("auto_landing_status"),
        "auto_landing_target_speed_mps": data.get("auto_landing_target_speed_mps"),
        "auto_landing_error": data.get("auto_landing_error"),
<<<<<<< HEAD
        "landing_mz80_connected": data.get("landing_mz80_connected"),
        "landing_mz80_detected": data.get("landing_mz80_detected"),
        "landing_mz80_distance_cm": data.get("landing_mz80_distance_cm"),
=======
<<<<<<< HEAD
        "landing_mz80_connected": data.get("landing_mz80_connected"),
        "landing_mz80_detected": data.get("landing_mz80_detected"),
        "landing_mz80_distance_cm": data.get("landing_mz80_distance_cm"),
=======
<<<<<<< HEAD
=======
        "landing_mz80_connected": data.get("landing_mz80_connected"),
        "landing_mz80_detected": data.get("landing_mz80_detected"),
        "landing_mz80_distance_cm": data.get("landing_mz80_distance_cm"),
>>>>>>> 82cd033 (orange cube entegrasyonu otopilot)
>>>>>>> b896abad72cec15526c5edf83a4468593bc2771f
>>>>>>> f0d59af20d4cf5734ccecd4ca8398321ce4993b1
    }
