import json
import threading
from io import BytesIO
from pathlib import Path

from PIL import Image

from config.settings import settings
from models.ml_models import MLTask

# Lazy imports for heavy ML libs — loaded on first use to reduce startup memory
_torch = None
_cv2 = None
_np = None
_transforms = None
_efficientnet_b0 = None
_YOLO = None
_SKIN_TRANSFORM = None


def _ensure_ml_imports():
    global _torch, _cv2, _np, _transforms, _efficientnet_b0, _YOLO, _SKIN_TRANSFORM
    if _torch is not None:
        return
    import torch as _t
    import cv2 as _c
    import numpy as _n
    from torchvision import transforms as _tr
    from torchvision.models import efficientnet_b0 as _eb0
    from ultralytics import YOLO as _Y

    _torch = _t
    _cv2 = _c
    _np = _n
    _transforms = _tr
    _efficientnet_b0 = _eb0
    _YOLO = _Y
    _SKIN_TRANSFORM = _tr.Compose(
        [
            _tr.Resize(256),
            _tr.CenterCrop(224),
            _tr.ToTensor(),
            _tr.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )


class MLServiceError(RuntimeError):
    pass


_MODEL_LOCK = threading.Lock()
_MODEL_CACHE: dict[str, object] = {}
_LABELS_CACHE: dict[str, list[str]] = {}

_DEFAULT_SKIN_CLASS_MAP = {
    0: "acne",
    1: "eczema",
    2: "psoriasis",
    3: "dermatitis",
    4: "fungal infection",
    5: "bacterial skin infection",
    6: "skin lesion",
    7: "benign skin finding",
}

_MODEL_DIR = Path(settings.models_directory)

_MODEL_CONFIG = {
    "fracture": {
        "type": "yolo",
        "path": lambda: _resolve_model_path("fracture", settings.yolo_fracture_model_path),
        "model_name": "YOLOv8 Fracture",
    },
    "tumor": {
        "type": "yolo",
        "path": lambda: _resolve_model_path("tumor", settings.yolo_tumor_model_path),
        "model_name": "YOLOv8 Tumor",
    },
    "kidney_stone": {
        "type": "yolo",
        "path": lambda: _resolve_model_path("kidney_stone", settings.yolo_kidney_stone_model_path),
        "model_name": "YOLOv8 Kidney Stone",
    },
    "skin_classification": {
        "type": "classifier",
        "path": lambda: _resolve_model_path("skin", settings.efficientnet_model_path),
        "labels": lambda: settings.efficientnet_labels_path,
        "model_name": "EfficientNet Skin Classifier",
    },
    "image_type_classification": {
        "type": "classifier",
        "path": lambda: settings.mobilenet_model_path,
        "labels": lambda: settings.mobilenet_labels_path,
        "model_name": "MobileNet Image Type Classifier",
    },
}


def _pt_files() -> list[Path]:
    if not _MODEL_DIR.exists() or not _MODEL_DIR.is_dir():
        return []
    return list(_MODEL_DIR.glob("*.pt"))


def _resolve_model_path(tag: str, configured_path: str) -> str:
    if configured_path and Path(configured_path).exists():
        return configured_path

    tag_lookup = {
        "fracture": ["fracture"],
        "tumor": ["tumor", "brain"],
        "kidney_stone": ["kidney", "stone"],
        "skin": ["skin"],
        "image_type": ["image", "type"],
    }
    keywords = tag_lookup.get(tag, [tag])

    for model_file in _pt_files():
        name = model_file.name.lower()
        if tag == "kidney_stone":
            if "kidney" in name or "stone" in name:
                return str(model_file)
        elif tag == "tumor":
            if "tumor" in name or "brain" in name:
                return str(model_file)
        elif all(keyword in name for keyword in keywords):
            return str(model_file)

    if tag == "skin":
        default_skin = _MODEL_DIR / "skin_model.pt"
        if default_skin.exists():
            return str(default_skin)

    return configured_path or ""


def _load_labels(path: str) -> list[str]:
    if not path:
        return []

    if path in _LABELS_CACHE:
        return _LABELS_CACHE[path]

    if not Path(path).exists():
        return []

    with Path(path).open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        labels = [str(item) for item in data]
    elif isinstance(data, dict):
        labels = [str(data[key]) for key in sorted(data.keys(), key=lambda key: int(key) if str(key).isdigit() else str(key))]
    else:
        labels = []

    _LABELS_CACHE[path] = labels
    return labels


def _prepare_state_dict(state: dict) -> dict:
    cleaned: dict = {}
    for key, value in state.items():
        normalized_key = key[7:] if key.startswith("module.") else key
        cleaned[normalized_key] = value
    return cleaned


def _normalize_prediction_label(task: MLTask, label: str, class_index: int | None = None) -> str:
    text = str(label or "").strip().lower().replace("_", " ")
    text = " ".join(text.split())

    if task == "skin_classification":
        if text.startswith("class") and class_index is not None:
            return _DEFAULT_SKIN_CLASS_MAP.get(class_index, "skin condition")
        if text in {"unknown", "unknown condition", "unknown_condition", ""}:
            return "skin condition"
        return text

    if task == "kidney_stone" and "stone" in text:
        return "kidney stone"
    if task == "fracture" and "fracture" in text:
        return "fracture"
    if task == "tumor" and ("tumor" in text or "mass" in text or "lesion" in text):
        return "tumor"

    if text in {"unknown", "unknown condition", "unknown_condition", "unclear", "indeterminate", ""}:
        return "unknown_condition"

    return text or "unknown condition"


def _is_unknown_label(label: str | None) -> bool:
    normalized = str(label or "").strip().lower().replace("_", " ")
    return normalized in {
        "",
        "unknown",
        "unknown condition",
        "unknown class",
        "indeterminate",
        "unclear",
        "class 0",
        "class 1",
        "class 2",
    }


def _load_skin_model(path: str):
    _ensure_ml_imports()
    try:
        scripted = _torch.jit.load(path, map_location="cpu")
        scripted.eval()
        return scripted
    except Exception:
        pass

    raw = _torch.load(path, map_location="cpu")
    state_dict = raw.get("state_dict", raw) if isinstance(raw, dict) else raw
    if not isinstance(state_dict, dict):
        raise MLServiceError("skin_model.pt is not a valid state_dict or TorchScript model")

    state_dict = _prepare_state_dict(state_dict)
    classifier_weight = state_dict.get("classifier.1.weight")
    if classifier_weight is None:
        raise MLServiceError("Unable to infer class count from skin_model.pt")

    num_classes = int(classifier_weight.shape[0])
    model = _efficientnet_b0(weights=None)
    in_features = model.classifier[1].in_features
    model.classifier[1] = _torch.nn.Linear(in_features, num_classes)
    model.load_state_dict(state_dict, strict=False)
    model.eval()
    return model


def _resolve_model(task: MLTask):
    config = _MODEL_CONFIG.get(task)
    if config is None:
        raise MLServiceError(f"Unsupported ML task: {task}")

    model_path = config["path"]()
    if not model_path:
        raise MLServiceError(f"Model path is not configured for task '{task}'")

    if not Path(model_path).exists():
        raise MLServiceError(f"Model file not found for task '{task}': {model_path}")

    with _MODEL_LOCK:
        cached = _MODEL_CACHE.get(task)
        if cached is not None:
            return cached, config

        _ensure_ml_imports()
        if config["type"] == "yolo":
            model = _YOLO(model_path)
        elif task == "skin_classification":
            model = _load_skin_model(model_path)
        else:
            model = _torch.jit.load(model_path, map_location="cpu")
            model.eval()

        _MODEL_CACHE[task] = model
        return model, config


def _standard_response(
    task: MLTask,
    model_name: str,
    model_type: str,
    predictions: list[dict] | None = None,
    error: str | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "success": error is None,
        "task": task,
        "model_name": model_name,
        "model_type": model_type,
        "predictions": predictions or [],
        "metadata": metadata or {},
        "error": error,
    }


def build_error_response(task: MLTask, error: str) -> dict:
    config = _MODEL_CONFIG.get(task)
    if config is None:
        return {
            "success": False,
            "task": task,
            "model_name": "Unknown",
            "model_type": "classifier",
            "predictions": [],
            "metadata": {},
            "error": error,
        }

    return _standard_response(
        task,
        config["model_name"],
        config["type"],
        predictions=[],
        metadata={},
        error=error,
    )


def _run_yolo_inference(model, task: MLTask, image: Image.Image, confidence: float) -> dict:
    _ensure_ml_imports()
    with _torch.inference_mode():
        results = model.predict(source=image, conf=confidence, device="cpu", verbose=False)

    if not results:
        config = _MODEL_CONFIG[task]
        return _standard_response(task, config["model_name"], "yolo", predictions=[])

    result = results[0]
    names = getattr(result, "names", {}) or {}
    boxes = getattr(result, "boxes", None)

    predictions: list[dict] = []
    if boxes is not None and hasattr(boxes, "cls") and hasattr(boxes, "conf") and hasattr(boxes, "xyxy"):
        classes = boxes.cls.tolist() if boxes.cls is not None else []
        confidences = boxes.conf.tolist() if boxes.conf is not None else []
        coordinates = boxes.xyxy.tolist() if boxes.xyxy is not None else []

        for index, cls_id in enumerate(classes):
            class_int = int(cls_id)
            label = names.get(class_int, str(class_int)) if isinstance(names, dict) else str(class_int)
            label = _normalize_prediction_label(task, str(label), class_int)
            conf = float(confidences[index]) if index < len(confidences) else 0.0
            bbox = [float(value) for value in coordinates[index]] if index < len(coordinates) else None
            predictions.append(
                {
                    "label": str(label),
                    "confidence": conf,
                    "bbox": bbox,
                }
            )

    config = _MODEL_CONFIG[task]
    return _standard_response(
        task,
        config["model_name"],
        "yolo",
        predictions=predictions,
        metadata={"num_detections": len(predictions)},
    )


def _image_to_tensor(image: Image.Image):
    _ensure_ml_imports()
    return _SKIN_TRANSFORM(image.convert("RGB")).unsqueeze(0)


def _run_classifier_inference(model, task: MLTask, image: Image.Image, top_k: int) -> dict:
    input_tensor = _image_to_tensor(image)

    _ensure_ml_imports()
    with _torch.inference_mode():
        outputs = model(input_tensor)

    if isinstance(outputs, (list, tuple)):
        outputs = outputs[0]

    if outputs.dim() == 1:
        outputs = outputs.unsqueeze(0)

    probabilities = _torch.softmax(outputs, dim=1)[0]
    total_classes = int(probabilities.shape[0])
    resolved_top_k = max(1, min(top_k, total_classes))

    confidence_values, class_indices = _torch.topk(probabilities, k=resolved_top_k)
    config = _MODEL_CONFIG[task]
    labels_path = config.get("labels", lambda: "")()
    labels = _load_labels(labels_path)

    predictions: list[dict] = []
    width, height = image.size
    estimated_bbox = [float(width * 0.2), float(height * 0.2), float(width * 0.8), float(height * 0.8)]
    for confidence, class_index in zip(confidence_values.tolist(), class_indices.tolist()):
        index_int = int(class_index)
        label = labels[index_int] if labels and index_int < len(labels) else f"class_{index_int}"
        label = _normalize_prediction_label(task, str(label), index_int)
        predictions.append(
            {
                "label": label,
                "confidence": float(confidence),
                "bbox": estimated_bbox,
                "is_estimated": True,
            }
        )

    return _standard_response(
        task,
        config["model_name"],
        "classifier",
        predictions=predictions,
        metadata={"top_k": resolved_top_k, "num_classes": total_classes, "image_width": width, "image_height": height},
    )


def run_ml_inference(task: MLTask, image_bytes: bytes, confidence: float | None = None, top_k: int | None = None) -> dict:
    model, config = _resolve_model(task)
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    threshold = confidence if confidence is not None else settings.ml_default_confidence
    resolved_top_k = top_k if top_k is not None else settings.ml_default_top_k

    if config["type"] == "yolo":
        result = _run_yolo_inference(model, task, image, threshold)
        result["metadata"] = {
            **(result.get("metadata") or {}),
            "image_width": image.size[0],
            "image_height": image.size[1],
        }
        return result

    return _run_classifier_inference(model, task, image, resolved_top_k)


def get_model_load_status() -> dict:
    status: dict[str, dict] = {}
    for task, config in _MODEL_CONFIG.items():
        path = config["path"]()
        status[task] = {
            "model_name": config["model_name"],
            "model_type": config["type"],
            "configured": bool(path),
            "path_exists": bool(path and Path(path).exists()),
            "loaded": task in _MODEL_CACHE,
        }
    return status


def detect_image_color_mode(image_bytes: bytes) -> str:
    _ensure_ml_imports()
    np_buffer = _np.frombuffer(image_bytes, dtype=_np.uint8)
    decoded = _cv2.imdecode(np_buffer, _cv2.IMREAD_UNCHANGED)
    if decoded is None:
        raise MLServiceError("Unable to decode image with OpenCV")

    if len(decoded.shape) == 2:
        return "grayscale"

    if len(decoded.shape) == 3 and decoded.shape[2] == 1:
        return "grayscale"

    if len(decoded.shape) == 3 and decoded.shape[2] >= 3:
        b = decoded[:, :, 0].astype(_np.float32)
        g = decoded[:, :, 1].astype(_np.float32)
        r = decoded[:, :, 2].astype(_np.float32)
        diff_score = float(_np.mean(_np.abs(r - g) + _np.abs(g - b) + _np.abs(r - b)))
        if diff_score < 8.0:
            return "grayscale"
        return "color"

    return "color"


def _best_prediction(ml_result: dict) -> dict | None:
    predictions = ml_result.get("predictions", []) or []
    if not predictions:
        return None
    return max(predictions, key=lambda item: float(item.get("confidence", 0.0)))


def _is_skin_symptom_hint(symptoms_hint: str | None) -> bool:
    text = str(symptoms_hint or "").strip().lower()
    if not text:
        return False

    skin_keywords = {
        "skin",
        "rash",
        "itch",
        "itching",
        "eczema",
        "psoriasis",
        "acne",
        "dermatitis",
        "lesion",
        "blister",
        "pimple",
        "hives",
        "fungal",
        "redness",
    }
    return any(keyword in text for keyword in skin_keywords)


def run_routed_image_analysis(image_bytes: bytes, symptoms_hint: str | None = None) -> dict:
    mode = detect_image_color_mode(image_bytes)
    force_skin_route = _is_skin_symptom_hint(symptoms_hint)

    if force_skin_route:
        skin_result = run_ml_inference("skin_classification", image_bytes)
        skin_pred = _best_prediction(skin_result)
        skin_score = float((skin_pred or {}).get("confidence", 0.0))
        return {
            "mode": mode,
            "task": "skin_classification",
            "condition": str((skin_pred or {}).get("label", "skin condition")),
            "confidence": skin_score,
            "raw": skin_result,
            "notes": "Routed to skin classifier due to skin-related symptom hints.",
        }

    if mode == "grayscale":
        tasks: list[MLTask] = ["fracture", "tumor", "kidney_stone"]
        candidates: list[dict] = []

        for task in tasks:
            try:
                result = run_ml_inference(task, image_bytes)
            except Exception as exc:
                result = build_error_response(task, str(exc))
            best = _best_prediction(result)
            score = float(best.get("confidence", 0.0)) if best else 0.0
            label = str((best or {}).get("label", "unknown_condition"))
            candidates.append(
                {
                    "task": task,
                    "score": score,
                    "label": label,
                    "is_unknown": _is_unknown_label(label),
                    "result": result,
                }
            )

        candidates.sort(key=lambda item: (0 if item["is_unknown"] else 1, item["score"]), reverse=True)
        best_choice = candidates[0]
        best_task = str(best_choice["task"])
        best_score = float(best_choice["score"])
        best_result = best_choice["result"]
        best_pred = _best_prediction(best_result)

        if best_score < 0.55:
            skin_result = run_ml_inference("skin_classification", image_bytes)
            skin_pred = _best_prediction(skin_result)
            skin_score = float((skin_pred or {}).get("confidence", 0.0))
            if skin_score >= best_score:
                return {
                    "mode": "grayscale",
                    "task": "skin_classification",
                    "condition": str((skin_pred or {}).get("label", "skin condition")),
                    "confidence": skin_score,
                    "raw": skin_result,
                    "notes": "Grayscale route had low confidence; switched to skin classifier fallback.",
                }

        return {
            "mode": "grayscale",
            "task": best_task,
            "condition": str((best_pred or {}).get("label", "unknown_condition")),
            "confidence": best_score,
            "raw": best_result,
            "notes": "Routed to radiology set (fracture, tumor, kidney stone) because image appears grayscale.",
        }

    skin_result = run_ml_inference("skin_classification", image_bytes)
    skin_pred = _best_prediction(skin_result)
    skin_score = float((skin_pred or {}).get("confidence", 0.0))

    return {
        "mode": "color",
        "task": "skin_classification",
        "condition": str((skin_pred or {}).get("label", "unknown_condition")),
        "confidence": skin_score,
        "raw": skin_result,
        "notes": "Routed to EfficientNet skin model because image appears color.",
    }
