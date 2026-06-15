"""DETAS YOLO detection durum ve JPEG kutu sayim servisi."""

from copy import deepcopy

from config import (
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


def _normalize_detection(detection, index):
    """Detection verisini panelin kullandigi JSON formatina cevirir."""
    if isinstance(detection, dict):
        item = deepcopy(detection)
        item.setdefault("name", f"nesne_{index + 1}")
        item.setdefault("confidence", "AI")
        return item

    return {
        "name": str(detection),
        "confidence": "AI",
    }


def update_detections(detections):
    """Detection listesini ve sayisini merkezi state'e yazar."""
    try:
        if detections is None:
            detections = []

        normalized = [
            _normalize_detection(item, index)
            for index, item in enumerate(list(detections)[:DETECTION_MAX_COUNT])
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
    """Yalnizca sayi varsa uyumlu bir detection listesi olusturur."""
    try:
        count = max(0, min(int(count), DETECTION_MAX_COUNT))
    except Exception:
        count = 0

    detections = [
        {
            "name": f"nesne_{index + 1}",
            "confidence": "AI",
        }
        for index in range(count)
    ]

    state.update(
        detection_count=count,
        detections=detections,
    )
    return count


def clear_detections():
    """Paneldeki detection bilgilerini temizler."""
    state.update(detection_count=0, detections=[])


def get_detections():
    """Mevcut detection verilerinin guvenli bir kopyasini dondurur."""
    snapshot = state.snapshot()
    return {
        "detection_count": snapshot["detection_count"],
        "detections": snapshot["detections"],
    }


def estimate_detection_count_from_jpeg(jpg_bytes):
    """Hailo tarafindan JPEG uzerine cizilen yesil kutulari tahmini sayar."""
    if not CV_AVAILABLE or not jpg_bytes:
        return 0

    try:
        array = np.frombuffer(jpg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(array, cv2.IMREAD_COLOR)

        if frame is None:
            return 0

        height, width = frame.shape[:2]

        if width > DETECTION_RESIZE_MAX_WIDTH:
            scale = DETECTION_RESIZE_MAX_WIDTH / width
            frame = cv2.resize(
                frame,
                (DETECTION_RESIZE_MAX_WIDTH, int(height * scale)),
            )

        lower_green = np.array([0, 120, 0], dtype=np.uint8)
        upper_green = np.array([130, 255, 130], dtype=np.uint8)
        mask = cv2.inRange(frame, lower_green, upper_green)

        kernel = np.ones((9, 9), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        frame_area = frame.shape[0] * frame.shape[1]
        boxes = []

        for contour in contours:
            x, y, box_width, box_height = cv2.boundingRect(contour)
            area = box_width * box_height

            if (
                box_width < DETECTION_MIN_BOX_WIDTH
                or box_height < DETECTION_MIN_BOX_HEIGHT
                or area < DETECTION_MIN_BOX_AREA
                or area > frame_area * DETECTION_MAX_FRAME_AREA_RATIO
            ):
                continue

            boxes.append((x, y, box_width, box_height))

        merged = []

        for box in boxes:
            x, y, box_width, box_height = box
            keep = True

            for merged_x, merged_y, merged_width, merged_height in merged:
                intersection_x1 = max(x, merged_x)
                intersection_y1 = max(y, merged_y)
                intersection_x2 = min(x + box_width, merged_x + merged_width)
                intersection_y2 = min(y + box_height, merged_y + merged_height)

                intersection = (
                    max(0, intersection_x2 - intersection_x1)
                    * max(0, intersection_y2 - intersection_y1)
                )
                area1 = box_width * box_height
                area2 = merged_width * merged_height
                union = area1 + area2 - intersection

                if union > 0 and intersection / union > DETECTION_MERGE_IOU_THRESHOLD:
                    keep = False
                    break

            if keep:
                merged.append(box)

        return min(len(merged), DETECTION_MAX_COUNT)

    except Exception as exc:
        add_log(f"YOLO kutu sayim hatasi: {exc}")
        return 0


def update_detection_state_from_jpeg(jpg_bytes):
    """Kamera servisinden gelen JPEG ile detection state'ini gunceller."""
    count = estimate_detection_count_from_jpeg(jpg_bytes)
    set_detection_count(count)
    return count


# Kamera callback'i icin okunabilir takma ad.
process_jpeg = update_detection_state_from_jpeg
