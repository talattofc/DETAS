"""DETAS YOLO detection pipeline.

Bu servis kamera servisinden gelen JPEG karelerini alir, Ultralytics YOLO
modeli ile tespit yapar, kutulari goruntuye cizer ve merkezi state'i gunceller.
Hailo AI HAT icin ileride eklenecek backend sinifi ayrica birakildi.
"""

import math
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
    DETECTION_EVENT_GPS_EXACT_DEDUP_METERS,
    DETECTION_EVENT_GPS_NEAR_DEDUP_METERS,
    DETECTION_EVENT_IMAGE_HASH_MAX_DISTANCE,
    DETECTION_EVENT_MAX_ITEMS,
    DETECTION_EVENT_MIN_CONFIDENCE,
    DETECTION_EVENT_SNAPSHOT_DIR,
    DETECTION_IMGSZ,
    DETECTION_MAX_COUNT,
    HAILO_CONFIDENCE,
    HAILO_CLASS_THRESHOLDS,
    HAILO_HEF_MODEL_PATH,
    HAILO_INPUT_SIZE,
    HAILO_MAX_CANDIDATES,
    HAILO_NMS_IOU,
    LABELS_PATH,
    PERSON_HAILO_HEF_MODEL_PATH,
    PERSON_HAILO_INPUT_SIZE,
    PERSON_MODEL_PATH,
    PERSON_MODEL_BACKEND,
    READY_HAILO_ALLOWED_CLASSES,
    READY_HAILO_CLASS_THRESHOLDS,
    READY_HAILO_HEF_MODEL_PATH,
    READY_HAILO_INCLUDE_PERSON,
    READY_HAILO_INPUT_SIZE,
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

try:
    from hailo_platform import (
        ConfigureParams,
        FormatType,
        HEF,
        HailoSchedulingAlgorithm,
        HailoStreamInterface,
        InferVStreams,
        InputVStreamParams,
        OutputVStreamParams,
        VDevice,
    )

    HAILO_RUNTIME_AVAILABLE = True
except Exception:
    ConfigureParams = None
    FormatType = None
    HEF = None
    HailoSchedulingAlgorithm = None
    HailoStreamInterface = None
    InferVStreams = None
    InputVStreamParams = None
    OutputVStreamParams = None
    VDevice = None
    HAILO_RUNTIME_AVAILABLE = False


_backend_lock = threading.Lock()
_detas_backend = None
_person_backend = None
_model_errors = {}
_backend_load_attempted = set()
_last_detections = []
_hailo_vdevice = None
_hailo_vdevice_lock = threading.Lock()


COCO_LABELS = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]


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


def _letterbox_frame(frame, size=640):
    height, width = frame.shape[:2]
    ratio = min(size / width, size / height)
    new_width = int(round(width * ratio))
    new_height = int(round(height * ratio))
    pad_x = (size - new_width) / 2
    pad_y = (size - new_height) / 2

    resized = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    left = int(round(pad_x - 0.1))
    top = int(round(pad_y - 0.1))
    canvas[top:top + new_height, left:left + new_width] = resized
    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    return rgb, ratio, left, top


def _sigmoid(values):
    values = np.clip(values, -40, 40)
    return 1.0 / (1.0 + np.exp(-values))


def _softmax(values, axis=-1):
    shifted = values - np.max(values, axis=axis, keepdims=True)
    exp = np.exp(shifted)
    return exp / np.sum(exp, axis=axis, keepdims=True)


def _as_hwc(output):
    try:
        array = np.asarray(output)
    except Exception:
        return None

    array = np.squeeze(array)

    if array.ndim != 3:
        return None

    if array.shape[-1] in (7, 64):
        return array.astype(np.float32, copy=False)

    if array.shape[0] in (7, 64):
        return np.transpose(array, (1, 2, 0)).astype(np.float32, copy=False)

    return None


def _output_values(raw_outputs):
    if isinstance(raw_outputs, dict):
        return list(raw_outputs.values())
    if isinstance(raw_outputs, (list, tuple)):
        return list(raw_outputs)
    return [raw_outputs]


def _shape_summary(value):
    if isinstance(value, dict):
        return {str(key): _shape_summary(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        if not value:
            return [0]
        if len(value) > 8:
            return [len(value), "..."]
        return [_shape_summary(item) for item in value]

    try:
        return list(np.asarray(value).shape)
    except Exception:
        return type(value).__name__


def _rows_from_node(node):
    try:
        array = np.asarray(node, dtype=np.float32)
    except Exception:
        return None

    array = np.squeeze(array)
    if array.size == 0:
        return None

    if array.ndim == 1 and array.shape[0] >= 5:
        return array.reshape(1, -1)

    if array.ndim == 2 and array.shape[-1] >= 5:
        return array

    return None


def _iter_hailo_nms_rows(raw_outputs, class_count):
    for output in _output_values(raw_outputs):
        yield from _iter_hailo_nms_node(output, class_count)


def _iter_hailo_nms_node(node, class_count):
    if isinstance(node, dict):
        for value in node.values():
            yield from _iter_hailo_nms_node(value, class_count)
        return

    try:
        array = np.asarray(node, dtype=np.float32)
    except Exception:
        array = None

    if array is not None and array.dtype != object:
        array = np.squeeze(array)

        if array.size == 0:
            return

        if array.ndim == 3 and array.shape[-1] >= 5:
            for class_id in range(min(array.shape[0], class_count)):
                for row in array[class_id]:
                    yield class_id, row, "yxyx"
            return

        if array.ndim == 2 and array.shape[-1] >= 5:
            for row in array:
                class_id = int(round(float(row[5]))) if row.shape[0] >= 6 else 0
                yield class_id, row, "xyxy"
            return

        if array.ndim == 1 and array.shape[0] >= 5:
            class_id = int(round(float(array[5]))) if array.shape[0] >= 6 else 0
            yield class_id, array, "xyxy"
            return

    if not isinstance(node, (list, tuple)):
        return

    if len(node) == 1:
        yield from _iter_hailo_nms_node(node[0], class_count)
        return

    if class_count and len(node) == class_count:
        for class_id, class_rows in enumerate(node):
            rows = _rows_from_node(class_rows)
            if rows is None:
                continue
            for row in rows:
                yield class_id, row, "yxyx"
        return

    rows = _rows_from_node(node)
    if rows is not None:
        for row in rows:
            class_id = int(round(float(row[5]))) if row.shape[0] >= 6 else 0
            yield class_id, row, "xyxy"
        return

    for item in node:
        yield from _iter_hailo_nms_node(item, class_count)


def _class_aware_nms(candidates, iou_threshold, max_count):
    selected = []
    by_class = {}
    for candidate in candidates:
        by_class.setdefault(candidate["class_id"], []).append(candidate)

    for class_candidates in by_class.values():
        class_candidates.sort(key=lambda item: item["confidence"], reverse=True)
        while class_candidates and len(selected) < max_count:
            best = class_candidates.pop(0)
            selected.append(best)
            class_candidates = [
                item
                for item in class_candidates
                if _box_iou(best["bbox"], item["bbox"]) < iou_threshold
            ]

    selected.sort(key=lambda item: item["confidence"], reverse=True)
    return selected[:max_count]


def _get_hailo_vdevice():
    global _hailo_vdevice

    with _hailo_vdevice_lock:
        if _hailo_vdevice is not None:
            return _hailo_vdevice

        try:
            params = VDevice.create_params()
            if HailoSchedulingAlgorithm is not None:
                try:
                    params.scheduling_algorithm = HailoSchedulingAlgorithm.ROUND_ROBIN
                except Exception:
                    pass
            _hailo_vdevice = VDevice(params)
        except Exception:
            _hailo_vdevice = VDevice()

        return _hailo_vdevice


class HailoRuntimeBackend(DetectionBackend):
    """HailoRT vstream runner tabani."""

    def __init__(self, model_path, labels=None):
        if not HAILO_RUNTIME_AVAILABLE:
            raise RuntimeError("hailo_platform runtime yuklu degil")

        if not model_path.exists():
            raise FileNotFoundError(str(model_path))

        self.model_path = model_path
        self.labels = labels or []
        self._lock = threading.Lock()
        self.hef = HEF(str(model_path))
        self.input_name = self.hef.get_input_vstream_infos()[0].name

        interface = getattr(HailoStreamInterface, "PCIe", None)
        try:
            if interface is None:
                configure_params = ConfigureParams.create_from_hef(self.hef)
            else:
                configure_params = ConfigureParams.create_from_hef(self.hef, interface=interface)
        except TypeError:
            configure_params = ConfigureParams.create_from_hef(self.hef)

        self.vdevice = _get_hailo_vdevice()
        self.network_group = self.vdevice.configure(self.hef, configure_params)[0]
        self.network_group_params = self.network_group.create_params()
        self.input_params = InputVStreamParams.make(
            self.network_group,
            format_type=FormatType.UINT8,
        )
        self.output_params = OutputVStreamParams.make(
            self.network_group,
            format_type=FormatType.FLOAT32,
        )
        self._output_shape_logged = False

    def _label_for(self, class_id):
        if 0 <= class_id < len(self.labels):
            return self.labels[class_id]
        return f"class_{class_id}"

    def _infer(self, input_frame):
        batched = np.expand_dims(input_frame, axis=0).astype(np.uint8, copy=False)
        with self._lock:
            with InferVStreams(self.network_group, self.input_params, self.output_params) as pipeline:
                with self.network_group.activate(self.network_group_params):
                    outputs = pipeline.infer({self.input_name: batched})

        if not self._output_shape_logged:
            self._output_shape_logged = True
            try:
                if isinstance(outputs, dict):
                    shapes = {
                        str(name): _shape_summary(value)
                        for name, value in outputs.items()
                    }
                else:
                    shapes = [_shape_summary(value) for value in (outputs or [])]
                add_log(f"{self.name} Hailo output shapes: {shapes}")
            except Exception:
                pass

        return outputs


class HailoBackend(HailoRuntimeBackend):
    """Hailo-8L HEF raw YOLOv8 heads + Python postprocess backend."""

    name = "detas_disaster_hailo8l"

    def __init__(self, model_path, labels):
        super().__init__(model_path, labels)
        self._empty_debug_count = 0

    def _collect_heads(self, raw_outputs):
        heads = {}
        outputs = raw_outputs.values() if isinstance(raw_outputs, dict) else (raw_outputs or [])
        for output in outputs:
            array = _as_hwc(output)
            if array is None:
                continue

            height, width, channels = array.shape
            if height != width or channels not in (7, 64):
                continue

            entry = heads.setdefault(height, {})
            if channels == 64:
                entry["bbox"] = array
            elif channels == 7:
                entry["cls"] = array

        return [
            (grid, parts["bbox"], parts["cls"])
            for grid, parts in heads.items()
            if "bbox" in parts and "cls" in parts
        ]

    def _decode_heads(self, heads, original_shape, ratio, pad_x, pad_y):
        candidates = []
        original_height, original_width = original_shape[:2]
        bins = np.arange(16, dtype=np.float32)

        for grid, bbox_head, class_head in heads:
            stride = HAILO_INPUT_SIZE / float(grid)
            distances = (_softmax(bbox_head.reshape(grid, grid, 4, 16), axis=-1) * bins).sum(axis=-1)
            scores = _sigmoid(class_head)

            ys, xs = np.meshgrid(np.arange(grid), np.arange(grid), indexing="ij")
            center_x = (xs.astype(np.float32) + 0.5) * stride
            center_y = (ys.astype(np.float32) + 0.5) * stride

            x1 = (center_x - distances[:, :, 0] * stride - pad_x) / ratio
            y1 = (center_y - distances[:, :, 1] * stride - pad_y) / ratio
            x2 = (center_x + distances[:, :, 2] * stride - pad_x) / ratio
            y2 = (center_y + distances[:, :, 3] * stride - pad_y) / ratio

            for class_id, class_name in enumerate(self.labels):
                class_name = _normalize_class_name(class_name)
                if class_name in DETAS_DISABLED_CLASSES or class_name not in DETAS_ALLOWED_CLASSES:
                    continue

                threshold = HAILO_CLASS_THRESHOLDS.get(class_name, HAILO_CONFIDENCE)
                mask = scores[:, :, class_id] >= threshold
                indexes = np.argwhere(mask)

                for row, col in indexes:
                    confidence = float(scores[row, col, class_id])
                    box = [
                        float(np.clip(x1[row, col], 0, original_width - 1)),
                        float(np.clip(y1[row, col], 0, original_height - 1)),
                        float(np.clip(x2[row, col], 0, original_width - 1)),
                        float(np.clip(y2[row, col], 0, original_height - 1)),
                    ]
                    if box[2] <= box[0] or box[3] <= box[1]:
                        continue

                    candidates.append({
                        "class_id": class_id,
                        "name": class_name,
                        "class_name": class_name,
                        "confidence": confidence,
                        "score": confidence,
                        "bbox": box,
                        "source": self.name,
                    })

        candidates.sort(key=lambda item: item["confidence"], reverse=True)
        return candidates[:HAILO_MAX_CANDIDATES]

    def _log_empty_debug(self, heads):
        if self._empty_debug_count >= 5:
            return

        self._empty_debug_count += 1
        try:
            summary = []
            for grid, _bbox_head, class_head in heads:
                scores = _sigmoid(class_head)
                for class_id, class_name in enumerate(self.labels):
                    class_name = _normalize_class_name(class_name)
                    if class_name in DETAS_DISABLED_CLASSES or class_name not in DETAS_ALLOWED_CLASSES:
                        continue
                    summary.append(f"{class_name}@{grid}:{float(scores[:, :, class_id].max()):.3f}")
            add_log(f"{self.name} aday yok, top skorlar: {', '.join(summary)}")
        except Exception as exc:
            add_log(f"{self.name} debug skoru okunamadi: {exc}")

    def _nms_box_to_xyxy(self, raw_box, original_width, original_height, ratio, pad_x, pad_y, order):
        values = [float(value) for value in raw_box[:4]]
        if max(values) <= 1.5:
            values = [
                values[0] * HAILO_INPUT_SIZE,
                values[1] * HAILO_INPUT_SIZE,
                values[2] * HAILO_INPUT_SIZE,
                values[3] * HAILO_INPUT_SIZE,
            ]

        if order == "yxyx":
            y1, x1, y2, x2 = values
        else:
            x1, y1, x2, y2 = values

        if x2 <= x1 or y2 <= y1:
            y1, x1, y2, x2 = values

        x1 = (x1 - pad_x) / ratio
        y1 = (y1 - pad_y) / ratio
        x2 = (x2 - pad_x) / ratio
        y2 = (y2 - pad_y) / ratio

        box = [
            float(np.clip(x1, 0, original_width - 1)),
            float(np.clip(y1, 0, original_height - 1)),
            float(np.clip(x2, 0, original_width - 1)),
            float(np.clip(y2, 0, original_height - 1)),
        ]
        if box[2] <= box[0] or box[3] <= box[1]:
            return None
        return box

    def _detas_candidate(self, class_id, score, box):
        class_name = _normalize_class_name(self._label_for(class_id))
        if class_name in DETAS_DISABLED_CLASSES or class_name not in DETAS_ALLOWED_CLASSES:
            return None
        if score < HAILO_CLASS_THRESHOLDS.get(class_name, HAILO_CONFIDENCE):
            return None
        return {
            "class_id": int(class_id),
            "name": class_name,
            "class_name": class_name,
            "confidence": float(score),
            "score": float(score),
            "bbox": box,
            "source": self.name,
        }

    def _decode_nms_outputs(self, raw_outputs, original_shape, ratio, pad_x, pad_y):
        candidates = []
        original_height, original_width = original_shape[:2]

        for class_id, row, order in _iter_hailo_nms_rows(raw_outputs, len(self.labels)):
            if not (0 <= class_id < len(self.labels)):
                continue
            score = float(row[4])
            box = self._nms_box_to_xyxy(
                row[:4],
                original_width,
                original_height,
                ratio,
                pad_x,
                pad_y,
                order=order,
            )
            if not box:
                continue
            candidate = self._detas_candidate(class_id, score, box)
            if candidate:
                candidates.append(candidate)

        candidates.sort(key=lambda item: item["confidence"], reverse=True)
        return candidates[:HAILO_MAX_CANDIDATES]

    def detect(self, frame):
        if not CV_AVAILABLE or frame is None:
            return []

        input_frame, ratio, pad_x, pad_y = _letterbox_frame(frame, HAILO_INPUT_SIZE)
        raw_outputs = self._infer(input_frame)
        heads = self._collect_heads(raw_outputs)
        if heads:
            candidates = self._decode_heads(heads, frame.shape, ratio, pad_x, pad_y)
        else:
            candidates = self._decode_nms_outputs(raw_outputs, frame.shape, ratio, pad_x, pad_y)

        if not candidates and heads:
            self._log_empty_debug(heads)
        nms_results = _class_aware_nms(candidates, HAILO_NMS_IOU, DETECTION_MAX_COUNT)

        detections = []
        for item in nms_results:
            item = dict(item)
            item["id"] = len(detections) + 1
            item["confidence"] = round(float(item["confidence"]), 4)
            item["score"] = item["confidence"]
            item["bbox"] = [round(float(value), 2) for value in item["bbox"]]
            detections.append(item)

        return detections


class PersonHailoBackend(HailoRuntimeBackend):
    """Hazir Hailo person/face HEF modeli; yalniz person ciktisini kullanir."""

    name = "person_hailo8l"

    def __init__(self, model_path):
        super().__init__(model_path, labels=["person", "face"])

    def _person_candidates_from_nms(self, raw_outputs, original_shape, ratio, pad_x, pad_y):
        candidates = []
        original_height, original_width = original_shape[:2]

        for class_id, row, order in _iter_hailo_nms_rows(raw_outputs, len(self.labels)):
            if class_id != 0:
                continue
            score = float(row[4])
            if score < DETAS_CLASS_THRESHOLDS.get("person", DETECTION_CONFIDENCE):
                continue
            box = self._nms_box_to_xyxy(
                row[:4],
                original_width,
                original_height,
                ratio,
                pad_x,
                pad_y,
                order=order,
            )
            if box:
                candidates.append(self._person_detection(score, box))

        return candidates

    def _nms_box_to_xyxy(self, raw_box, original_width, original_height, ratio, pad_x, pad_y, order):
        values = [float(value) for value in raw_box[:4]]
        if max(values) <= 1.5:
            values = [
                values[0] * HAILO_INPUT_SIZE,
                values[1] * HAILO_INPUT_SIZE,
                values[2] * HAILO_INPUT_SIZE,
                values[3] * HAILO_INPUT_SIZE,
            ]

        a, b, c, d = values

        if order == "yxyx":
            y1, x1, y2, x2 = values
        else:
            x1, y1, x2, y2 = a, b, c, d

        if x2 <= x1 or y2 <= y1:
            y1, x1, y2, x2 = values

        x1 = (x1 - pad_x) / ratio
        y1 = (y1 - pad_y) / ratio
        x2 = (x2 - pad_x) / ratio
        y2 = (y2 - pad_y) / ratio

        box = [
            float(np.clip(x1, 0, original_width - 1)),
            float(np.clip(y1, 0, original_height - 1)),
            float(np.clip(x2, 0, original_width - 1)),
            float(np.clip(y2, 0, original_height - 1)),
        ]

        if box[2] <= box[0] or box[3] <= box[1]:
            return None
        return box

    def _person_detection(self, confidence, box):
        return {
            "class_id": 0,
            "name": "person",
            "class_name": "person",
            "confidence": float(confidence),
            "score": float(confidence),
            "bbox": box,
            "source": self.name,
        }

    def detect(self, frame):
        if not CV_AVAILABLE or frame is None:
            return []

        input_frame, ratio, pad_x, pad_y = _letterbox_frame(frame, PERSON_HAILO_INPUT_SIZE)
        raw_outputs = self._infer(input_frame)
        candidates = self._person_candidates_from_nms(raw_outputs, frame.shape, ratio, pad_x, pad_y)
        nms_results = _class_aware_nms(candidates, HAILO_NMS_IOU, DETECTION_MAX_COUNT)

        detections = []
        for item in nms_results:
            item = dict(item)
            item["id"] = len(detections) + 1
            item["confidence"] = round(float(item["confidence"]), 4)
            item["score"] = item["confidence"]
            item["bbox"] = [round(float(value), 2) for value in item["bbox"]]
            detections.append(item)

        return detections


class ReadyHailoCocoBackend(HailoRuntimeBackend):
    """Hailo hazir COCO YOLO HEF modeli icin B-plan backend."""

    name = "ready_hailo_coco"

    def __init__(self, model_path):
        super().__init__(model_path, labels=COCO_LABELS)

    def _nms_box_to_xyxy(self, raw_box, original_width, original_height, ratio, pad_x, pad_y, order):
        values = [float(value) for value in raw_box[:4]]
        if max(values) <= 1.5:
            values = [
                values[0] * READY_HAILO_INPUT_SIZE,
                values[1] * READY_HAILO_INPUT_SIZE,
                values[2] * READY_HAILO_INPUT_SIZE,
                values[3] * READY_HAILO_INPUT_SIZE,
            ]

        if order == "yxyx":
            y1, x1, y2, x2 = values
        else:
            x1, y1, x2, y2 = values

        if x2 <= x1 or y2 <= y1:
            y1, x1, y2, x2 = values

        x1 = (x1 - pad_x) / ratio
        y1 = (y1 - pad_y) / ratio
        x2 = (x2 - pad_x) / ratio
        y2 = (y2 - pad_y) / ratio

        box = [
            float(np.clip(x1, 0, original_width - 1)),
            float(np.clip(y1, 0, original_height - 1)),
            float(np.clip(x2, 0, original_width - 1)),
            float(np.clip(y2, 0, original_height - 1)),
        ]

        if box[2] <= box[0] or box[3] <= box[1]:
            return None
        return box

    def _candidate(self, class_id, score, box):
        class_name = self._label_for(class_id)
        if class_name == "person" and not READY_HAILO_INCLUDE_PERSON:
            return None
        if class_name not in READY_HAILO_ALLOWED_CLASSES:
            return None
        if score < READY_HAILO_CLASS_THRESHOLDS.get(class_name, DETECTION_CONFIDENCE):
            return None
        return {
            "class_id": int(class_id),
            "name": class_name,
            "class_name": class_name,
            "confidence": float(score),
            "score": float(score),
            "bbox": box,
            "source": self.name,
        }

    def _candidates_from_nms(self, raw_outputs, original_shape, ratio, pad_x, pad_y):
        candidates = []
        original_height, original_width = original_shape[:2]

        for class_id, row, order in _iter_hailo_nms_rows(raw_outputs, len(self.labels)):
            if not (0 <= class_id < len(self.labels)):
                continue
            score = float(row[4])
            box = self._nms_box_to_xyxy(
                row[:4],
                original_width,
                original_height,
                ratio,
                pad_x,
                pad_y,
                order=order,
            )
            if not box:
                continue
            candidate = self._candidate(class_id, score, box)
            if candidate:
                candidates.append(candidate)

        return candidates

    def detect(self, frame):
        if not CV_AVAILABLE or frame is None:
            return []

        input_frame, ratio, pad_x, pad_y = _letterbox_frame(frame, READY_HAILO_INPUT_SIZE)
        raw_outputs = self._infer(input_frame)
        candidates = self._candidates_from_nms(raw_outputs, frame.shape, ratio, pad_x, pad_y)
        nms_results = _class_aware_nms(candidates, HAILO_NMS_IOU, DETECTION_MAX_COUNT)

        detections = []
        for item in nms_results:
            item = dict(item)
            item["id"] = len(detections) + 1
            item["confidence"] = round(float(item["confidence"]), 4)
            item["score"] = item["confidence"]
            item["bbox"] = [round(float(value), 2) for value in item["bbox"]]
            detections.append(item)

        return detections


def _model_path_for_backend():
    backend = str(YOLO_MODEL_BACKEND or "pt").lower()
    if backend == "onnx":
        return YOLO_ONNX_MODEL_PATH
    return YOLO_PT_MODEL_PATH


def _create_detas_backend():
    labels = _read_labels()
    backend = str(YOLO_MODEL_BACKEND or "pt").lower()

    if backend in ("ready_hailo", "coco_hailo", "hailo_ready"):
        try:
            return ReadyHailoCocoBackend(READY_HAILO_HEF_MODEL_PATH)
        except Exception as exc:
            _model_errors["ready_hailo"] = str(exc)
            add_log(f"Hazir Hailo COCO HEF kullanilamadi, PT fallback aktif: {exc}")
            return DetasDisasterBackend(YOLO_PT_MODEL_PATH, labels)

    if backend == "hailo":
        try:
            return HailoBackend(HAILO_HEF_MODEL_PATH, labels)
        except Exception as exc:
            _model_errors["hailo"] = str(exc)
            add_log(f"Hailo HEF kullanilamadi, PT fallback aktif: {exc}")
            return DetasDisasterBackend(YOLO_PT_MODEL_PATH, labels)

    return DetasDisasterBackend(_model_path_for_backend(), labels)


def _create_person_backend():
    backend = str(PERSON_MODEL_BACKEND or "pt").lower()

    if backend == "hailo":
        try:
            return PersonHailoBackend(PERSON_HAILO_HEF_MODEL_PATH)
        except Exception as exc:
            _model_errors["person_hailo"] = str(exc)
            add_log(f"Person Hailo HEF kullanilamadi, yolov8n fallback aktif: {exc}")
            return PersonBackend(PERSON_MODEL_PATH)

    return PersonBackend(PERSON_MODEL_PATH)


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
                _create_detas_backend,
            )

        if _person_backend is None:
            _person_backend = _load_backend(
                "person",
                _create_person_backend,
            )

        backends = [backend for backend in (_detas_backend, _person_backend) if backend is not None]
        try:
            state.update(hailo=any(isinstance(backend, HailoRuntimeBackend) for backend in backends))
        except Exception:
            pass
        return backends


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


def _meters_between(lat_a, lng_a, lat_b, lng_b):
    try:
        lat_a = float(lat_a)
        lng_a = float(lng_a)
        lat_b = float(lat_b)
        lng_b = float(lng_b)
    except Exception:
        return None

    radius_m = 6371000.0
    phi_a = math.radians(lat_a)
    phi_b = math.radians(lat_b)
    d_phi = math.radians(lat_b - lat_a)
    d_lam = math.radians(lng_b - lng_a)
    hav = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi_a) * math.cos(phi_b) * math.sin(d_lam / 2) ** 2
    )
    return radius_m * 2 * math.atan2(math.sqrt(hav), math.sqrt(1 - hav))


def _average_hash_from_frame(frame, bbox=None):
    if frame is None:
        return None

    try:
        target = frame
        if bbox and len(bbox) >= 4:
            height, width = frame.shape[:2]
            x1 = max(0, min(width - 1, int(float(bbox[0]))))
            y1 = max(0, min(height - 1, int(float(bbox[1]))))
            x2 = max(0, min(width, int(float(bbox[2]))))
            y2 = max(0, min(height, int(float(bbox[3]))))
            if x2 - x1 >= 8 and y2 - y1 >= 8:
                target = frame[y1:y2, x1:x2]

        gray = cv2.cvtColor(target, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA)
        avg = float(small.mean())
        value = 0
        for pixel in small.flatten():
            value = (value << 1) | (1 if float(pixel) >= avg else 0)
        return f"{value:016x}"
    except Exception:
        return None


def _image_average_hash(jpg_bytes, bbox=None):
    return _average_hash_from_frame(_decode_jpeg(jpg_bytes), bbox)


def _hash_distance(hash_a, hash_b):
    if not hash_a or not hash_b:
        return None

    try:
        return (int(str(hash_a), 16) ^ int(str(hash_b), 16)).bit_count()
    except Exception:
        return None


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


def _is_location_image_duplicate(events, class_name, gps, image_hash, crop_hash=None):
    if not gps.get("gps_known"):
        return False

    for event in events:
        if event.get("class_name") != class_name:
            continue

        if not event.get("gps_known"):
            continue

        distance = _meters_between(gps["lat"], gps["lng"], event.get("lat"), event.get("lng"))
        if distance is None:
            continue

        if distance <= DETECTION_EVENT_GPS_EXACT_DEDUP_METERS:
            return True

        if distance > DETECTION_EVENT_GPS_NEAR_DEDUP_METERS:
            continue

        hash_distance = _hash_distance(crop_hash, event.get("crop_hash"))
        if hash_distance is None:
            hash_distance = _hash_distance(image_hash, event.get("image_hash"))

        if hash_distance is not None and hash_distance <= DETECTION_EVENT_IMAGE_HASH_MAX_DISTANCE:
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


def _register_actionable_events(detections, frame_jpg=None, hash_jpg=None):
    snapshot = state.snapshot()
    events = list(snapshot.get("detection_events") or [])
    gps = _gps_snapshot(snapshot)
    hash_frame = _decode_jpeg(hash_jpg or frame_jpg)
    image_hash = _average_hash_from_frame(hash_frame)
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

        crop_hash = _average_hash_from_frame(hash_frame, bbox) or image_hash
        if _is_location_image_duplicate(events, class_name, gps, image_hash, crop_hash):
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
            "image_hash": image_hash,
            "crop_hash": crop_hash,
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
        _register_actionable_events(detections, annotated_jpg, jpg_bytes)
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
