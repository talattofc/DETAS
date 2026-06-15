"""DETAS kamera secimi ve video stream route'lari."""

from flask import Blueprint, Response, jsonify

from routes import get_route_service
from services.state import state


video_blueprint = Blueprint("video", __name__)


@video_blueprint.route("/video", endpoint="video")
def video():
    stream_service = get_route_service("camera_stream")

    if stream_service is None:
        return jsonify({
            "ok": False,
            "error": "camera_stream servisi henuz baglanmadi",
        }), 503

    try:
        camera_id = state.snapshot()["camera"]
        return Response(
            stream_service(camera_id),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )
    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500


@video_blueprint.route(
    "/set_camera/<int:camera_id>",
    methods=["POST"],
    endpoint="set_camera",
)
def set_camera(camera_id):
    camera_service = get_route_service("set_camera")

    if camera_service is None:
        return jsonify({
            "ok": False,
            "error": "set_camera servisi henuz baglanmadi",
        }), 503

    try:
        result = camera_service(camera_id)

        if isinstance(result, tuple):
            payload, status_code = result
            return jsonify(payload), status_code

        return jsonify(result)
    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500
