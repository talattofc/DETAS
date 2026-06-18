"""DETAS veri, tek servo ve gorev API route'lari."""

from flask import Blueprint, Response, jsonify, request

from routes import get_route_service
from services.detection_service import get_detections
from services.feedback_dataset_service import (
    capture_feedback,
    get_classes,
    get_export_info,
    get_latest_frame_jpeg,
    get_stats,
)
from services.logger_service import get_logs
from services.state import state


api_blueprint = Blueprint("api", __name__)


def _json_error(message, status_code=500):
    return jsonify({"ok": False, "error": message}), status_code


def _call_json_service(name, *args):
    service = get_route_service(name)

    if service is None:
        return _json_error(f"{name} servisi henuz baglanmadi", 503)

    try:
        result = service(*args)

        if isinstance(result, tuple):
            payload, status_code = result
            return jsonify(payload), status_code

        return jsonify(result)
    except Exception as exc:
        return _json_error(str(exc), 500)


@api_blueprint.route("/data", endpoint="data")
def data():
    payload = state.snapshot()
    payload["logs"] = get_logs()
    return jsonify(payload)


@api_blueprint.route("/api/detections", methods=["GET"], endpoint="api_detections")
def api_detections():
    return jsonify({
        "ok": True,
        **get_detections(),
    })


@api_blueprint.route("/api/feedback/classes", methods=["GET"], endpoint="feedback_classes")
def feedback_classes():
    return jsonify(get_classes())


@api_blueprint.route("/api/feedback/capture", methods=["POST"], endpoint="feedback_capture")
def feedback_capture():
    result = capture_feedback(request.get_json(silent=True) or {})
    if isinstance(result, tuple):
        payload, status_code = result
        return jsonify(payload), status_code
    return jsonify(result)


@api_blueprint.route("/api/feedback/stats", methods=["GET"], endpoint="feedback_stats")
def feedback_stats():
    return jsonify(get_stats())


@api_blueprint.route("/api/feedback/export-info", methods=["GET"], endpoint="feedback_export_info")
def feedback_export_info():
    return jsonify(get_export_info())


@api_blueprint.route("/api/feedback/latest-frame", methods=["GET"], endpoint="feedback_latest_frame")
def feedback_latest_frame():
    jpg = get_latest_frame_jpeg()
    if not jpg:
        return jsonify({
            "ok": False,
            "error": "Son kamera karesi yok",
        }), 404

    return Response(jpg, mimetype="image/jpeg")


@api_blueprint.route("/mission/arm", methods=["POST"], endpoint="mission_arm_route")
def mission_arm_route():
    return _call_json_service("mission_arm")


@api_blueprint.route("/mission/stop", methods=["POST"], endpoint="mission_stop_route")
def mission_stop_route():
    return _call_json_service("mission_stop")


@api_blueprint.route("/mission/reset", methods=["POST"], endpoint="mission_reset_route")
def mission_reset_route():
    return _call_json_service("mission_reset")


@api_blueprint.route("/mission/motor_test", methods=["POST"], endpoint="mission_motor_test_route")
def mission_motor_test_route():
    return _call_json_service("mission_motor_test")


@api_blueprint.route("/servo/position/<int:pwm>", methods=["GET", "POST"], endpoint="servo_position_route")
def servo_position_route(pwm):
    return _call_json_service("servo_position", pwm)


@api_blueprint.route("/servo/center", methods=["GET", "POST"], endpoint="servo_center_route")
def servo_center_route():
    return _call_json_service("servo_center")


@api_blueprint.route("/servo/scan", methods=["GET", "POST"], endpoint="servo_scan_route")
def servo_scan_route():
    return _call_json_service("servo_scan")


@api_blueprint.route("/servo/stop", methods=["GET", "POST"], endpoint="servo_stop_route")
def servo_stop_route():
    return _call_json_service("servo_stop")
