"""DETAS detection pipeline.

Mevcut Raspberry Pi akisi Hailo postprocess ile JPEG uzerine kutu ciziyor.
Bu servis o kutulari okur, varsa supervision ile `sv.Detections` uzerinden
NMS uygular ve panel icin temiz bir detection listesi uretir.
"""

from copy import deepcopy

from config import (
    DETECTION_DEFAULT_CLASS,
    DETECTION_MAX_COUNT,
    DETECTION_MAX_FRAME_AREA_RATIO,
    DETECTION_MERGE_IOU_THRESHOLD,
    DETECTION_MIN_BOX_AREA,
    DETECTION_MIN_BOX_HEIGHT,
    DETECTION_MIN_BOX_WIDTH,
    DETECTION_RESIZE_MAX_WIDTH,
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
    import supervision as sv

    SV_AVAILABLE = True
except Exception:
    sv = None
    SV_AVAILABLE = False


def _normalize_detection(detection, index):
    if isinstance(detection, dict):
        item = deepcopy(detection)
        item.setdefault("name", DETECTION_DEFAULT_CLASS)
        item.setdefault("confidence", "AI")
        item.setdefault("source", "detas")
        item.setdefault("id", index + 1)
        return item

    return {
        "id": index + 1,
        "name": str(detection),
        "confidence": "AI",
        "source": "detas",
    }


def update_detections(detections):
    """Detection listesini ve sayisini merkezi state'e yazar."""
    try:
        normalized = [
            _normalize_detection(item, index)
            for index, item in enumerate(list(detections or [])[:DETECTION_MAX_COUNT])
        ]

        state.update(
            detection_count=len(normalized),
            detections=normalized,
        )
        return normalized
    except Exception as exc:
        add_log(f"Detection listesi guncelleme hatasi: {exc}")
        return []


def set_detection_count(count):
    """Yalnizca sayi varsa panel uyumlu detection listesi olusturur."""
    try:
        count = max(0, min(int(count), DETECTION_MAX_COUNT))
    except Exception:
        count = 0

    return len(update_detections({
        "name": DETECTION_DEFAULT_CLASS,
        "confidence": "AI",
        "source": "count_fallback",
    } for _ in range(count)))


def clear_detections():
    state.update(
        detection_count=0,
        detections=[],
        detection_engine="none",
        detection_supervision_available=SV_AVAILABLE,
    )


def get_detections():
    snapshot = state.snapshot()
    return {
        "detection_count": snapshot["detection_count"],
        "detections": snapshot["detections"],
    }


def _decode_jpeg(jpg_bytes):
    if not CV_AVAILABLE or not jpg_bytes:
        return None, 1.0

    array = np.frombuffer(jpg_bytes, dtype=np.uint8)
    frame = cv2.imdecode(array, cv2.IMREAD_COLOR)

    if frame is None:
        return None, 1.0

    height, width = frame.shape[:2]
    scale = 1.0

    if width > DETECTION_RESIZE_MAX_WIDTH:
        scale = DETECTION_RESIZE_MAX_WIDTH / width
        frame = cv2.resize(frame, (DETECTION_RESIZE_MAX_WIDTH, int(height * scale)))

    return frame, scale


def _extract_hailo_overlay_boxes(frame):
    """Hailo'nun JPEG uzerine cizdigi yesil kutulari xyxy olarak cikarir."""
    lower_green = np.array([0, 120, 0], dtype=np.uint8)
    upper_green = np.array([130, 255, 130], dtype=np.uint8)
    mask = cv2.inRange(frame, lower_green, upper_green)

    kernel = np.ones((9, 9), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    frame_area = frame.shape[0] * frame.shape[1]
    boxes = []

    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        area = width * height

        if (
            width < DETECTION_MIN_BOX_WIDTH
            or height < DETECTION_MIN_BOX_HEIGHT
            or area < DETECTION_MIN_BOX_AREA
            or area > frame_area * DETECTION_MAX_FRAME_AREA_RATIO
        ):
            continue

        boxes.append([x, y, x + width, y + height])

    return boxes


def _box_iou(box_a, box_b):
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])

    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = max(0, box_a[2] - box_a[0]) * max(0, box_a[3] - box_a[1])
    area_b = max(0, box_b[2] - box_b[0]) * max(0, box_b[3] - box_b[1])
    union = area_a + area_b - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def _fallback_nms(boxes):
    kept = []

    for box in sorted(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True):
        if all(_box_iou(box, kept_box) <= DETECTION_MERGE_IOU_THRESHOLD for kept_box in kept):
            kept.append(box)

    return kept[:DETECTION_MAX_COUNT]


def _supervision_nms(boxes):
    if not SV_AVAILABLE or not boxes:
        return None

    try:
        detections = sv.Detections(
            xyxy=np.array(boxes, dtype=float),
            confidence=np.ones(len(boxes), dtype=float),
            class_id=np.zeros(len(boxes), dtype=int),
        )

        if hasattr(detections, "with_nms"):
            detections = detections.with_nms(threshold=DETECTION_MERGE_IOU_THRESHOLD)

        return detections
    except Exception as exc:
        add_log(f"supervision detection hatasi: {exc}")
        return None


def _detections_to_panel_items(boxes, scale, source):
    items = []

    for index, box in enumerate(boxes[:DETECTION_MAX_COUNT]):
        x1, y1, x2, y2 = [int(round(value / scale)) for value in box]
        items.append({
            "id": index + 1,
            "name": DETECTION_DEFAULT_CLASS,
            "confidence": "AI",
            "source": source,
            "bbox": [x1, y1, x2, y2],
        })

    return items


def process_jpeg(jpg_bytes):
    """Kamera servisinden gelen JPEG ile detection state'ini gunceller."""
    if not CV_AVAILABLE:
        clear_detections()
        return 0

    try:
        frame, scale = _decode_jpeg(jpg_bytes)
        if frame is None:
            clear_detections()
            return 0

        boxes = _extract_hailo_overlay_boxes(frame)
        detections = _supervision_nms(boxes)

        if detections is not None:
            clean_boxes = detections.xyxy.tolist()
            source = "supervision"
        else:
            clean_boxes = _fallback_nms(boxes)
            source = "opencv_fallback"

        items = _detections_to_panel_items(clean_boxes, scale, source)
        update_detections(items)
        state.update(
            detection_engine=source,
            detection_supervision_available=SV_AVAILABLE,
        )
        return len(items)

    except Exception as exc:
        add_log(f"Detection pipeline hatasi: {exc}")
        clear_detections()
        return 0


def estimate_detection_count_from_jpeg(jpg_bytes):
    return process_jpeg(jpg_bytes)


update_detection_state_from_jpeg = process_jpeg
