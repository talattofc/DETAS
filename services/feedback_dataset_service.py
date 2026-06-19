"""DETAS dashboard feedback dataset service.

Canli kameradaki son ham JPEG kareyi ve son detection state'ini kullanarak
YOLO formatinda tekrar egitim ornekleri toplar.
"""

import json
import time
from pathlib import Path
from uuid import uuid4

from config import (
    DATASET_FEEDBACK_DIR,
    FEEDBACK_CLASS_NAMES,
    FEEDBACK_CROPS_DIR,
    FEEDBACK_IMAGES_DIR,
    FEEDBACK_LABELS_DIR,
    FEEDBACK_METADATA_PATH,
    FEEDBACK_REVIEW_IMAGES_DIR,
    FEEDBACK_REVIEW_LABELS_DIR,
)
from services import camera_service
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
    from PIL import Image

    PIL_AVAILABLE = True
except Exception:
    Image = None
    PIL_AVAILABLE = False


NONE_CLASS = "none"
NONE_LABEL = "none / background / yanlis tespit"
CLASS_TO_ID = {name: index for index, name in enumerate(FEEDBACK_CLASS_NAMES)}


def _ensure_feedback_dirs():
    for path in (
        FEEDBACK_IMAGES_DIR,
        FEEDBACK_LABELS_DIR,
        FEEDBACK_REVIEW_IMAGES_DIR,
        FEEDBACK_REVIEW_LABELS_DIR,
        FEEDBACK_CROPS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)

    _write_feedback_yaml()


def _write_feedback_yaml():
    DATASET_FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "path: dataset_feedback",
        "train: images/train",
        "val: images/train",
        "nc: 9",
        "names:",
    ]
    lines.extend(f"{index}: {name}" for index, name in enumerate(FEEDBACK_CLASS_NAMES))
    (DATASET_FEEDBACK_DIR / "feedback.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _relative(path):
    try:
        return str(Path(path).relative_to(DATASET_FEEDBACK_DIR)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _stamp_id():
    return f"{time.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:4]}"


def _image_size(jpg_bytes):
    if CV_AVAILABLE:
        array = np.frombuffer(jpg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if frame is not None:
            height, width = frame.shape[:2]
            return int(width), int(height), frame

    if PIL_AVAILABLE:
        from io import BytesIO

        image = Image.open(BytesIO(jpg_bytes))
        return int(image.width), int(image.height), None

    raise RuntimeError("Goruntu boyutu okunamadi: opencv/Pillow yok")


def _find_detection(detections, detection_id):
    if detection_id is None:
        return None

    wanted = str(detection_id)
    for detection in detections:
        if str(detection.get("id")) == wanted:
            return detection
    return None


def _clip(value, low, high):
    return max(low, min(high, value))


def _bbox_to_yolo(bbox, image_width, image_height):
    if not bbox or len(bbox) < 4:
        raise ValueError("bbox eksik")

    x1, y1, x2, y2 = [float(value) for value in bbox[:4]]
    x1 = _clip(x1, 0.0, float(image_width))
    x2 = _clip(x2, 0.0, float(image_width))
    y1 = _clip(y1, 0.0, float(image_height))
    y2 = _clip(y2, 0.0, float(image_height))

    if x2 <= x1 or y2 <= y1:
        raise ValueError("bbox gecersiz")

    width = x2 - x1
    height = y2 - y1
    x_center = x1 + width / 2.0
    y_center = y1 + height / 2.0

    return (
        x_center / image_width,
        y_center / image_height,
        width / image_width,
        height / image_height,
    )


def _save_crop(frame, bbox, sample_id, detection_id):
    if frame is None or not CV_AVAILABLE or not bbox:
        return None

    try:
        height, width = frame.shape[:2]
        x1, y1, x2, y2 = [int(round(value)) for value in bbox[:4]]
        x1 = int(_clip(x1, 0, width))
        x2 = int(_clip(x2, 0, width))
        y1 = int(_clip(y1, 0, height))
        y2 = int(_clip(y2, 0, height))
        if x2 <= x1 or y2 <= y1:
            return None

        crop = frame[y1:y2, x1:x2]
        crop_path = FEEDBACK_CROPS_DIR / f"{sample_id}_{detection_id}.jpg"
        cv2.imwrite(str(crop_path), crop)
        return _relative(crop_path)
    except Exception:
        return None


def _normalise_selected_class(value):
    text = str(value or NONE_CLASS).strip()
    if text in {"", "background", "yanlis", "yanlis_tespit", "false_positive"}:
        return NONE_CLASS
    return text


def _metadata_line(payload):
    FEEDBACK_METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FEEDBACK_METADATA_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def get_classes():
    _ensure_feedback_dirs()
    return {
        "ok": True,
        "none": {
            "id": None,
            "name": NONE_CLASS,
            "label": NONE_LABEL,
        },
        "classes": [
            {
                "id": index,
                "name": name,
            }
            for index, name in enumerate(FEEDBACK_CLASS_NAMES)
        ],
    }


def capture_feedback(payload=None):
    _ensure_feedback_dirs()
    payload = payload or {}
    latest = camera_service.get_latest_frame()

    if latest is None or not latest.get("jpg"):
        return {
            "ok": False,
            "error": "Kaydedilecek kamera karesi yok. Once /video akisi acik olmali.",
        }, 409

    jpg_bytes = latest["jpg"]
    image_width, image_height, frame = _image_size(jpg_bytes)
    snapshot = state.snapshot()
    detections = list(snapshot.get("detections") or [])
    annotations = payload.get("annotations")
    if annotations is None:
        annotations = payload.get("selections")
    if annotations is None:
        annotations = []

    sample_id = _stamp_id()
    image_path = FEEDBACK_IMAGES_DIR / f"{sample_id}.jpg"
    label_path = FEEDBACK_LABELS_DIR / f"{sample_id}.txt"
    image_path.write_bytes(jpg_bytes)

    label_lines = []
    user_annotations = []

    for annotation in annotations:
        selected_class = _normalise_selected_class(
            annotation.get("true_class") or annotation.get("class_name") or annotation.get("selected_class")
        )
        detection_id = annotation.get("detection_id")
        detection = _find_detection(detections, detection_id)
        model_prediction = deepcopy_detection(detection)

        entry = {
            "detection_id": detection_id,
            "selected_class": selected_class,
            "model_prediction": model_prediction,
            "written_to_label": False,
        }

        if selected_class != NONE_CLASS:
            if selected_class not in CLASS_TO_ID:
                return {
                    "ok": False,
                    "error": f"Gecersiz sinif: {selected_class}",
                }, 400

            if detection is None:
                return {
                    "ok": False,
                    "error": f"Tespit bulunamadi: {detection_id}",
                }, 400

            try:
                x_center, y_center, width, height = _bbox_to_yolo(
                    detection.get("bbox"),
                    image_width,
                    image_height,
                )
            except Exception as exc:
                return {
                    "ok": False,
                    "error": f"bbox label'a cevrilemedi: {exc}",
                }, 400

            label_lines.append(
                f"{CLASS_TO_ID[selected_class]} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"
            )
            entry["written_to_label"] = True
            entry["crop"] = _save_crop(frame, detection.get("bbox"), sample_id, detection_id)

        user_annotations.append(entry)

    label_path.write_text("\n".join(label_lines) + ("\n" if label_lines else ""), encoding="utf-8")

    metadata = {
        "id": sample_id,
        "image": _relative(image_path),
        "label": _relative(label_path),
        "timestamp": time.time(),
        "camera": latest.get("camera"),
        "frame_timestamp": latest.get("timestamp"),
        "image_width": image_width,
        "image_height": image_height,
        "model_predictions": detections,
        "user_annotations": user_annotations,
        "source": "dashboard_feedback",
        "note": payload.get("note") or "false_positive_or_corrected_sample",
    }
    _metadata_line(metadata)
    add_log(f"Feedback dataset karesi kaydedildi: {image_path.name}")

    return {
        "ok": True,
        "id": sample_id,
        "image": str(image_path),
        "label": str(label_path),
        "label_lines": len(label_lines),
        "metadata": metadata,
        "stats": get_stats()["stats"],
    }


def deepcopy_detection(detection):
    if detection is None:
        return None
    return json.loads(json.dumps(detection, ensure_ascii=False))


def _iter_image_files():
    if not FEEDBACK_IMAGES_DIR.exists():
        return []
    return [
        path for path in FEEDBACK_IMAGES_DIR.iterdir()
        if path.suffix.lower() in {".jpg", ".jpeg", ".png"}
    ]


def get_stats():
    _ensure_feedback_dirs()
    images = _iter_image_files()
    empty_labels = 0
    class_distribution = {name: 0 for name in FEEDBACK_CLASS_NAMES}

    for image_path in images:
        label_path = FEEDBACK_LABELS_DIR / f"{image_path.stem}.txt"
        if not label_path.exists() or not label_path.read_text(encoding="utf-8").strip():
            empty_labels += 1
            continue

        for line in label_path.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if not parts:
                continue
            try:
                class_id = int(parts[0])
            except Exception:
                continue
            if 0 <= class_id < len(FEEDBACK_CLASS_NAMES):
                class_distribution[FEEDBACK_CLASS_NAMES[class_id]] += 1

    return {
        "ok": True,
        "stats": {
            "image_count": len(images),
            "negative_count": empty_labels,
            "class_distribution": class_distribution,
            "dataset_dir": str(DATASET_FEEDBACK_DIR),
        },
    }


def get_export_info():
    _ensure_feedback_dirs()
    feedback_yaml = DATASET_FEEDBACK_DIR / "feedback.yaml"
    return {
        "ok": True,
        "dataset_dir": str(DATASET_FEEDBACK_DIR),
        "images_dir": str(FEEDBACK_IMAGES_DIR),
        "labels_dir": str(FEEDBACK_LABELS_DIR),
        "review_images_dir": str(FEEDBACK_REVIEW_IMAGES_DIR),
        "review_labels_dir": str(FEEDBACK_REVIEW_LABELS_DIR),
        "crops_dir": str(FEEDBACK_CROPS_DIR),
        "metadata_path": str(FEEDBACK_METADATA_PATH),
        "feedback_yaml": str(feedback_yaml),
        "feedback_yaml_content": feedback_yaml.read_text(encoding="utf-8"),
    }


def get_latest_frame_jpeg():
    latest = camera_service.get_latest_frame()
    if latest is None:
        return None
    return latest.get("jpg")
