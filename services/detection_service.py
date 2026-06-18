"""DETAS YOLO detection pipeline.

Bu servis kamera servisinden gelen JPEG karelerini alir, Ultralytics YOLO
modeli ile tespit yapar, kutulari goruntuye cizer ve merkezi state'i gunceller.
Hailo AI HAT icin ileride eklenecek backend sinifi ayrica birakildi.
"""

import threading
import time
from copy import deepcopy
from uuid import uuid4

from config import (
    DETAS_ALLOWED_CLASSES,
    DETAS_CLASS_THRESHOLDS,
    DETAS_DISABLED_CLASSES,
    DETECTION_CONFIDENCE,
    DETECTION_EVENT_CLASSES,
    DETECTION_EVENT_CLASS_PRIORITIES,
    DETECTION_EVENT_CLASS_THRESHOLDS,
    DETECTION_EVENT_DEDUP_SECONDS,
    DETECTION_EVENT_MAX_ITEMS,
    DETECTION_EVENT_MIN_CONFIDENCE,
    DETECTION_EVENT_SNAPSHOT_DIR,
    DETECTION_IMGSZ,
    DETECTION_MAX_COUNT,
    LABELS_PATH,
    PERSON_MODEL_PATH,
    YOLO_MODEL_BACKEND,
    YOLO_ONNX_MODEL_PATH,
    YOLO_PT_MODEL_PATH,
)
from services.logger_service import add_log
from services.state import state

try:
    import cv2
    import numpy as np

    CV_AVAILABLE = True
except Exception:
    cv2 = None
    np = None
    CV_AVAILABLE = False

try:
    from ultralytics import YOLO

    ULTRALYTICS_AVAILABLE = True
except Exception:
    YOLO = None
    ULTRALYTICS_AVAILABLE = False


_backend_lock = threading.Lock()
_detas_backend = None
_person_backend = None
_model_errors = {}
_backend_load_attempted = set()
_last_detections = []


def _read_labels():
    if not LABELS_PATH.exists():
        return []

    try:
        return [
            line.strip()
            for line in LABELS_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except Exception as exc:
        add_log(f"labels.txt okunamadi: {exc}")
        return []


def _normalize_class_name(name):
    if name == "safe_passage":
        return "open_road"
    return name


class DetectionBackend:
    """Inference backend arayuzu."""

    name = "base"

    def detect(self, frame):
        raise NotImplementedError


class UltralyticsBackend(DetectionBackend):
    """Ultralytics YOLO taban sinifi."""

    def __init__(self, model_path, labels=None, name_prefix="ultralytics"):
        if not ULTRALYTICS_AVAILABLE:
            raise RuntimeError("ultralytics paketi yuklu degil")

        if not model_path.exists():
            raise FileNotFoundError(str(model_path))

        self.model_path = model_path
        self.labels = labels or []
        self.model = YOLO(str(model_path))
        self.name = f"{name_prefix}_{model_path.suffix.lstrip('.')}"

    def _label_for(self, class_id):
        if 0 <= class_id < len(self.labels):
            return self.labels[class_id]

        names = getattr(self.model, "names", {})
        return str(names.get(class_id, f"class_{class_id}"))

    def _predict(self, frame, classes=None):
        results = self.model.predict(
            source=frame,
            conf=DETECTION_CONFIDENCE,
            imgsz=DETECTION_IMGSZ,
            classes=classes,
            verbose=False,
        )

        if not results:
            return []

        result = results[0]
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return []

        return boxes

    def _box_to_detection(self, box, index, name=None):
        xyxy = box.xyxy[0].detach().cpu().numpy().tolist()
        confidence = float(box.conf[0].detach().cpu().item())
        class_id = int(box.cls[0].detach().cpu().item())
        label = _normalize_class_name(name or self._label_for(class_id))

        return {
            "id": index + 1,
            "name": label,
            "class_name": label,
            "class_id": class_id,
            "confidence": round(confidence, 4),
            "score": round(confidence, 4),
            "bbox": [round(float(value), 2) for value in xyxy],
            "source": self.name,
        }


class DetasDisasterBackend(UltralyticsBackend):
    """DETAS afet modeli; person/rescue_worker sonuclarini kullanmaz."""

    def __init__(self, model_path, labels):
        super().__init__(model_path, labels=labels, name_prefix="detas_disaster")

    def detect(self, frame):
        boxes = self._predict(frame)
        detections = []
        for box in boxes:
            detection = self._box_to_detection(box, len(detections))
            name = detection["name"]
            confidence = detection["confidence"]

            if name in DETAS_DISABLED_CLASSES:
                continue

            if name not in DETAS_ALLOWED_CLASSES:
                continue

            if confidence < DETAS_CLASS_THRESHOLDS.get(name, DETECTION_CONFIDENCE):
                continue

            detections.append(detection)
            if len(detections) >= DETECTION_MAX_COUNT:
                break

        return detections


class PersonBackend(UltralyticsBackend):
    """COCO yolov8n modeli; sadece class 0 person cikarir."""

    def __init__(self, model_path):
        super().__init__(model_path, labels=["person"], name_prefix="person")

    def detect(self, frame):
        boxes = self._predict(frame, classes=[0])
        detections = []
        for box in boxes:
            detection = self._box_to_detection(box, len(detections), name="person")
            confidence = detection["confidence"]

            if confidence < DETAS_CLASS_THRESHOLDS.get("person", DETECTION_CONFIDENCE):
                continue

            detections.append(detection)
            if len(detections) >= DETECTION_MAX_COUNT:
                break

        return detections


class HailoBackend(DetectionBackend):
    """Ileride best.hef / Hailo AI HAT entegrasyonu icin ayrilan sinif."""

    name = "hailo_pending"

    def detect(self, frame):
        return []


def _model_path_for_backend():
    backend = str(YOLO_MODEL_BACKEND or "pt").lower()
    if backend == "onnx":
        return YOLO_ONNX_MODEL_PATH
    return YOLO_PT_MODEL_PATH


def _load_backend(key, factory):
    global _model_errors, _backend_load_attempted

    if key in _backend_load_attempted:
        return None

    _backend_load_attempted.add(key)

    try:
        backend = factory()
        _model_errors.pop(key, None)
        model_name = getattr(backend, "model_path", None)
        add_log(f"{key} modeli yuklendi: {model_name.name if model_name else backend.name}")
        return backend
    except Exception as exc:
        _model_errors[key] = str(exc)
        add_log(f"{key} modeli yuklenemedi: {exc}")
        return None


def _get_backends():
    global _detas_backend, _person_backend

    with _backend_lock:
        if _detas_backend is None:
            _detas_backend = _load_backend(
                "detas",
                lambda: DetasDisasterBackend(_model_path_for_backend(), _read_labels()),
            )

        if _person_backend is None:
            _person_backend = _load_backend(
                "person",
                lambda: PersonBackend(PERSON_MODEL_PATH),
            )

        return [backend for backend in (_detas_backend, _person_backend) if backend is not None]


def _decode_jpeg(jpg_bytes):
    if not CV_AVAILABLE or not jpg_bytes:
        return None

    array = np.frombuffer(jpg_bytes, dtype=np.uint8)
    return cv2.imdecode(array, cv2.IMREAD_COLOR)


def _encode_jpeg(frame):
    if not CV_AVAILABLE or frame is None:
        return None

    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        return None

    return encoded.tobytes()


def _class_counts(detections):
    counts = {}
    for detection in detections:
        name = detection.get("name", "unknown")
        counts[name] = counts.get(name, 0) + 1
    return counts


def _renumber_detections(detections):
    limited = detections[:DETECTION_MAX_COUNT]
    for index, detection in enumerate(limited):
        detection["id"] = index + 1
    return limited


def _run_all_backends(frame):
    detections = []
    engines = []
    backends = _get_backends()

    if not backends:
        return [], "disabled"

    for backend in backends:
        try:
            backend_detections = backend.detect(frame)
            detections.extend(backend_detections)
            engines.append(backend.name)
        except Exception as exc:
            _model_errors[backend.name] = str(exc)
            add_log(f"{backend.name} inference hatasi: {exc}")

    return _renumber_detections(detections), "+".join(engines) if engines else "error"


def _gps_snapshot(snapshot):
    lat = snapshot.get("cube_lat") or snapshot.get("cube_latitude") or snapshot.get("lat")
    lng = snapshot.get("cube_lng") or snapshot.get("cube_longitude") or snapshot.get("lng")

    try:
        lat = float(lat)
        lng = float(lng)
        gps_known = -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0
    except Exception:
        lat = None
        lng = None
        gps_known = False

    return {
        "lat": lat if gps_known else None,
        "lng": lng if gps_known else None,
        "gps_known": gps_known,
        "gps_text": f"{lat:.6f}, {lng:.6f}" if gps_known else "Bilinmiyor",
        "gps_fix": snapshot.get("cube_gps_fix", 0),
        "satellites": snapshot.get("cube_satellites", 0),
    }


def _box_iou(box_a, box_b):
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])

    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = max(0, box_a[2] - box_a[0]) * max(0, box_a[3] - box_a[1])
    area_b = max(0, box_b[2] - box_b[0]) * max(0, box_b[3] - box_b[1])
    union = area_a + area_b - intersection
    return 0.0 if union <= 0 else intersection / union


def _is_recent_duplicate(events, class_name, confidence, bbox, now):
    for event in events:
        try:
            if now - float(event.get("timestamp", 0)) > DETECTION_EVENT_DEDUP_SECONDS:
                continue
        except Exception:
            continue

        if event.get("class_name") != class_name:
            continue

        old_bbox = event.get("bbox")
        if bbox and old_bbox and _box_iou(bbox, old_bbox) < 0.60:
            continue

        if abs(float(event.get("confidence", 0)) - confidence) <= 0.08:
            return True

    return False


def _event_threshold_for(class_name):
    return DETECTION_EVENT_CLASS_THRESHOLDS.get(class_name, DETECTION_EVENT_MIN_CONFIDENCE)


def _event_priority(class_name):
    return DETECTION_EVENT_CLASS_PRIORITIES.get(class_name, 50)


def _sort_detection_events(events):
    return sorted(
        events,
        key=lambda event: (
            _event_priority(str(event.get("class_name") or "")),
            float(event.get("timestamp", 0) or 0),
        ),
        reverse=True,
    )


def _save_detection_snapshot(jpg_bytes, event_id):
    if not jpg_bytes:
        return None

    try:
        DETECTION_EVENT_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{event_id}.jpg"
        path = DETECTION_EVENT_SNAPSHOT_DIR / filename
        path.write_bytes(jpg_bytes)
        return f"/static/detections/{filename}"
    except Exception as exc:
        add_log(f"AI olay fotografi kaydedilemedi: {exc}")
        return None


def _register_actionable_events(detections, frame_jpg=None):
    snapshot = state.snapshot()
    events = list(snapshot.get("detection_events") or [])
    gps = _gps_snapshot(snapshot)
    now = time.time()
    changed = False

    for detection in detections:
        class_name = str(detection.get("name") or detection.get("class_name") or "").strip()
        confidence = float(detection.get("confidence", 0.0))
        bbox = detection.get("bbox")

        if class_name not in DETECTION_EVENT_CLASSES:
            continue

        if confidence < _event_threshold_for(class_name):
            continue

        if _is_recent_duplicate(events, class_name, confidence, bbox, now):
            continue

        event_id = f"{int(now)}-{uuid4().hex[:8]}"
        event = {
            "id": event_id,
            "timestamp": now,
            "time": time.strftime("%H:%M:%S"),
            "class_name": class_name,
            "label": class_name.replace("_", " "),
            "confidence": round(confidence, 4),
            "confidence_percent": round(confidence * 100, 1),
            "bbox": bbox,
            "lat": gps["lat"],
            "lng": gps["lng"],
            "gps_known": gps["gps_known"],
            "gps_text": gps["gps_text"],
            "gps_fix": gps["gps_fix"],
            "satellites": gps["satellites"],
            "snapshot_url": _save_detection_snapshot(frame_jpg, event_id),
            "source": detection.get("source", "detas"),
            "priority": _event_priority(class_name),
        }
        events.insert(0, event)
        changed = True
        add_log(f"AI olay: {event['label']} %{event['confidence_percent']} GPS: {event['gps_text']}")

    if changed:
        events = _sort_detection_events(events)[:DETECTION_EVENT_MAX_ITEMS]
        state.update(
            detection_events=events,
            detection_event_count=len(events),
        )


def _update_detection_state(detections, engine):
    now = time.time()
    counts = _class_counts(detections)
    payload = deepcopy(detections)
    state.update(
        detection_count=len(payload),
        detections=payload,
        detected_objects=payload,
        last_detection_time=now if payload else state.snapshot().get("last_detection_time", 0.0),
        detection_count_by_class=counts,
        detection_engine=engine,
        detection_supervision_available=False,
    )


def _color_for_detection(name):
    if name == "person":
        return (0, 180, 255)
    if name == "safe_passage":
        return (25, 180, 90)
    if name in DETECTION_EVENT_CLASSES:
        return (180, 23, 99)
    return (13, 202, 240)


def _draw_detections(frame, detections):
    if not CV_AVAILABLE or frame is None:
        return frame

    for detection in detections:
        bbox = detection.get("bbox")
        if not bbox or len(bbox) < 4:
            continue

        x1, y1, x2, y2 = [int(round(value)) for value in bbox[:4]]
        name = str(detection.get("name", "object"))
        confidence = float(detection.get("confidence", 0.0))
        color = _color_for_detection(name)
        label = f"{name} {confidence * 100:.0f}%"

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        (text_width, text_height), baseline = cv2.getTextSize(
            label,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            2,
        )
        top = max(0, y1 - text_height - baseline - 8)
        cv2.rectangle(
            frame,
            (x1, top),
            (x1 + text_width + 10, top + text_height + baseline + 8),
            color,
            -1,
        )
        cv2.putText(
            frame,
            label,
            (x1 + 5, top + text_height + 3),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

    return frame


def run_detection_on_jpeg(jpg_bytes):
    """JPEG uzerinde inference calistirir, state'i gunceller ve tespitleri dondurur."""
    frame = _decode_jpeg(jpg_bytes)

    if frame is None:
        _update_detection_state([], "opencv_missing")
        return [], jpg_bytes

    try:
        detections, engine = _run_all_backends(frame)
        annotated = _draw_detections(frame.copy(), detections)
        annotated_jpg = _encode_jpeg(annotated) or jpg_bytes
        _update_detection_state(detections, engine)
        _register_actionable_events(detections, annotated_jpg)
        return detections, annotated_jpg
    except Exception as exc:
        add_log(f"YOLO inference hatasi: {exc}")
        _update_detection_state([], "error")
        return [], jpg_bytes


def annotate_jpeg_with_last_detections(jpg_bytes):
    frame = _decode_jpeg(jpg_bytes)
    if frame is None:
        return jpg_bytes

    annotated = _draw_detections(frame, _last_detections)
    return _encode_jpeg(annotated) or jpg_bytes


def process_stream_jpeg(jpg_bytes, run_inference=True):
    """Kamera akisi icin JPEG isler; hata halinde orijinal JPEG'i dondurur."""
    global _last_detections

    if run_inference:
        detections, annotated = run_detection_on_jpeg(jpg_bytes)
        _last_detections = detections
        return annotated

    return annotate_jpeg_with_last_detections(jpg_bytes)


def update_detections(detections, frame_jpg=None):
    """Dis servislerden dogrudan detection listesi gelirse state'i gunceller."""
    normalized = list(detections or [])[:DETECTION_MAX_COUNT]
    _update_detection_state(normalized, "external")
    _register_actionable_events(normalized, frame_jpg)
    return normalized


def clear_detections():
    state.update(
        detection_count=0,
        detections=[],
        detected_objects=[],
        detection_count_by_class={},
        detection_engine="none",
        detection_supervision_available=False,
    )


def get_detections():
    snapshot = state.snapshot()
    model_error = "; ".join(f"{key}: {value}" for key, value in _model_errors.items())
    return {
        "detection_count": snapshot["detection_count"],
        "detections": snapshot["detections"],
        "detected_objects": snapshot["detected_objects"],
        "last_detection_time": snapshot["last_detection_time"],
        "detection_count_by_class": snapshot["detection_count_by_class"],
        "detection_engine": snapshot["detection_engine"],
        "model_error": model_error or None,
    }


def update_detection_state_from_jpeg(jpg_bytes):
    detections, _ = run_detection_on_jpeg(jpg_bytes)
    return len(detections)


def process_jpeg(jpg_bytes):
    detections, _ = run_detection_on_jpeg(jpg_bytes)
    return len(detections)


estimate_detection_count_from_jpeg = process_jpeg
