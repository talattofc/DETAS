"""ADTİ Flask uygulama baslangic noktasi."""

import atexit

from flask import Flask

import config
from routes import register_routes
from services import camera_service, mavlink_service, servo_service
from services.detection_service import process_stream_jpeg
from services.earthquake_rearm_service import start_earthquake_rearm_watcher
from services.logger_service import add_log
from services.mission_status_service import start_mission_status_service
from services.telemetry_service import start_telemetry_thread
from services.thermal_service import start_thermal_thread


def register_route_services(app):
    """Blueprint route'larinin kullanacagi servis fonksiyonlarini kaydeder."""
    app.extensions["detas_services"] = {
        "camera_stream": camera_service.generate_frames,
        "set_camera": camera_service.set_camera,

        "servo_position": servo_service.set_position,
        "servo_center": servo_service.servo_center,
        "servo_scan": servo_service.servo_scan,
        "servo_stop": servo_service.servo_stop,

        "mission_arm": mavlink_service.mission_arm,
        "mission_stop": mavlink_service.mission_stop,
        "mission_reset": mavlink_service.mission_reset,
        "mission_motor_test": mavlink_service.mission_motor_test,
    }


def create_app():
    """Flask uygulamasini, route'lari ve servis baglantilarini olusturur."""
    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = config.JSON_AS_ASCII

    try:
        app.json.ensure_ascii = config.JSON_AS_ASCII
    except Exception:
        pass

    register_route_services(app)
    register_routes(app)
    return app


def start_background_services():
    """ADTİ donanim ve otomatik gorev servislerini baslatir."""
    camera_service.set_detection_callback(process_stream_jpeg)

    try:
        start_mission_status_service()
    except Exception as e:
        print("Görev durumu takip sistemi başlatılamadı:", e)

    try:
        start_earthquake_rearm_watcher()
    except Exception as e:
        print("Deprem tekrar ARM takipçisi başlatılamadı:", e)

    start_telemetry_thread()
    mavlink_service.start_mavlink_thread()
    mavlink_service.start_auto_mission_thread()
    start_thermal_thread()

    add_log("ADTİ panel basladi")
    add_log("AI modu aktif")
    add_log("YOLO kutu sayimi aktif")
    add_log("Cube MAVLink modu aktif")


app = create_app()
atexit.register(camera_service.stop_active_process)


if __name__ == "__main__":
    start_background_services()

    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
        threaded=config.FLASK_THREADED,
    )
