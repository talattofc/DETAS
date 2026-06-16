"""DETAS uygulamasinin merkezi ve thread-safe durum yonetimi."""

import threading
import time
from copy import deepcopy

try:
    from config import (
        AUTO_ARM_ON_EARTHQUAKE,
        AUTO_MISSION_ENABLED_DEFAULT,
        DEFAULT_CAMERA,
        PAN_CENTER,
        PAN_MAX,
        PAN_MIN,
        THRESHOLD_VALUE_DEFAULT,
    )
except ImportError:
    DEFAULT_CAMERA = 0
    THRESHOLD_VALUE_DEFAULT = 1.5
    AUTO_MISSION_ENABLED_DEFAULT = True
    AUTO_ARM_ON_EARTHQUAKE = True

    PAN_MIN = 450
    PAN_CENTER = 1300
    PAN_MAX = 2500


class AppState:
    """Uygulama servisleri arasinda paylasilan merkezi veri deposu."""

    def __init__(self):
        self._lock = threading.RLock()

        # Deprem, istasyon telemetrisi ve gorev durumu
        self.deprem = 0
        self.movement = 0.0
        self.max_movement = 0.0
        self.threshold = THRESHOLD_VALUE_DEFAULT
        self.mute = 0
        self.mission_status = "BEKLEMEDE"

        self.telemetry_connected = False
        self.telemetry_packet_count = 0
        self.telemetry_raw = ""
        self.telemetry_last_time = 0.0

        # Termal sensor
        self.thermal_connected = False
        self.thermal_address = None
        self.thermal = [[0.0 for _ in range(8)] for _ in range(8)]
        self.thermal_min = 0.0
        self.thermal_max = 0.0
        self.thermal_sensor_temp = 0.0
        self.hotspot = 0

        # Kamera ve nesne algilama
        self.camera = DEFAULT_CAMERA
        self.detection_count = 0
        self.detections = []
        self.hailo = False

        # Orange Cube / MAVLink
        self.cube_connected = False
        self.cube_mode = "BILINMIYOR"
        self.cube_armed = False
        self.cube_battery_voltage = 0.0
        self.cube_battery_current = 0.0
        self.cube_gps_fix = 0
        self.cube_satellites = 0
        self.cube_eph = 0
        self.cube_altitude = 0.0
        self.cube_groundspeed = 0.0
        self.cube_heading = 0
        self.cube_throttle = 0
        self.cube_roll = 0.0
        self.cube_pitch = 0.0
        self.cube_yaw = 0.0
        self.cube_last_heartbeat = 0.0

        # SERVO9 / AUX1 tek eksenli kamera servosu
        self.servo_pwm = PAN_CENTER
        self.single_servo_pwm = PAN_CENTER
        self.servo_number = 9
        self.servo_mode = "single_aux1_vertical"
        self.servo_scan_active = False
        self.servo_scan_mode = "stop"

        # Eski panel alanlari icin aynalar
        self.servo_pan = PAN_CENTER
        self.servo_tilt = PAN_CENTER

        # Otomatik gorev
        self.auto_mission_enabled = AUTO_MISSION_ENABLED_DEFAULT
        self.auto_mission_stopped = False
        self.auto_arm_on_earthquake = AUTO_ARM_ON_EARTHQUAKE
        self.auto_arm_sent = False
        self.last_auto_arm_time = 0.0

    def update(self, **kwargs):
        """Verilen state alanlarini tek kilit altinda gunceller."""
        with self._lock:
            for key in kwargs:
                if key.startswith("_") or not hasattr(self, key):
                    raise AttributeError(f"Bilinmeyen state alani: {key}")

            for key, value in kwargs.items():
                setattr(self, key, deepcopy(value))

    def snapshot(self):
        """Mevcut durumu /data endpointi icin JSON uyumlu dict olarak dondurur."""
        with self._lock:
            heartbeat_age = None

            if self.cube_last_heartbeat:
                heartbeat_age = round(time.time() - self.cube_last_heartbeat, 1)

            thermal_address = self.thermal_address
            if isinstance(thermal_address, int):
                thermal_address = f"0x{thermal_address:02X}"

            return {
                "camera": self.camera,
                "hailo": self.hailo,

                "deprem": self.deprem,
                "movement": self.movement,
                "threshold": self.threshold,
                "max_movement": round(self.max_movement, 2),
                "mute": self.mute,
                "mission_status": self.mission_status,

                "detection_count": self.detection_count,
                "detections": deepcopy(self.detections),

                "thermal": deepcopy(self.thermal),
                "thermal_min": self.thermal_min,
                "thermal_max": self.thermal_max,
                "thermal_sensor_temp": self.thermal_sensor_temp,
                "hotspot": self.hotspot,
                "thermal_connected": self.thermal_connected,
                "thermal_address": thermal_address,

                "telemetry_connected": self.telemetry_connected,
                "telemetry_raw": self.telemetry_raw,
                "telemetry_packet_count": self.telemetry_packet_count,

                "cube_connected": self.cube_connected,
                "cube_mode": self.cube_mode,
                "cube_armed": self.cube_armed,
                "cube_arm_status": "ARMED" if self.cube_armed else "DISARMED",

                "cube_roll": self.cube_roll,
                "cube_pitch": self.cube_pitch,
                "cube_yaw": self.cube_yaw,

                "cube_altitude": self.cube_altitude,
                "cube_groundspeed": self.cube_groundspeed,
                "cube_heading": self.cube_heading,
                "cube_throttle": self.cube_throttle,

                "cube_battery_voltage": self.cube_battery_voltage,
                "cube_battery_current": self.cube_battery_current,

                "cube_gps_fix": self.cube_gps_fix,
                "cube_satellites": self.cube_satellites,
                "cube_eph": self.cube_eph,
                "cube_last_heartbeat_age": heartbeat_age,

                "servo_pwm": self.servo_pwm,
                "single_servo_pwm": self.single_servo_pwm,
                "servo_number": self.servo_number,
                "servo_mode": self.servo_mode,
                "servo_scan_active": self.servo_scan_active,
                "servo_scan_mode": self.servo_scan_mode,
                "servo_min": PAN_MIN,
                "servo_center": PAN_CENTER,
                "servo_max": PAN_MAX,
                "servo_down": 1400,

                "servo_pan": self.servo_pan,
                "servo_tilt": self.servo_tilt,
                "servo_pan_min": PAN_MIN,
                "servo_pan_center": PAN_CENTER,
                "servo_pan_max": PAN_MAX,
                "servo_tilt_min": PAN_MIN,
                "servo_tilt_center": PAN_CENTER,
                "servo_tilt_max": PAN_MAX,

                "auto_mission_enabled": self.auto_mission_enabled,
                "auto_mission_stopped": self.auto_mission_stopped,
                "auto_arm_on_earthquake": self.auto_arm_on_earthquake,
                "auto_arm_sent": self.auto_arm_sent,
                "last_auto_arm_time": self.last_auto_arm_time,
            }

    def to_dict(self):
        """snapshot() icin okunabilir takma ad."""
        return self.snapshot()


state = AppState()
