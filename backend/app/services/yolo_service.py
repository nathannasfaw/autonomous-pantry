"""
YOLO-based pantry detection service.

The current default model (`yolov8n-oiv7.pt`) is a general-purpose detector,
not a pantry-specialized grocery model. This module keeps the existing
pipeline intact while making the first stage more pantry-friendly through:

* pantry-specific class normalization and filtering
* per-class confidence thresholds
* one best crop candidate per raw class for Claude verification
* padded crop boxes for better downstream verification
* structured debug metadata for accepted and discarded detections
"""

from __future__ import annotations

import base64
import io
import logging
import os
import re
from typing import Any

import numpy as np
from PIL import Image
from ultralytics import YOLO

logger = logging.getLogger(__name__)

MODEL_PATH = os.environ.get("YOLO_MODEL_PATH", "yolov8n-oiv7.pt")
MODEL_CONF_THRESHOLD = float(os.environ.get("YOLO_CONF", "0.10"))
MIN_BOX_AREA_RATIO = float(os.environ.get("YOLO_MIN_BOX_AREA", "0.0025"))
DEFAULT_CROP_PADDING_RATIO = float(os.environ.get("YOLO_CROP_PADDING", "0.12"))

_model: YOLO | None = None


def get_model() -> YOLO:
    global _model
    if _model is None:
        logger.info("Loading YOLO model: %s", MODEL_PATH)
        _model = YOLO(MODEL_PATH)
        logger.info("YOLO ready - %d classes", len(_model.names))
    return _model


def _rule(
    item: str,
    unit: str,
    quantity: float,
    *,
    min_conf: float,
    verification_only: bool = False,
) -> dict[str, Any]:
    return {
        "item": item,
        "unit": unit,
        "quantity": quantity,
        "min_conf": min_conf,
        "verification_only": verification_only,
    }


_CLASS_MAP: dict[str, dict[str, Any]] = {
    # Produce
    "apple": _rule("apple", "count", 1.0, min_conf=0.18),
    "banana": _rule("banana", "count", 1.0, min_conf=0.18),
    "orange": _rule("orange", "count", 1.0, min_conf=0.18),
    "lemon": _rule("lemon", "count", 1.0, min_conf=0.18),
    "lime": _rule("lime", "count", 1.0, min_conf=0.18),
    "grapefruit": _rule("grapefruit", "count", 1.0, min_conf=0.18),
    "pineapple": _rule("pineapple", "count", 1.0, min_conf=0.20),
    "mango": _rule("mango", "count", 1.0, min_conf=0.18),
    "watermelon": _rule("watermelon", "count", 1.0, min_conf=0.20),
    "strawberry": _rule("strawberry", "count", 4.0, min_conf=0.20),
    "grape": _rule("grapes", "bunch", 1.0, min_conf=0.18),
    "peach": _rule("peach", "count", 1.0, min_conf=0.18),
    "pear": _rule("pear", "count", 1.0, min_conf=0.18),
    "plum": _rule("plum", "count", 2.0, min_conf=0.18),
    "coconut": _rule("coconut", "count", 1.0, min_conf=0.20),
    "tomato": _rule("tomato", "count", 2.0, min_conf=0.18),
    "carrot": _rule("carrot", "count", 2.0, min_conf=0.18),
    "broccoli": _rule("broccoli", "head", 1.0, min_conf=0.18),
    "onion": _rule("onion", "count", 1.0, min_conf=0.18),
    "garlic": _rule("garlic", "head", 1.0, min_conf=0.18),
    "potato": _rule("potato", "count", 2.0, min_conf=0.18),
    "sweet potato": _rule("sweet potato", "count", 1.0, min_conf=0.18),
    "cucumber": _rule("cucumber", "count", 1.0, min_conf=0.18),
    "avocado": _rule("avocado", "count", 1.0, min_conf=0.18),
    "bell pepper": _rule("bell pepper", "count", 1.0, min_conf=0.18),
    "pepper": _rule("pepper", "count", 1.0, min_conf=0.18),
    "corn": _rule("corn", "count", 1.0, min_conf=0.18),
    "mushroom": _rule("mushroom", "count", 4.0, min_conf=0.18),
    "cabbage": _rule("cabbage", "head", 1.0, min_conf=0.18),
    "lettuce": _rule("lettuce", "head", 1.0, min_conf=0.18),
    "spinach": _rule("spinach", "bag", 1.0, min_conf=0.20),
    "zucchini": _rule("zucchini", "count", 1.0, min_conf=0.18),
    "asparagus": _rule("asparagus", "bunch", 1.0, min_conf=0.18),
    "celery": _rule("celery", "bunch", 1.0, min_conf=0.18),
    "radish": _rule("radish", "count", 3.0, min_conf=0.18),
    # Dairy / proteins
    "milk": _rule("milk", "carton", 1.0, min_conf=0.22),
    "egg": _rule("eggs", "count", 2.0, min_conf=0.22),
    "cheese": _rule("cheese", "block", 1.0, min_conf=0.22),
    "butter": _rule("butter", "stick", 1.0, min_conf=0.22),
    "cream": _rule("cream", "carton", 1.0, min_conf=0.22),
    "yogurt": _rule("yogurt", "cup", 1.0, min_conf=0.22),
    "chicken": _rule("chicken", "lbs", 1.0, min_conf=0.24),
    "pork": _rule("pork", "lbs", 1.0, min_conf=0.24),
    "fish": _rule("fish", "lbs", 1.0, min_conf=0.24),
    "shrimp": _rule("shrimp", "lbs", 0.5, min_conf=0.24),
    "salmon": _rule("salmon", "lbs", 0.5, min_conf=0.24),
    "crab": _rule("crab", "count", 1.0, min_conf=0.24),
    "lobster": _rule("lobster", "count", 1.0, min_conf=0.24),
    # Pantry staples / packaged foods
    "bread": _rule("bread", "loaf", 1.0, min_conf=0.22),
    "pasta": _rule("pasta", "package", 1.0, min_conf=0.22),
    "rice": _rule("rice", "bag", 1.0, min_conf=0.22),
    "flour": _rule("flour", "bag", 1.0, min_conf=0.24),
    "olive oil": _rule("olive oil", "bottle", 1.0, min_conf=0.24),
    "tomato sauce": _rule("tomato sauce", "jar", 1.0, min_conf=0.24),
    "pizza sauce": _rule("pizza sauce", "jar", 1.0, min_conf=0.24),
    "cereal": _rule("cereal", "box", 1.0, min_conf=0.22),
    "coffee": _rule("coffee", "bag", 1.0, min_conf=0.22),
    "tea": _rule("tea", "box", 1.0, min_conf=0.22),
    "juice": _rule("juice", "bottle", 1.0, min_conf=0.22),
    # Generic containers - useful for crops, but too weak to trust without Claude.
    "bottle": _rule("bottled item", "bottle", 1.0, min_conf=0.50, verification_only=True),
    "jar": _rule("jarred item", "jar", 1.0, min_conf=0.48, verification_only=True),
    "box": _rule("boxed item", "box", 1.0, min_conf=0.48, verification_only=True),
    "tin can": _rule("canned item", "can", 1.0, min_conf=0.46, verification_only=True),
    "sports ball": _rule("round produce", "count", 1.0, min_conf=0.52, verification_only=True),
}

_PATTERN_RULES: list[tuple[re.Pattern[str], dict[str, Any]]] = [
    (re.compile(r"\bmilk\b"), _rule("milk", "carton", 1.0, min_conf=0.22)),
    (re.compile(r"\begg(s)?\b"), _rule("eggs", "count", 2.0, min_conf=0.22)),
    (re.compile(r"\bcheese\b"), _rule("cheese", "block", 1.0, min_conf=0.22)),
    (re.compile(r"\byog(?:h)?urt\b"), _rule("yogurt", "cup", 1.0, min_conf=0.22)),
    (re.compile(r"\bbread\b"), _rule("bread", "loaf", 1.0, min_conf=0.22)),
    (re.compile(r"\bpasta|noodle\b"), _rule("pasta", "package", 1.0, min_conf=0.22)),
    (re.compile(r"\brice\b"), _rule("rice", "bag", 1.0, min_conf=0.22)),
    (re.compile(r"\bflour\b"), _rule("flour", "bag", 1.0, min_conf=0.24)),
    (re.compile(r"\bolive oil|cooking oil\b"), _rule("olive oil", "bottle", 1.0, min_conf=0.24)),
    (re.compile(r"\btomato sauce|pasta sauce\b"), _rule("tomato sauce", "jar", 1.0, min_conf=0.24)),
    (re.compile(r"\bpizza sauce\b"), _rule("pizza sauce", "jar", 1.0, min_conf=0.24)),
    (re.compile(r"\bonion\b"), _rule("onion", "count", 1.0, min_conf=0.18)),
    (re.compile(r"\bgarlic\b"), _rule("garlic", "head", 1.0, min_conf=0.18)),
    (re.compile(r"\bbanana\b"), _rule("banana", "count", 1.0, min_conf=0.18)),
    (re.compile(r"\bapple\b"), _rule("apple", "count", 1.0, min_conf=0.18)),
    (re.compile(r"\bchicken\b"), _rule("chicken", "lbs", 1.0, min_conf=0.24)),
]


def _normalize_class_name(class_name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9 ]", " ", str(class_name).lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _lookup(class_name: str) -> dict[str, Any] | None:
    normalized = _normalize_class_name(class_name)
    if normalized in _CLASS_MAP:
        return dict(_CLASS_MAP[normalized])
    for pattern, rule in _PATTERN_RULES:
        if pattern.search(normalized):
            return dict(rule)
    return None


def _box_area_ratio(x1: float, y1: float, x2: float, y2: float, width: int, height: int) -> float:
    if width <= 0 or height <= 0:
        return 0.0
    box_width = max(0.0, x2 - x1)
    box_height = max(0.0, y2 - y1)
    return (box_width * box_height) / float(width * height)


def _pad_box(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    width: int,
    height: int,
    *,
    padding_ratio: float = DEFAULT_CROP_PADDING_RATIO,
) -> tuple[float, float, float, float]:
    box_width = max(0.0, x2 - x1)
    box_height = max(0.0, y2 - y1)
    pad_x = box_width * padding_ratio
    pad_y = box_height * padding_ratio
    return (
        max(0.0, x1 - pad_x),
        max(0.0, y1 - pad_y),
        min(float(width), x2 + pad_x),
        min(float(height), y2 + pad_y),
    )


def _candidate_score(confidence: float, area_ratio: float) -> float:
    return (confidence * 0.8) + min(area_ratio * 4.0, 0.2)


def _intersection_over_union(box_a: dict[str, Any], box_b: dict[str, Any]) -> float:
    ax1, ay1, ax2, ay2 = box_a["x1"], box_a["y1"], box_a["x2"], box_a["y2"]
    bx1, by1, bx2, by2 = box_b["x1"], box_b["y1"], box_b["x2"], box_b["y2"]

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    if inter_area <= 0:
        return 0.0

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union


def _build_item_payload(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "item": candidate["item"],
        "quantity": candidate["quantity"],
        "unit": candidate["unit"],
        "confidence": candidate["confidence"],
        "label": candidate["label"],
        "raw_class": candidate["raw_class"],
        "verification_only": candidate["verification_only"],
    }


def _build_box_payload(candidate: dict[str, Any], width: int, height: int) -> dict[str, Any]:
    return {
        "x1": round(candidate["x1"] / width, 4),
        "y1": round(candidate["y1"] / height, 4),
        "x2": round(candidate["x2"] / width, 4),
        "y2": round(candidate["y2"] / height, 4),
        "crop_x1": round(candidate["crop_x1"] / width, 4),
        "crop_y1": round(candidate["crop_y1"] / height, 4),
        "crop_x2": round(candidate["crop_x2"] / width, 4),
        "crop_y2": round(candidate["crop_y2"] / height, 4),
        "label": candidate["label"],
        "raw_class": candidate["raw_class"],
        "item": candidate["item"],
        "confidence": candidate["confidence"],
        "verification_only": candidate["verification_only"],
        "crop_padding_ratio": round(DEFAULT_CROP_PADDING_RATIO, 3),
        "box_width": round(candidate["x2"] - candidate["x1"], 1),
        "box_height": round(candidate["y2"] - candidate["y1"], 1),
        "area_ratio": round(candidate["area_ratio"], 5),
        "selection_score": round(candidate["selection_score"], 4),
    }


def _build_debug_entry(
    *,
    raw_class: str,
    normalized_class: str,
    mapped_item: str | None,
    confidence: float,
    decision: str,
    reason: str | None = None,
    area_ratio: float | None = None,
    verification_only: bool | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "raw_class": raw_class,
        "normalized_class": normalized_class,
        "mapped_item": mapped_item,
        "confidence": round(confidence, 4),
        "decision": decision,
    }
    if reason:
        entry["reason"] = reason
    if area_ratio is not None:
        entry["area_ratio"] = round(area_ratio, 5)
    if verification_only is not None:
        entry["verification_only"] = verification_only
    return entry


def process_detections(raw_detections: list[dict[str, Any]], width: int, height: int) -> dict[str, Any]:
    """
    Convert raw model detections into pantry-friendly items and crop candidates.

    Separated from model execution so unit tests can exercise mapping,
    thresholding, deduping, and crop padding without loading the model.
    """
    accepted_candidates: list[dict[str, Any]] = []
    debug_discarded: list[dict[str, Any]] = []

    for detection in raw_detections:
        raw_class = str(detection["raw_class"])
        normalized_class = _normalize_class_name(raw_class)
        confidence = float(detection["confidence"])
        x1, y1, x2, y2 = [float(value) for value in detection["xyxy"]]

        rule = _lookup(raw_class)
        if rule is None:
            debug_discarded.append(
                _build_debug_entry(
                    raw_class=raw_class,
                    normalized_class=normalized_class,
                    mapped_item=None,
                    confidence=confidence,
                    decision="discarded",
                    reason="unsupported_class",
                )
            )
            continue

        area_ratio = _box_area_ratio(x1, y1, x2, y2, width, height)
        if area_ratio < MIN_BOX_AREA_RATIO:
            debug_discarded.append(
                _build_debug_entry(
                    raw_class=raw_class,
                    normalized_class=normalized_class,
                    mapped_item=rule["item"],
                    confidence=confidence,
                    decision="discarded",
                    reason="box_too_small",
                    area_ratio=area_ratio,
                    verification_only=bool(rule["verification_only"]),
                )
            )
            continue

        if confidence < float(rule["min_conf"]):
            debug_discarded.append(
                _build_debug_entry(
                    raw_class=raw_class,
                    normalized_class=normalized_class,
                    mapped_item=rule["item"],
                    confidence=confidence,
                    decision="discarded",
                    reason="below_class_threshold",
                    area_ratio=area_ratio,
                    verification_only=bool(rule["verification_only"]),
                )
            )
            continue

        crop_x1, crop_y1, crop_x2, crop_y2 = _pad_box(x1, y1, x2, y2, width, height)
        candidate = {
            "raw_class": raw_class,
            "normalized_class": normalized_class,
            "item": rule["item"],
            "quantity": rule["quantity"],
            "unit": rule["unit"],
            "confidence": round(confidence, 4),
            "verification_only": bool(rule["verification_only"]),
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "crop_x1": crop_x1,
            "crop_y1": crop_y1,
            "crop_x2": crop_x2,
            "crop_y2": crop_y2,
            "area_ratio": area_ratio,
            "selection_score": _candidate_score(confidence, area_ratio),
        }
        accepted_candidates.append(candidate)

    selected_candidates: list[dict[str, Any]] = []
    debug_selected: list[dict[str, Any]] = []

    overlap_threshold = 0.65
    for candidate in sorted(accepted_candidates, key=lambda item: item["selection_score"], reverse=True):
        overlapping = next(
            (
                chosen
                for chosen in selected_candidates
                if (
                    chosen["item"] == candidate["item"]
                    or chosen["raw_class"] == candidate["raw_class"]
                )
                and _intersection_over_union(chosen, candidate) >= overlap_threshold
            ),
            None,
        )
        if overlapping is not None:
            debug_discarded.append(
                _build_debug_entry(
                    raw_class=candidate["raw_class"],
                    normalized_class=candidate["normalized_class"],
                    mapped_item=candidate["item"],
                    confidence=candidate["confidence"],
                    decision="discarded",
                    reason="overlapping_lower_ranked_candidate",
                    area_ratio=candidate["area_ratio"],
                    verification_only=candidate["verification_only"],
                )
            )
            continue

        selected_candidates.append(candidate)
        debug_selected.append(
            _build_debug_entry(
                raw_class=candidate["raw_class"],
                normalized_class=candidate["normalized_class"],
                mapped_item=candidate["item"],
                confidence=candidate["confidence"],
                decision="selected",
                area_ratio=candidate["area_ratio"],
                verification_only=candidate["verification_only"],
            )
        )

    boxes_out: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    raw_class_counts: dict[str, int] = {}

    for candidate in selected_candidates:
        raw_class = candidate["raw_class"]
        occurrence = raw_class_counts.get(raw_class, 0) + 1
        raw_class_counts[raw_class] = occurrence
        candidate["label"] = raw_class if occurrence == 1 else f"{raw_class} #{occurrence}"
        boxes_out.append(_build_box_payload(candidate, width, height))
        items.append(_build_item_payload(candidate))

    debug = {
        "model_path": MODEL_PATH,
        "model_conf_threshold": MODEL_CONF_THRESHOLD,
        "min_box_area_ratio": MIN_BOX_AREA_RATIO,
        "overlap_threshold": overlap_threshold,
        "selected": debug_selected,
        "discarded": debug_discarded,
    }

    logger.info(
        "YOLO result: %d pantry items, %d crop boxes, %d discarded candidates (model=%s, conf=%.2f)",
        len(items),
        len(boxes_out),
        len(debug_discarded),
        MODEL_PATH,
        MODEL_CONF_THRESHOLD,
    )
    return {
        "items": items,
        "boxes": boxes_out,
        "candidates": selected_candidates,
        "width": width,
        "height": height,
        "debug": debug,
    }


def detect(image_b64: str, media_type: str = "image/jpeg") -> dict[str, Any]:
    """
    Run YOLO on a base64-encoded image frame and post-process detections for pantry use.
    """
    del media_type  # kept for API compatibility

    model = get_model()

    img_bytes = base64.b64decode(image_b64)
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    width, height = img.size
    img_array = np.array(img)

    results = model(img_array, conf=MODEL_CONF_THRESHOLD, verbose=False)

    raw_detections: list[dict[str, Any]] = []
    for result in results:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            raw_class = str(model.names[cls_id])
            confidence = round(float(box.conf[0]), 4)
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            raw_detections.append(
                {
                    "raw_class": raw_class,
                    "confidence": confidence,
                    "xyxy": [x1, y1, x2, y2],
                }
            )
            logger.debug("YOLO raw detection: class=%r conf=%.3f box=%s", raw_class, confidence, [x1, y1, x2, y2])

    return process_detections(raw_detections, width, height)
