"""DETAS 915 MHz istasyon telemetri servisi."""

import re
import threading
import time

from config import (
    TELEMETRY_BAUD,
    TELEMETRY_DISCONNECT_TIMEOUT,
    TELEMETRY_PORT,
    TELEMETRY_RECONNECT_DELAY,
    TELEMETRY_TIMEOUT,
)
from services.logger_service import add_log
from services.state import state

try:
    import serial

    SERIAL_AVAILABLE = True
except Exception as exc:
    serial = None
    SERIAL_AVAILABLE = False
    _SERIAL_IMPORT_ERROR = exc


_thread_lock = threading.Lock()
_telemetry_thread = None

_MOVEMENT_PATTERNS = (
    r"movement\s*[:=]\s*(-?\d+(?:\.\d+)?)",
    r"hareket\s*[:=]\s*(-?\d+(?:\.\d+)?)",
    r"sarsinti\s*[:=]\s*(-?\d+(?:\.\d+)?)",
    r"sarsıntı\s*[:=]\s*(-?\d+(?:\.\d+)?)",
    r"shake\s*[:=]\s*(-?\d+(?:\.\d+)?)",
    r"ivme\s*[:=]\s*(-?\d+(?:\.\d+)?)",
    r"acc\s*[:=]\s*(-?\d+(?:\.\d+)?)",
    r"mag\s*[:=]\s*(-?\d+(?:\.\d+)?)",
)


def _find_number(text, patterns):
    for pattern in patterns:
        match = re.search(pattern, text)

        if match:
            try:
                return float(match.group(1))
            except Exception:
                pass

    return None


def parse_telemetry_text(text):
    """Gelen telemetri metnini parse ederek merkezi state'i gunceller."""
    try:
        lower = str(text).lower().strip()
        snapshot = state.snapshot()

        movement = _find_number(lower, _MOVEMENT_PATTERNS)
        threshold = _find_number(lower, (
            r"threshold\s*[:=]\s*(-?\d+(?:\.\d+)?)",
            r"esik\s*[:=]\s*(-?\d+(?:\.\d+)?)",
            r"eşik\s*[:=]\s*(-?\d+(?:\.\d+)?)",
        ))
        mute = _find_number(lower, (
            r"mute\s*[:=]\s*(-?\d+(?:\.\d+)?)",
            r"sessiz\s*[:=]\s*(-?\d+(?:\.\d+)?)",
        ))

        if movement is None:
            numbers = re.findall(r"-?\d+(?:\.\d+)?", lower)

            if numbers:
                try:
                    movement = float(numbers[0])
                except Exception:
                    movement = None

        current_threshold = snapshot["threshold"]
        if threshold is not None:
            current_threshold = threshold

        deprem = snapshot["deprem"]
        alarm_text = (
            "deprem" in lower
            or "alarm" in lower
            or "quake" in lower
        )

        if alarm_text and (
            "1" in lower
            or "true" in lower
            or "var" in lower
        ):
            deprem = 1

        updates = {
            "threshold": current_threshold,
        }

        if mute is not None:
            updates["mute"] = int(mute)

        if movement is not None:
            movement = round(abs(movement), 2)
            updates["movement"] = movement
            updates["max_movement"] = max(snapshot["max_movement"], movement)

            if movement >= current_threshold:
                deprem = 1
            elif not alarm_text:
                deprem = 0

        updates["deprem"] = deprem
        state.update(**updates)

        return updates
    except Exception as exc:
        add_log(f"Telemetri parse hatasi: {exc}")
        return {}


def telemetry_worker():
    """Seri portu okuyup hata durumunda yeniden baglanmayi dener."""
    if not SERIAL_AVAILABLE:
        add_log(f"Telemetri icin pyserial yok: {_SERIAL_IMPORT_ERROR}")
        state.update(telemetry_connected=False)
        return

    while True:
        ser = None

        try:
            add_log(f"Istasyon telemetri aciliyor: {TELEMETRY_PORT}")

            ser = serial.Serial(
                port=TELEMETRY_PORT,
                baudrate=TELEMETRY_BAUD,
                timeout=TELEMETRY_TIMEOUT,
            )

            state.update(telemetry_connected=True)
            add_log("Istasyon telemetri baglandi")

            while True:
                try:
                    raw = ser.readline()

                    if not raw:
                        raw = ser.read(64)

                    if raw:
                        now = time.time()
                        text = raw.decode("utf-8", errors="replace").strip()
                        snapshot = state.snapshot()

                        state.update(
                            telemetry_connected=True,
                            telemetry_packet_count=snapshot["telemetry_packet_count"] + 1,
                            telemetry_raw=text,
                            telemetry_last_time=now,
                        )

                        parse_telemetry_text(text)
                    else:
                        snapshot = state.snapshot()
                        last_time = state.telemetry_last_time

                        if (
                            last_time > 0
                            and time.time() - last_time > TELEMETRY_DISCONNECT_TIMEOUT
                            and snapshot["telemetry_connected"]
                        ):
                            state.update(telemetry_connected=False)

                        time.sleep(0.05)

                except Exception as exc:
                    state.update(telemetry_connected=False)
                    add_log(f"Istasyon telemetri okuma hatasi: {exc}")
                    break

        except Exception as exc:
            state.update(telemetry_connected=False)
            add_log(f"Istasyon telemetri port hatasi: {exc}")
        finally:
            if ser is not None:
                try:
                    ser.close()
                except Exception:
                    pass

        time.sleep(TELEMETRY_RECONNECT_DELAY)


def start_telemetry_thread():
    """Telemetri worker'ini daemon thread olarak bir kez baslatir."""
    global _telemetry_thread

    with _thread_lock:
        if _telemetry_thread is not None and _telemetry_thread.is_alive():
            return _telemetry_thread

        _telemetry_thread = threading.Thread(
            target=telemetry_worker,
            name="detas-telemetry",
            daemon=True,
        )
        _telemetry_thread.start()
        return _telemetry_thread


# Eski app.py isimlendirmesiyle uyumluluk.
telemetry_thread = telemetry_worker
