"""DETAS uygulama sabitleri ve donanim ayarlari."""

from pathlib import Path


# Proje ve Flask ayarlari
BASE_DIR = Path(__file__).resolve().parent

FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
FLASK_DEBUG = False
FLASK_THREADED = True
JSON_AS_ASCII = False


# Mevcut frontend ve backend endpointleri
ROUTE_DASHBOARD = "/"
ROUTE_DATA = "/data"
ROUTE_VIDEO = "/video"
ROUTE_SET_CAMERA = "/set_camera/<int:camera_id>"

ROUTE_MISSION_STOP = "/mission/stop"
ROUTE_MISSION_RESET = "/mission/reset"

ROUTE_SERVO_POSITION = "/servo/position/<int:pwm>"
ROUTE_SERVO_CENTER = "/servo/center"
ROUTE_SERVO_SCAN = "/servo/scan"
ROUTE_SERVO_STOP = "/servo/stop"


# AI HAT / YOLO postprocess ayarlari
HAILO_JSON = "/usr/share/rpi-camera-assets/hailo_yolov8_inference.json"
RPICAM_HAILO_POSTPROCESS_ENABLED = False
<<<<<<< HEAD
=======

MODELS_DIR = BASE_DIR / "models"
YOLO_PT_MODEL_PATH = MODELS_DIR / "best.pt"
YOLO_ONNX_MODEL_PATH = MODELS_DIR / "best.onnx"
HAILO_HEF_MODEL_PATH = MODELS_DIR / "detas_v3_7class_yolov8n_json_nms_hailo8l.hef"
HAILO_MODEL_MANIFEST_PATH = MODELS_DIR / "detas_v3_hailo8l_manifest.json"
READY_HAILO_HEF_MODEL_PATH = Path("/usr/share/hailo-models/yolov8s_h8l.hef")
READY_HAILO_INPUT_SIZE = 640
READY_HAILO_INCLUDE_PERSON = False
PERSON_MODEL_PATH = MODELS_DIR / "yolov8n.pt"
PERSON_HAILO_HEF_MODEL_PATH = Path("/usr/share/hailo-models/yolov5s_personface_h8l.hef")
LABELS_PATH = MODELS_DIR / "labels.txt"
DETECTION_CONFIDENCE = 0.35
DETECTION_IMGSZ = 640
# DETAS HEF sorun cikarirsa gecici B-plan icin "ready_hailo" yapilabilir.
YOLO_MODEL_BACKEND = "hailo"
PERSON_MODEL_BACKEND = "hailo"
HAILO_INPUT_SIZE = 640
PERSON_HAILO_INPUT_SIZE = 640
HAILO_CONFIDENCE = 0.25
HAILO_NMS_IOU = 0.45
HAILO_MAX_CANDIDATES = 1200

READY_HAILO_CLASS_THRESHOLDS = {
    "person": 0.35,
    "car": 0.50,
    "truck": 0.50,
    "bus": 0.50,
    "motorcycle": 0.45,
    "bicycle": 0.45,
    "chair": 0.55,
    "backpack": 0.45,
    "handbag": 0.45,
}

READY_HAILO_ALLOWED_CLASSES = [
    "person",
    "car",
    "truck",
    "bus",
    "motorcycle",
    "bicycle",
    "chair",
    "backpack",
    "handbag",
]

DETAS_DISABLED_CLASSES = [
    "person",
    "rescue_worker",
]

DETAS_ALLOWED_CLASSES = [
    "rubble",
    "blocked_road",
    "collapsed_building",
    "damaged_vehicle",
    "fire_smoke",
    "open_road",
    "flood_area",
]

DETAS_CLASS_THRESHOLDS = {
    "rubble": 0.70,
    "blocked_road": 0.75,
    "collapsed_building": 0.75,
    "damaged_vehicle": 0.70,
    "fire_smoke": 0.70,
    "open_road": 0.80,
    "flood_area": 0.75,
    "person": 0.35,
}

HAILO_CLASS_THRESHOLDS = {
    "rubble": 0.45,
    "blocked_road": 0.50,
    "collapsed_building": 0.35,
    "damaged_vehicle": 0.45,
    "fire_smoke": 0.45,
    "open_road": 0.55,
    "flood_area": 0.45,
}
>>>>>>> 82cd033 (orange cube entegrasyonu otopilot)

MODELS_DIR = BASE_DIR / "models"
YOLO_PT_MODEL_PATH = MODELS_DIR / "best.pt"
YOLO_ONNX_MODEL_PATH = MODELS_DIR / "best.onnx"
HAILO_HEF_MODEL_PATH = MODELS_DIR / "detas_v3_7class_yolov8n_json_nms_hailo8l.hef"
HAILO_MODEL_MANIFEST_PATH = MODELS_DIR / "detas_v3_hailo8l_manifest.json"
READY_HAILO_HEF_MODEL_PATH = Path("/usr/share/hailo-models/yolov8s_h8l.hef")
READY_HAILO_INPUT_SIZE = 640
READY_HAILO_INCLUDE_PERSON = False
PERSON_MODEL_PATH = MODELS_DIR / "yolov8n.pt"
PERSON_HAILO_HEF_MODEL_PATH = Path("/usr/share/hailo-models/yolov5s_personface_h8l.hef")
LABELS_PATH = MODELS_DIR / "labels.txt"
DETECTION_CONFIDENCE = 0.35
DETECTION_IMGSZ = 640
# DETAS HEF sorun cikarirsa gecici B-plan icin "ready_hailo" yapilabilir.
YOLO_MODEL_BACKEND = "hailo"
PERSON_MODEL_BACKEND = "hailo"
HAILO_INPUT_SIZE = 640
PERSON_HAILO_INPUT_SIZE = 640
HAILO_CONFIDENCE = 0.25
HAILO_NMS_IOU = 0.45
HAILO_MAX_CANDIDATES = 1200

READY_HAILO_CLASS_THRESHOLDS = {
    "person": 0.35,
    "car": 0.50,
    "truck": 0.50,
    "bus": 0.50,
    "motorcycle": 0.45,
    "bicycle": 0.45,
    "chair": 0.55,
    "backpack": 0.45,
    "handbag": 0.45,
}

READY_HAILO_ALLOWED_CLASSES = [
    "person",
    "car",
    "truck",
    "bus",
    "motorcycle",
    "bicycle",
    "chair",
    "backpack",
    "handbag",
]

DETAS_DISABLED_CLASSES = [
    "person",
    "rescue_worker",
]

DETAS_ALLOWED_CLASSES = [
    "rubble",
    "blocked_road",
    "collapsed_building",
    "damaged_vehicle",
    "fire_smoke",
    "open_road",
    "flood_area",
]

DETAS_CLASS_THRESHOLDS = {
    "rubble": 0.70,
    "blocked_road": 0.75,
    "collapsed_building": 0.75,
    "damaged_vehicle": 0.70,
    "fire_smoke": 0.70,
    "open_road": 0.80,
    "flood_area": 0.75,
    "person": 0.35,
}

HAILO_CLASS_THRESHOLDS = {
    "rubble": 0.45,
    "blocked_road": 0.50,
    "collapsed_building": 0.35,
    "damaged_vehicle": 0.45,
    "fire_smoke": 0.45,
    "open_road": 0.55,
    "flood_area": 0.45,
}

MODELS_DIR = BASE_DIR / "models"
YOLO_PT_MODEL_PATH = MODELS_DIR / "best.pt"
YOLO_ONNX_MODEL_PATH = MODELS_DIR / "best.onnx"
HAILO_HEF_MODEL_PATH = MODELS_DIR / "detas_v3_7class_yolov8n_json_nms_hailo8l.hef"
HAILO_MODEL_MANIFEST_PATH = MODELS_DIR / "detas_v3_hailo8l_manifest.json"
READY_HAILO_HEF_MODEL_PATH = Path("/usr/share/hailo-models/yolov8s_h8l.hef")
READY_HAILO_INPUT_SIZE = 640
READY_HAILO_INCLUDE_PERSON = False
PERSON_MODEL_PATH = MODELS_DIR / "yolov8n.pt"
PERSON_HAILO_HEF_MODEL_PATH = Path("/usr/share/hailo-models/yolov5s_personface_h8l.hef")
LABELS_PATH = MODELS_DIR / "labels.txt"
DETECTION_CONFIDENCE = 0.35
DETECTION_IMGSZ = 640
# DETAS HEF sorun cikarirsa gecici B-plan icin "ready_hailo" yapilabilir.
YOLO_MODEL_BACKEND = "hailo"
PERSON_MODEL_BACKEND = "hailo"
HAILO_INPUT_SIZE = 640
PERSON_HAILO_INPUT_SIZE = 640
HAILO_CONFIDENCE = 0.25
HAILO_NMS_IOU = 0.45
HAILO_MAX_CANDIDATES = 1200

READY_HAILO_CLASS_THRESHOLDS = {
    "person": 0.35,
    "car": 0.50,
    "truck": 0.50,
    "bus": 0.50,
    "motorcycle": 0.45,
    "bicycle": 0.45,
    "chair": 0.55,
    "backpack": 0.45,
    "handbag": 0.45,
}

READY_HAILO_ALLOWED_CLASSES = [
    "person",
    "car",
    "truck",
    "bus",
    "motorcycle",
    "bicycle",
    "chair",
    "backpack",
    "handbag",
]

DETAS_DISABLED_CLASSES = [
    "person",
    "rescue_worker",
]

DETAS_ALLOWED_CLASSES = [
    "rubble",
    "blocked_road",
    "collapsed_building",
    "damaged_vehicle",
    "fire_smoke",
    "open_road",
    "flood_area",
]

DETAS_CLASS_THRESHOLDS = {
    "rubble": 0.70,
    "blocked_road": 0.75,
    "collapsed_building": 0.75,
    "damaged_vehicle": 0.70,
    "fire_smoke": 0.70,
    "open_road": 0.80,
    "flood_area": 0.75,
    "person": 0.35,
}

HAILO_CLASS_THRESHOLDS = {
    "rubble": 0.45,
    "blocked_road": 0.50,
    "collapsed_building": 0.35,
    "damaged_vehicle": 0.45,
    "fire_smoke": 0.45,
    "open_road": 0.55,
    "flood_area": 0.45,
}

MODELS_DIR = BASE_DIR / "models"
YOLO_PT_MODEL_PATH = MODELS_DIR / "best.pt"
YOLO_ONNX_MODEL_PATH = MODELS_DIR / "best.onnx"
PERSON_MODEL_PATH = MODELS_DIR / "yolov8n.pt"
LABELS_PATH = MODELS_DIR / "labels.txt"
DETECTION_CONFIDENCE = 0.35
DETECTION_IMGSZ = 640
YOLO_MODEL_BACKEND = "pt"

DETAS_DISABLED_CLASSES = [
    "person",
    "rescue_worker",
]

DETAS_ALLOWED_CLASSES = [
    "rubble",
    "blocked_road",
    "collapsed_building",
    "damaged_vehicle",
    "fire_smoke",
    "open_road",
    "flood_area",
]

DETAS_CLASS_THRESHOLDS = {
    "rubble": 0.70,
    "blocked_road": 0.75,
    "collapsed_building": 0.75,
    "damaged_vehicle": 0.70,
    "fire_smoke": 0.70,
    "open_road": 0.80,
    "flood_area": 0.75,
    "person": 0.35,
}

MODELS_DIR = BASE_DIR / "models"
YOLO_PT_MODEL_PATH = MODELS_DIR / "best.pt"
YOLO_ONNX_MODEL_PATH = MODELS_DIR / "best.onnx"
PERSON_MODEL_PATH = MODELS_DIR / "yolov8n.pt"
LABELS_PATH = MODELS_DIR / "labels.txt"
DETECTION_CONFIDENCE = 0.25
DETECTION_IMGSZ = 640
YOLO_MODEL_BACKEND = "pt"

DETAS_DISABLED_CLASSES = [
    "person",
    "rescue_worker",
]

DETAS_ALLOWED_CLASSES = [
    "rubble",
    "blocked_road",
    "collapsed_building",
    "damaged_vehicle",
    "fire_smoke",
    "safe_passage",
    "flood_area",
]

DETAS_CLASS_THRESHOLDS = {
    "rubble": 0.70,
    "blocked_road": 0.75,
    "collapsed_building": 0.75,
    "damaged_vehicle": 0.70,
    "fire_smoke": 0.70,
    "safe_passage": 0.80,
    "flood_area": 0.75,
    "person": 0.35,
}

DETECTION_FRAME_INTERVAL = 12
DETECTION_MAX_COUNT = 20
DETECTION_RESIZE_MAX_WIDTH = 960
DETECTION_MIN_BOX_WIDTH = 70
DETECTION_MIN_BOX_HEIGHT = 70
DETECTION_MIN_BOX_AREA = 6000
DETECTION_MAX_FRAME_AREA_RATIO = 0.85
DETECTION_MERGE_IOU_THRESHOLD = 0.25
DETECTION_DEFAULT_CLASS = "afet_tespiti"
DETECTION_EVENT_MIN_CONFIDENCE = 0.70
DETECTION_EVENT_CLASS_THRESHOLDS = {
    "person": 0.50,
    "collapsed_building": 0.45,
    "rubble": 0.55,
    "flood_area": 0.55,
    "fire_smoke": 0.55,
    "damaged_vehicle": 0.55,
}
DETECTION_EVENT_CLASS_PRIORITIES = {
    "person": 100,
    "rubble": 70,
    "collapsed_building": 70,
    "blocked_road": 65,
    "damaged_vehicle": 65,
    "fire_smoke": 65,
    "flood_area": 65,
}
DETECTION_EVENT_CLASSES = [
    "person",
    "rubble",
    "blocked_road",
    "collapsed_building",
    "damaged_vehicle",
    "fire_smoke",
    "flood_area",
]
DETECTION_EVENT_MAX_ITEMS = 60
DETECTION_EVENT_DEDUP_SECONDS = 8.0
DETECTION_EVENT_GPS_EXACT_DEDUP_METERS = 5.0
DETECTION_EVENT_GPS_NEAR_DEDUP_METERS = 20.0
DETECTION_EVENT_IMAGE_HASH_MAX_DISTANCE = 14
DETECTION_EVENT_SNAPSHOT_DIR = BASE_DIR / "static" / "detections"


# Dataset feedback / sahada yanlis tespit toplama
DATASET_FEEDBACK_DIR = BASE_DIR / "dataset_feedback"
FEEDBACK_IMAGES_DIR = DATASET_FEEDBACK_DIR / "images" / "train"
FEEDBACK_LABELS_DIR = DATASET_FEEDBACK_DIR / "labels" / "train"
FEEDBACK_REVIEW_IMAGES_DIR = DATASET_FEEDBACK_DIR / "images" / "review"
FEEDBACK_REVIEW_LABELS_DIR = DATASET_FEEDBACK_DIR / "labels" / "review"
FEEDBACK_CROPS_DIR = DATASET_FEEDBACK_DIR / "crops"
FEEDBACK_METADATA_PATH = DATASET_FEEDBACK_DIR / "metadata.jsonl"
FEEDBACK_CLASS_NAMES = [
    "person",
    "rubble",
    "blocked_road",
    "collapsed_building",
    "damaged_vehicle",
    "fire_smoke",
    "rescue_worker",
    "safe_passage",
    "flood_area",
]


# Kamera ayarlari
DEFAULT_CAMERA = 0
VALID_CAMERA_IDS = (0, 1)
RPICAM_COMMAND = "rpicam-vid"
RPICAM_STREAM_READ_SIZE = 4096

CAM0_CONFIG = {
    "id": 0,
    "name": "Pi Camera V3",
    "width": 1280,
    "height": 720,
    "framerate": 30,
    "extra_controls": ["--hflip", "--vflip", "--ev", "0.4"],
}

CAM1_CONFIG = {
    "id": 1,
    "name": "Gece gorus kamerasi",
    "width": 1280,
    "height": 720,
    "framerate": 30,
    "extra_controls": ["--gain", "1.2", "--shutter", "10000"],
}

CAMERA_CONFIGS = {
    CAM0_CONFIG["id"]: CAM0_CONFIG,
    CAM1_CONFIG["id"]: CAM1_CONFIG,
}


# 915 MHz istasyon telemetrisi
TELEMETRY_PORT = "/dev/serial0"
TELEMETRY_BAUD = 57600
TELEMETRY_TIMEOUT = 1
TELEMETRY_DISCONNECT_TIMEOUT = 5.0
TELEMETRY_RECONNECT_DELAY = 2.0


# Orange Cube MAVLink
MAVLINK_PORT = "/dev/ttyAMA4"
MAVLINK_BAUD = 57600
MAVLINK_SOURCE_SYSTEM = 255
MAVLINK_HEARTBEAT_TIMEOUT = 10
MAVLINK_DISCONNECT_TIMEOUT = 5.0
MAVLINK_RECONNECT_DELAY = 2.0
MAVLINK_STREAM_RATE = 4


# AMG8833 termal sensor
AMG8833_I2C_BUS = 1
AMG8833_ADDRESSES = [0x69, 0x68]
AMG8833_PIXEL_BASE = 0x80
AMG8833_THERMISTOR_L = 0x0E
AMG8833_THERMISTOR_H = 0x0F
AMG8833_MATRIX_SIZE = 8
AMG8833_PIXEL_COUNT = 64
AMG8833_HOTSPOT_THRESHOLD = 38.0
AMG8833_READ_INTERVAL = 1.0
AMG8833_RECONNECT_DELAY = 2.0

# Eski fonksiyon adlariyla uyumluluk icin register sabitleri
PIXEL_BASE = AMG8833_PIXEL_BASE
THERMISTOR_L = AMG8833_THERMISTOR_L
THERMISTOR_H = AMG8833_THERMISTOR_H


<<<<<<< HEAD
# Inis yaklasma sensorleri
=======
# Inis yaklasma sensoru
>>>>>>> 82cd033 (orange cube entegrasyonu otopilot)
LANDING_MZ80_GPIO_PIN = 18
LANDING_MZ80_ACTIVE_LOW = True
LANDING_MZ80_DETECT_DISTANCE_CM = 80.0
LANDING_MZ80_READ_INTERVAL = 0.05

<<<<<<< HEAD
SHARP_GP2Y0A41_MAX_DISTANCE_CM = 30.0
SHARP_GP2Y0A41_MIN_VALID_CM = 4.0
SHARP_GP2Y0A41_MAX_VALID_CM = 35.0
SHARP_ADC_MAX_VOLTAGE = 3.3
SHARP_ADC_MAX_RAW = 4095.0
SHARP_ADC_FIELD = "adc1"
=======
>>>>>>> 82cd033 (orange cube entegrasyonu otopilot)
LANDING_WARNING_DISTANCE_CM = 80.0
LANDING_DANGER_DISTANCE_CM = 30.0

# Otomatik inis yardimi
# Motor PWM'ine dogrudan mudahale edilmez; Cube stabilizasyonu korunarak MAVLink
# hiz komutu kullanilir. Sahada kalibrasyon yapmadan hizlari yukseltmeyin.
AUTO_LANDING_ENABLED_DEFAULT = False
AUTO_LANDING_CONTROL_MODE = "GUIDED_VELOCITY"
AUTO_LANDING_START_MODE = "GUIDED"
AUTO_LANDING_HOLD_MODE = "LOITER"
AUTO_LANDING_REQUIRE_ARMED = True
AUTO_LANDING_REQUIRE_SENSOR = True
AUTO_LANDING_SENSOR_TIMEOUT_SEC = 1.2
AUTO_LANDING_COMMAND_INTERVAL_SEC = 0.35
AUTO_LANDING_FAST_ABOVE_CM = 120.0
AUTO_LANDING_SLOW_BELOW_CM = 80.0
AUTO_LANDING_FINAL_BELOW_CM = 30.0
AUTO_LANDING_HOLD_BELOW_CM = 18.0
AUTO_LANDING_TOUCHDOWN_BELOW_CM = 10.0
AUTO_LANDING_FAST_DESCENT_MPS = 0.45
AUTO_LANDING_SLOW_DESCENT_MPS = 0.22
AUTO_LANDING_FINAL_DESCENT_MPS = 0.08
AUTO_LANDING_DISARM_ON_TOUCHDOWN = False


# SERVO9 / Orange Cube AUX1 tek eksenli kamera servo ayarlari
SERVO_CAMERA = 9
SERVO_PAN = SERVO_CAMERA
SERVO_TILT = SERVO_CAMERA

PAN_MIN = 1250
PAN_CENTER = 2400
PAN_MAX = 2600

TILT_MIN = PAN_MIN
TILT_CENTER = PAN_CENTER
TILT_MAX = PAN_MAX

SERVO_DEFAULT_MIN = PAN_MIN
SERVO_DEFAULT_MAX = PAN_MAX
SERVO_MOVE_STEP = 50
SERVO_MOVE_DELAY = 0.45
SERVO_PWM_DEADBAND = 5


# Deprem ve otomatik gorev ayarlari
DEFAULT_EARTHQUAKE_THRESHOLD = 1.5
THRESHOLD_VALUE_DEFAULT = DEFAULT_EARTHQUAKE_THRESHOLD

# Otonom gorev ana ayarlari
AUTO_MISSION_ENABLED = True
AUTO_MISSION_START_ON_EARTHQUAKE = True
AUTO_MISSION_EARTHQUAKE_CONFIRM_SECONDS = 2.0
AUTO_TAKEOFF_ALTITUDE_M = 10
AUTO_MISSION_REQUIRE_GPS = True
AUTO_MISSION_MIN_SATELLITES = 8
AUTO_MISSION_MIN_BATTERY_VOLTAGE = 14.0
AUTO_MISSION_RTL_ON_STOP = True
AUTO_MISSION_RTL_AFTER_FINISH = True
AUTO_MISSION_RETRIGGER_COOLDOWN_SECONDS = 60

# Eski servis isimleriyle uyumluluk
AUTO_MISSION_ENABLED_DEFAULT = AUTO_MISSION_ENABLED
AUTO_ARM_ON_EARTHQUAKE = AUTO_MISSION_START_ON_EARTHQUAKE
AUTO_ARM_COOLDOWN = AUTO_MISSION_RETRIGGER_COOLDOWN_SECONDS
AUTO_MISSION_CHECK_INTERVAL = 0.4
AUTO_MISSION_SEQUENCE_ENABLED = True
<<<<<<< HEAD
AUTO_MISSION_EARTHQUAKE_CONFIRM_SEC = 3.0
AUTO_MISSION_EARTHQUAKE_GAP_TOLERANCE_SEC = 0.8
AUTO_MISSION_TAKEOFF_ALTITUDE_M = 3.0
AUTO_MISSION_TAKEOFF_SETTLE_SEC = 8.0
AUTO_MISSION_SCAN_DURATION_SEC = 45.0
AUTO_MISSION_SCAN_MIN_ALTITUDE_M = 1.5
AUTO_MISSION_LAND_AFTER_SCAN = True
=======
AUTO_MISSION_EARTHQUAKE_CONFIRM_SEC = AUTO_MISSION_EARTHQUAKE_CONFIRM_SECONDS
AUTO_MISSION_EARTHQUAKE_GAP_TOLERANCE_SEC = 0.8
AUTO_MISSION_TAKEOFF_ALTITUDE_M = AUTO_TAKEOFF_ALTITUDE_M
AUTO_MISSION_TAKEOFF_SETTLE_SEC = 8.0
AUTO_MISSION_SCAN_DURATION_SEC = 45.0
AUTO_MISSION_SCAN_MIN_ALTITUDE_M = 1.5
AUTO_MISSION_LAND_AFTER_SCAN = not AUTO_MISSION_RTL_AFTER_FINISH
>>>>>>> 82cd033 (orange cube entegrasyonu otopilot)


# Log ayarlari
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "detas.log"
LOG_MAX_ITEMS = 30
LOG_TIME_FORMAT = "%H:%M:%S"
LOG_ENCODING = "utf-8"


# Otomatik motor test ayarlari
# PERVANELER TAKILI DEGILKEN kullan.
# Gercek uçuşta AUTO_MOTOR_SPIN_TEST_ON_EARTHQUAKE = True yap.
AUTO_MOTOR_SPIN_TEST_ON_EARTHQUAKE = True
MOTOR_TEST_THROTTLE_PERCENT = 22
MOTOR_TEST_DURATION_SEC = 1.5
MOTOR_TEST_MOTOR_COUNT = 4
MOTOR_TEST_GAP_SEC = 0.4


# ===== DETAS EARTHQUAKE ARM ONLY MODE START =====
# Deprem tetiklenince sadece ARM gönder.
# Otomatik motor test / otomatik disarm kapalı.
AUTO_ARM_ON_EARTHQUAKE = True
AUTO_MOTOR_SPIN_TEST_ON_EARTHQUAKE = False
AUTO_MOTOR_TEST_ON_EARTHQUAKE = False
AUTO_DISARM_AFTER_MOTOR_TEST = False
MOTOR_TEST_AUTO_DISARM = False
AUTO_MISSION_DISARM_AFTER_TEST = False
AUTO_MISSION_ENABLED_DEFAULT = AUTO_MISSION_ENABLED
AUTO_ARM_ON_EARTHQUAKE = AUTO_MISSION_START_ON_EARTHQUAKE
AUTO_ARM_COOLDOWN = AUTO_MISSION_RETRIGGER_COOLDOWN_SECONDS
# ===== DETAS EARTHQUAKE ARM ONLY MODE END =====
