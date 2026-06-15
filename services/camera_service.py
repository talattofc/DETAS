"""DETAS rpicam kamera ve MJPEG stream servisi."""

import os
import subprocess
import threading
import time

from config import (
    CAMERA_CONFIGS,
    DEFAULT_CAMERA,
    DETECTION_FRAME_INTERVAL,
    HAILO_JSON,
    RPICAM_COMMAND,
    RPICAM_STREAM_READ_SIZE,
    VALID_CAMERA_IDS,
)
from services.logger_service import add_log
from services.state import state


_process_lock = threading.Lock()
_active_process = None
_detection_callback = None


def set_detection_callback(callback):
    """JPEG karelerini isleyecek detection service callback'ini ayarlar."""
    global _detection_callback
    _detection_callback = callback


def get_active_camera():
    """Merkezi state icindeki aktif kamera numarasini dondurur."""
    try:
        return state.snapshot()["camera"]
    except Exception:
        return DEFAULT_CAMERA


def set_camera(camera_id):
    """Aktif kamerayi degistirir ve eski rpicam process'ini kapatir."""
    if camera_id not in VALID_CAMERA_IDS:
        return {
            "ok": False,
            "error": "Gecersiz kamera",
        }, 400

    try:
        state.update(camera=camera_id)

        camera_name = CAMERA_CONFIGS[camera_id]["name"]
        add_log(f"CAM{camera_id} {camera_name} secildi")

        stop_active_process()

        return {
            "ok": True,
            "camera": camera_id,
        }
    except Exception as exc:
        add_log(f"Kamera degistirme hatasi: {exc}")
        return {
            "ok": False,
            "error": str(exc),
        }, 500


def build_rpicam_command(camera_id):
    """Secilen kamera icin mevcut sistemle uyumlu rpicam komutu olusturur."""
    if camera_id not in VALID_CAMERA_IDS:
        raise ValueError("Gecersiz kamera")

    camera_config = CAMERA_CONFIGS[camera_id]

    command = [
        RPICAM_COMMAND,
        "--camera", str(camera_id),
        "-t", "0",
        "--codec", "mjpeg",
        "--width", str(camera_config["width"]),
        "--height", str(camera_config["height"]),
        "--framerate", str(camera_config["framerate"]),
        "--nopreview",
        "-o", "-",
    ]

    command.extend(camera_config.get("extra_controls", []))

    hailo_active = os.path.exists(HAILO_JSON)
    state.update(hailo=hailo_active)

    if hailo_active:
        command.extend([
            "--post-process-file",
            HAILO_JSON,
        ])
    else:
        add_log("Hailo JSON bulunamadi, AI postprocess kapali")

    return command


def stop_active_process():
    """Calisan rpicam process'ini guvenli sekilde kapatir."""
    global _active_process

    with _process_lock:
        process = _active_process
        _active_process = None

    if process is None:
        return

    try:
        process.terminate()
        time.sleep(0.3)

        if process.poll() is None:
            process.kill()
    except Exception as exc:
        add_log(f"rpicam process kapatma hatasi: {exc}")


def _update_detection(jpg_bytes):
    """Varsa detection service callback'ini cagirir."""
    callback = _detection_callback

    if callback is None:
        return

    try:
        callback(jpg_bytes)
    except Exception as exc:
        add_log(f"YOLO detection guncelleme hatasi: {exc}")


def generate_frames(camera_id=None):
    """Flask /video route'u icin multipart MJPEG frame generator'u."""
    global _active_process

    if camera_id is None:
        camera_id = get_active_camera()

    process = None

    try:
        stop_active_process()
        command = build_rpicam_command(camera_id)

        add_log(f"AI HAT YOLO stream basladi: CAM{camera_id}")

        try:
            print("Calisan komut:")
            print(" ".join(command))
        except Exception:
            pass

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )

        with _process_lock:
            _active_process = process

        buffer = b""
        frame_counter = 0

        while True:
            chunk = process.stdout.read(RPICAM_STREAM_READ_SIZE)

            if not chunk:
                break

            buffer += chunk

            while True:
                start = buffer.find(b"\xff\xd8")
                end = buffer.find(b"\xff\xd9", start + 2)

                if start == -1:
                    if len(buffer) > 1024 * 1024:
                        buffer = buffer[-1024:]
                    break

                if end == -1:
                    if start > 0:
                        buffer = buffer[start:]
                    break

                jpg = buffer[start:end + 2]
                buffer = buffer[end + 2:]
                frame_counter += 1

                if frame_counter % DETECTION_FRAME_INTERVAL == 0:
                    _update_detection(jpg)

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + jpg
                    + b"\r\n"
                )

    except GeneratorExit:
        pass
    except Exception as exc:
        add_log(f"Stream hatasi: {exc}")
    finally:
        if process is not None:
            try:
                process.terminate()
                time.sleep(0.2)

                if process.poll() is None:
                    process.kill()
            except Exception:
                pass

        with _process_lock:
            if _active_process is process:
                _active_process = None


# Eski app.py ve route iskeletiyle uyumlu isimler.
jpeg_stream_from_rpicam = generate_frames
camera_stream = generate_frames
