"""MZ80 yaklasma uyarisi servisi.

Bu servis MZ80 bilgisini yalnizca uyari/status olarak kullanir. Motor, throttle,
DISARM veya dogrudan inis kontrolu yapmaz.
"""

from services.logger_service import add_log
from services.state import state


def _snapshot():
    try:
        return state.snapshot()
    except Exception:
        return {}


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
    _state_update(
        auto_landing_enabled=False,
        auto_landing_active=False,
        auto_landing_phase="idle",
        auto_landing_status="Kapali",
        auto_landing_target_speed_mps=0.0,
        auto_landing_error=None,
    )
    add_log("MZ80 uyari modu kapatildi; ucus komutu gonderilmedi")
    return {"ok": True, "message": "MZ80 uyari modu kapatildi"}


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
        "landing_mz80_connected": data.get("landing_mz80_connected"),
        "landing_mz80_detected": data.get("landing_mz80_detected"),
        "landing_mz80_distance_cm": data.get("landing_mz80_distance_cm"),
    }
