"""DETAS veri, servo ve gorev API route'lari."""

from flask import Blueprint, jsonify

from routes import get_route_service
from services.logger_service import get_logs
from services.state import state


api_blueprint = Blueprint("api", __name__)


def _service_unavailable(name):
    return jsonify({
        "ok": False,
        "error": f"{name} servisi henuz baglanmadi",
    }), 503


def _call_json_service(name, *args):
    """Enjekte edilen servis fonksiyonunu guvenli sekilde cagirir."""
    service = get_route_service(name)

    if service is None:
        return _service_unavailable(name)

    try:
        result = service(*args)

        if isinstance(result, tuple):
            payload, status_code = result
            return jsonify(payload), status_code

        return jsonify(result)
    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500


@api_blueprint.route("/data", endpoint="data")
def data():
    payload = state.snapshot()
    payload["logs"] = get_logs()
    return jsonify(payload)


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

from services import mavlink_service as detas_mavlink_service_fix




# ===== DETAS CLEAN SERVO ROUTES START =====

@api_blueprint.route("/servo/pan/<int:pwm>", methods=["GET", "POST"])
def detas_clean_servo_pan(pwm):
    try:
        result = detas_mavlink_service_fix.detas_set_pan(pwm)
        result["servo"] = "pan"
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "servo": "pan"}), 500


@api_blueprint.route("/servo/tilt/<int:pwm>", methods=["GET", "POST"])
def detas_clean_servo_tilt(pwm):
    try:
        result = detas_mavlink_service_fix.detas_set_tilt(pwm)
        result["servo"] = "tilt"
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "servo": "tilt"}), 500


@api_blueprint.route("/servo/center", methods=["GET", "POST"])
def detas_clean_servo_center():
    try:
        return jsonify(detas_mavlink_service_fix.detas_servo_center())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@api_blueprint.route("/servo/stop", methods=["GET", "POST"])
def detas_clean_servo_stop():
    try:
        return jsonify(detas_mavlink_service_fix.detas_servo_stop())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@api_blueprint.route("/servo/scan_pan_slow", methods=["GET", "POST"])
def detas_clean_scan_pan_slow():
    try:
        return jsonify(detas_mavlink_service_fix.detas_scan_pan_slow())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@api_blueprint.route("/servo/scan_tilt_slow", methods=["GET", "POST"])
def detas_clean_scan_tilt_slow():
    try:
        return jsonify(detas_mavlink_service_fix.detas_scan_tilt_slow())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@api_blueprint.route("/servo/scan_full_slow", methods=["GET", "POST"])
def detas_clean_scan_full_slow():
    try:
        return jsonify(detas_mavlink_service_fix.detas_scan_full_slow())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ===== DETAS CLEAN SERVO ROUTES END =====


# ============================================================
# DETAS TEK SERVO TARAMA ROUTE DÜZELTMESİ
# ============================================================
# Bu route'lar direkt services/servo_service.py içindeki tek servo kodunu çağırır.
# AUX1 = SERVO9, tarama 1400 ↔ 2400 arasında yapılır.

try:
    from services import servo_service
except Exception:
    servo_service = None


@api_blueprint.route("/servo/scan_single", methods=["GET", "POST"])
def servo_scan_single_route():
    if servo_service is None:
        return jsonify({"ok": False, "error": "servo_service yüklenemedi"}), 500

    result = servo_service.servo_scan()
    return jsonify(result)


@api_blueprint.route("/servo/stop_single", methods=["GET", "POST"])
def servo_stop_single_route():
    if servo_service is None:
        return jsonify({"ok": False, "error": "servo_service yüklenemedi"}), 500

    result = servo_service.servo_stop()
    return jsonify(result)


@api_blueprint.route("/servo/single/<int:pwm>", methods=["GET", "POST"])
def servo_single_pwm_route(pwm):
    if servo_service is None:
        return jsonify({"ok": False, "error": "servo_service yüklenemedi"}), 500

    result = servo_service.set_position(pwm)
    return jsonify(result)

