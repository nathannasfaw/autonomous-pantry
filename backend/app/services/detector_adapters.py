"""
Demo-optimized detector adapters for pantry scanning.

This layer is intentionally narrow: it only cares about three items for the
demo scenario:

* olive oil
* mozzarella cheese
* tomato sauce

Live scan prefers YOLO-World with a tiny prompt vocabulary.
Final review prefers Grounding DINO with the same constrained vocabulary.
Everything else is discarded to keep the scan fast and predictable.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np
from PIL import Image

from app.services import yolo_service

logger = logging.getLogger(__name__)

# Default to generic_yolo for live detection: ~100ms/frame on CPU vs ~8-9s for
# YOLO-World. At 900ms scan intervals, generic YOLO keeps boxes continuously
# visible via the tracker's sticky-frame mechanism. Set PANTRY_LIVE_DETECTOR=yolo_world
# to re-enable YOLO-World on a machine with a GPU.
LIVE_DETECTOR_BACKEND = os.environ.get("PANTRY_LIVE_DETECTOR", "generic_yolo").strip().lower()
FINAL_DETECTOR_BACKEND = os.environ.get("PANTRY_FINAL_DETECTOR", "grounding_dino").strip().lower()
YOLO_WORLD_MODEL_PATH = os.environ.get("YOLO_WORLD_MODEL_PATH", "yolov8s-world.pt")
GROUNDING_DINO_MODEL_ID = os.environ.get("GROUNDING_DINO_MODEL_ID", "IDEA-Research/grounding-dino-base")
GROUNDING_DINO_LOCAL_ONLY = os.environ.get("GROUNDING_DINO_LOCAL_ONLY", "1").strip().lower() not in {"0", "false", "no"}
GROUNDING_DINO_BOX_THRESHOLD = float(os.environ.get("GROUNDING_DINO_BOX_THRESHOLD", "0.18"))
GROUNDING_DINO_TEXT_THRESHOLD = float(os.environ.get("GROUNDING_DINO_TEXT_THRESHOLD", "0.16"))
DEMO_MAX_LIVE_CANDIDATES = int(os.environ.get("PANTRY_DEMO_MAX_LIVE_CANDIDATES", "3"))
DEMO_MAX_FINAL_CANDIDATES = int(os.environ.get("PANTRY_DEMO_MAX_FINAL_CANDIDATES", "3"))

DEMO_TARGET_ITEMS = ("olive oil", "mozzarella cheese", "tomato sauce")
TARGET_ITEM_SET = set(DEMO_TARGET_ITEMS)

# Shape-based vocabulary for live detection.
# YOLO-World is much better at distinguishing visual shapes (bottle vs jar vs bag)
# than at product-specific descriptions (all containers look like "olive oil bottle"
# to the model, causing everything to map to the first class).
# TARGET_PATTERNS below maps these shape labels to the correct demo items.
DEMO_LIVE_VOCABULARY = [
    "bottle",
    "jar",
    "plastic bag",
    "food package",
]

# Final vocabulary can be more descriptive since Grounding DINO handles it better.
DEMO_FINAL_VOCABULARY = [
    "olive oil bottle",
    "mozzarella cheese",
    "shredded cheese bag",
    "tomato sauce jar",
    "pasta sauce jar",
]

TARGET_CONFIG: dict[str, dict[str, Any]] = {
    "olive oil": {
        "unit": "bottle",
        "quantity": 1.0,
        "min_conf": 0.07,
    },
    "mozzarella cheese": {
        "unit": "package",
        "quantity": 1.0,
        "min_conf": 0.06,
    },
    "tomato sauce": {
        "unit": "jar",
        "quantity": 1.0,
        "min_conf": 0.07,
    },
}

TARGET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Exact product names (from Grounding DINO final vocabulary or Claude output)
    (re.compile(r"\bolive oil\b"), "olive oil"),
    (re.compile(r"\boil\b.*\bbottle\b|\bbottle\b.*\boil\b"), "olive oil"),
    (re.compile(r"\bmozzarella\b"), "mozzarella cheese"),
    (re.compile(r"\bshredded cheese\b"), "mozzarella cheese"),
    (re.compile(r"\bcheese package\b|\bpackaged cheese\b|\bcheese bag\b|\bcheese block\b"), "mozzarella cheese"),
    (re.compile(r"\bcheese\b"), "mozzarella cheese"),
    (re.compile(r"\btomato sauce\b"), "tomato sauce"),
    (re.compile(r"\bpasta sauce\b"), "tomato sauce"),
    (re.compile(r"\bsauce\b.*\bjar\b|\bsauce\b.*\bbottle\b"), "tomato sauce"),
    # Generic YOLO / COCO container class fallbacks.
    # COCO has no "jar" class — jars are detected as "bottle" — so these all map
    # to the same demo item.  That's intentional: the live scan is only responsible
    # for producing *boxes* at the right positions; Claude at finalize assigns the
    # correct item name.  Using "olive oil" as the catch-all provisional label keeps
    # the tracker happy without misleading the user (the frontend shows a neutral
    # "scanning…" label for all provisional boxes instead of item names).
    (re.compile(r"\bbottl(?:e|ed)(?: item)?\b"), "olive oil"),
    (re.compile(r"\bjarr?(?:ed)?(?: item)?\b"), "olive oil"),
    (re.compile(r"\bplastic bag\b|\bfood package\b|\bpackage\b"), "olive oil"),
]


def _normalize_label(text: str) -> str:
    lowered = re.sub(r"[^a-z0-9 ]", " ", str(text).lower())
    return re.sub(r"\s+", " ", lowered).strip()


def is_demo_target_item(item_name: str) -> bool:
    return str(item_name).strip().lower() in TARGET_ITEM_SET


def normalize_pantry_label(raw_label: str) -> dict[str, Any] | None:
    normalized = _normalize_label(raw_label)
    if not normalized:
        return None

    for pattern, item_name in TARGET_PATTERNS:
        if pattern.search(normalized):
            config = TARGET_CONFIG[item_name]
            return {
                "item": item_name,
                "unit": config["unit"],
                "quantity": config["quantity"],
                "verification_only": False,
                "min_conf": config["min_conf"],
            }
    return None


def _box_area_ratio(x1: float, y1: float, x2: float, y2: float, width: int, height: int) -> float:
    return yolo_service._box_area_ratio(x1, y1, x2, y2, width, height)


def _pad_box(x1: float, y1: float, x2: float, y2: float, width: int, height: int) -> tuple[float, float, float, float]:
    return yolo_service._pad_box(x1, y1, x2, y2, width, height, padding_ratio=0.15)


def _intersection_over_union(box_a: dict[str, Any], box_b: dict[str, Any]) -> float:
    return yolo_service._intersection_over_union(box_a, box_b)


def _load_image(image_b64: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(image_b64))).convert("RGB")


def _center_distance_ratio(x1: float, y1: float, x2: float, y2: float, width: int, height: int) -> float:
    center_x = ((x1 + x2) / 2.0) / max(float(width), 1.0)
    center_y = ((y1 + y2) / 2.0) / max(float(height), 1.0)
    return abs(center_x - 0.5) + abs(center_y - 0.5)


def _demo_selection_score(confidence: float, area_ratio: float, center_distance_ratio: float) -> float:
    center_bonus = max(0.0, 0.20 - min(center_distance_ratio, 0.20))
    area_bonus = min(area_ratio * 5.0, 0.22)
    return (confidence * 0.72) + area_bonus + center_bonus


def _candidate_limit_for(detector_name: str) -> int:
    return DEMO_MAX_LIVE_CANDIDATES if detector_name in {"yolo_world", "generic_yolo_fallback"} else DEMO_MAX_FINAL_CANDIDATES


def _log_detected_item(item_name: str, detector_name: str) -> None:
    if detector_name in {"yolo_world", "generic_yolo_fallback"}:
        logger.info("Detected %s (live)", item_name)
    elif detector_name == "grounding_dino":
        logger.info("Detected %s (final detector)", item_name)


def normalize_open_vocabulary_detections(
    raw_detections: list[dict[str, Any]],
    *,
    width: int,
    height: int,
    detector_name: str,
) -> dict[str, Any]:
    selected_candidates: list[dict[str, Any]] = []
    discarded: list[dict[str, Any]] = []

    for raw in raw_detections:
        raw_label = str(raw["raw_label"])
        confidence = float(raw["confidence"])
        rule = normalize_pantry_label(raw_label)
        if rule is None:
            logger.debug(
                "[%s] discard raw_label=%r conf=%.3f reason=not_demo_target",
                detector_name, raw_label, confidence,
            )
            discarded.append(
                {
                    "detector": detector_name,
                    "raw_label": raw_label,
                    "confidence": round(confidence, 4),
                    "decision": "discarded",
                    "reason": "not_demo_target",
                }
            )
            continue

        if confidence < float(rule["min_conf"]):
            discarded.append(
                {
                    "detector": detector_name,
                    "raw_label": raw_label,
                    "mapped_item": rule["item"],
                    "confidence": round(confidence, 4),
                    "decision": "discarded",
                    "reason": "below_target_threshold",
                }
            )
            continue

        x1, y1, x2, y2 = [float(value) for value in raw["xyxy"]]
        area_ratio = _box_area_ratio(x1, y1, x2, y2, width, height)
        if area_ratio < yolo_service.MIN_BOX_AREA_RATIO:
            discarded.append(
                {
                    "detector": detector_name,
                    "raw_label": raw_label,
                    "mapped_item": rule["item"],
                    "confidence": round(confidence, 4),
                    "decision": "discarded",
                    "reason": "box_too_small",
                    "area_ratio": round(area_ratio, 5),
                }
            )
            continue

        crop_x1, crop_y1, crop_x2, crop_y2 = _pad_box(x1, y1, x2, y2, width, height)
        center_ratio = _center_distance_ratio(x1, y1, x2, y2, width, height)
        selected_candidates.append(
            {
                "raw_class": raw_label,
                "label": raw_label,
                "item": rule["item"],
                "quantity": rule["quantity"],
                "unit": rule["unit"],
                "verification_only": False,
                "confidence": round(confidence, 4),
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "crop_x1": crop_x1,
                "crop_y1": crop_y1,
                "crop_x2": crop_x2,
                "crop_y2": crop_y2,
                "area_ratio": area_ratio,
                "center_ratio": center_ratio,
                "selection_score": _demo_selection_score(confidence, area_ratio, center_ratio),
                "detector": detector_name,
                "raw_label": raw_label,
            }
        )

    kept: list[dict[str, Any]] = []
    candidate_limit = _candidate_limit_for(detector_name)
    for candidate in sorted(selected_candidates, key=lambda item: item["selection_score"], reverse=True):
        overlapping = next(
            (
                existing
                for existing in kept
                if existing["item"] == candidate["item"]
                and _intersection_over_union(existing, candidate) >= 0.62
            ),
            None,
        )
        if overlapping is not None:
            discarded.append(
                {
                    "detector": detector_name,
                    "raw_label": candidate["raw_label"],
                    "mapped_item": candidate["item"],
                    "confidence": candidate["confidence"],
                    "decision": "discarded",
                    "reason": "overlapping_lower_ranked_candidate",
                }
            )
            continue

        if len(kept) >= candidate_limit:
            discarded.append(
                {
                    "detector": detector_name,
                    "raw_label": candidate["raw_label"],
                    "mapped_item": candidate["item"],
                    "confidence": candidate["confidence"],
                    "decision": "discarded",
                    "reason": "frame_candidate_limit",
                }
            )
            continue

        kept.append(candidate)
        _log_detected_item(candidate["item"], detector_name)

    items = [
        {
            "item": candidate["item"],
            "quantity": candidate["quantity"],
            "unit": candidate["unit"],
            "confidence": candidate["confidence"],
            "label": candidate["label"],
            "raw_class": candidate["raw_class"],
            "verification_only": False,
            "detector": candidate["detector"],
            "raw_label": candidate["raw_label"],
        }
        for candidate in kept
    ]
    boxes = [
        {
            "x1": round(candidate["x1"] / width, 4),
            "y1": round(candidate["y1"] / height, 4),
            "x2": round(candidate["x2"] / width, 4),
            "y2": round(candidate["y2"] / height, 4),
            "crop_x1": round(candidate["crop_x1"] / width, 4),
            "crop_y1": round(candidate["crop_y1"] / height, 4),
            "crop_x2": round(candidate["crop_x2"] / width, 4),
            "crop_y2": round(candidate["crop_y2"] / height, 4),
            "label": candidate["label"],
            "item": candidate["item"],
            "confidence": candidate["confidence"],
            "verification_only": False,
            "detector": candidate["detector"],
            "raw_label": candidate["raw_label"],
        }
        for candidate in kept
    ]
    return {
        "items": items,
        "boxes": boxes,
        "candidates": kept,
        "width": width,
        "height": height,
        "debug": {
            "detector": detector_name,
            "selected": [
                {
                    "raw_label": candidate["raw_label"],
                    "mapped_item": candidate["item"],
                    "confidence": candidate["confidence"],
                    "selection_score": round(candidate["selection_score"], 4),
                    "detector": detector_name,
                }
                for candidate in kept
            ],
            "discarded": discarded,
            "vocabulary": list(DEMO_LIVE_VOCABULARY if detector_name in {"yolo_world", "generic_yolo_fallback"} else DEMO_FINAL_VOCABULARY),
            "candidate_limit": candidate_limit,
        },
    }


class DetectorAdapter(Protocol):
    name: str

    def detect(self, image_b64: str, media_type: str = "image/jpeg") -> dict[str, Any]:
        ...


@dataclass
class AdapterStatus:
    available: bool
    reason: str | None = None


class GenericYoloFallbackAdapter:
    name = "generic_yolo_fallback"

    def detect(self, image_b64: str, media_type: str = "image/jpeg") -> dict[str, Any]:
        result = yolo_service.detect(image_b64, media_type)
        raw_detections = [
            {
                # Use raw_class (e.g. "bottle", "jar") not the remapped item name
                # ("bottled item", "jarred item") so TARGET_PATTERNS can match them.
                "raw_label": str(candidate.get("raw_class") or candidate.get("item") or ""),
                "confidence": float(candidate["confidence"]),
                "xyxy": [
                    float(candidate["x1"]),
                    float(candidate["y1"]),
                    float(candidate["x2"]),
                    float(candidate["y2"]),
                ],
            }
            for candidate in result.get("candidates", [])
        ]
        normalized = normalize_open_vocabulary_detections(
            raw_detections,
            width=int(result["width"]),
            height=int(result["height"]),
            detector_name=self.name,
        )
        normalized["debug"]["fallback"] = True
        normalized["debug"]["source_model"] = "generic_yolo"
        return normalized


class YoloWorldLiveAdapter:
    name = "yolo_world"

    def __init__(self):
        self._model = None
        self._status: AdapterStatus | None = None

    def _ensure_model(self):
        if self._status is not None and not self._status.available:
            raise RuntimeError(self._status.reason or "YOLO-World unavailable")
        if self._model is not None:
            return self._model
        try:
            from ultralytics import YOLOWorld

            # Drop the manual os.path.exists() guard — ultralytics auto-downloads
            # yolov8s-world.pt from its hub on first call when the file is absent.
            # If the download fails (no internet) the exception is still caught here
            # and the adapter marks itself unavailable, triggering the generic fallback.
            if not os.path.exists(YOLO_WORLD_MODEL_PATH):
                logger.info(
                    "YOLO-World weights not found at %s — ultralytics will attempt auto-download",
                    YOLO_WORLD_MODEL_PATH,
                )
            model = YOLOWorld(YOLO_WORLD_MODEL_PATH, verbose=False)
            model.set_classes(DEMO_LIVE_VOCABULARY)
            self._model = model
            self._status = AdapterStatus(available=True)
            logger.info("YOLO-World live detector ready: %s", YOLO_WORLD_MODEL_PATH)
            return self._model
        except Exception as exc:
            reason = str(exc)
            self._status = AdapterStatus(available=False, reason=reason)
            raise RuntimeError(reason) from exc

    def detect(self, image_b64: str, media_type: str = "image/jpeg") -> dict[str, Any]:
        del media_type
        model = self._ensure_model()
        image = _load_image(image_b64)
        width, height = image.size
        img_array = np.array(image)

        results = model(img_array, conf=min(config["min_conf"] for config in TARGET_CONFIG.values()), verbose=False)
        raw_detections: list[dict[str, Any]] = []
        names = model.names if hasattr(model, "names") else {}
        for result in results:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                raw_label = str(names[cls_id] if cls_id in names else cls_id)
                raw_detections.append(
                    {
                        "raw_label": raw_label,
                        "confidence": float(box.conf[0]),
                        "xyxy": box.xyxy[0].tolist(),
                    }
                )

        normalized = normalize_open_vocabulary_detections(
            raw_detections,
            width=width,
            height=height,
            detector_name=self.name,
        )
        normalized["debug"]["backend"] = self.name
        normalized["debug"]["model_path"] = YOLO_WORLD_MODEL_PATH
        return normalized


class GroundingDinoFinalAdapter:
    name = "grounding_dino"

    def __init__(self):
        self._processor = None
        self._model = None
        self._status: AdapterStatus | None = None

    def _ensure_model(self):
        if self._status is not None and not self._status.available:
            raise RuntimeError(self._status.reason or "Grounding DINO unavailable")
        if self._processor is not None and self._model is not None:
            return self._processor, self._model
        try:
            from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

            self._processor = AutoProcessor.from_pretrained(
                GROUNDING_DINO_MODEL_ID,
                local_files_only=GROUNDING_DINO_LOCAL_ONLY,
            )
            self._model = AutoModelForZeroShotObjectDetection.from_pretrained(
                GROUNDING_DINO_MODEL_ID,
                local_files_only=GROUNDING_DINO_LOCAL_ONLY,
            )
            self._status = AdapterStatus(available=True)
            logger.info("Grounding DINO final detector ready: %s", GROUNDING_DINO_MODEL_ID)
            return self._processor, self._model
        except Exception as exc:
            reason = str(exc)
            self._status = AdapterStatus(available=False, reason=reason)
            raise RuntimeError(reason) from exc

    def detect(self, image_b64: str, media_type: str = "image/jpeg") -> dict[str, Any]:
        del media_type
        processor, model = self._ensure_model()
        image = _load_image(image_b64)
        prompt = ". ".join(DEMO_FINAL_VOCABULARY) + "."
        inputs = processor(images=image, text=prompt, return_tensors="pt")
        outputs = model(**inputs)
        results = processor.post_process_grounded_object_detection(
            outputs,
            inputs.input_ids,
            box_threshold=GROUNDING_DINO_BOX_THRESHOLD,
            text_threshold=GROUNDING_DINO_TEXT_THRESHOLD,
            target_sizes=[image.size[::-1]],
        )
        raw_detections = []
        for box, score, label in zip(results[0]["boxes"], results[0]["scores"], results[0]["labels"], strict=False):
            raw_detections.append(
                {
                    "raw_label": str(label),
                    "confidence": float(score),
                    "xyxy": box.tolist(),
                }
            )

        normalized = normalize_open_vocabulary_detections(
            raw_detections,
            width=image.width,
            height=image.height,
            detector_name=self.name,
        )
        normalized["debug"]["backend"] = self.name
        normalized["debug"]["model_id"] = GROUNDING_DINO_MODEL_ID
        normalized["debug"]["prompt"] = prompt
        normalized["debug"]["box_threshold"] = GROUNDING_DINO_BOX_THRESHOLD
        normalized["debug"]["text_threshold"] = GROUNDING_DINO_TEXT_THRESHOLD
        return normalized


_live_yolo_world = YoloWorldLiveAdapter()
_generic_fallback = GenericYoloFallbackAdapter()
_grounding_dino = GroundingDinoFinalAdapter()


def detect_live_frame(image_b64: str, media_type: str = "image/jpeg") -> dict[str, Any]:
    if LIVE_DETECTOR_BACKEND == "yolo_world":
        try:
            result = _live_yolo_world.detect(image_b64, media_type)
            logger.info(
                "[live-detector] YOLO-World: %d items, %d boxes",
                len(result.get("items", [])),
                len(result.get("boxes", [])),
            )
            return result
        except Exception as exc:
            logger.warning("YOLO-World live detection failed, using generic fallback: %s", exc)
            fallback = _generic_fallback.detect(image_b64, media_type)
            logger.info(
                "[live-detector] generic-YOLO fallback: %d items, %d boxes (fallback_reason=%s)",
                len(fallback.get("items", [])),
                len(fallback.get("boxes", [])),
                exc,
            )
            fallback["debug"] = dict(fallback.get("debug") or {})
            fallback["debug"]["requested_detector"] = "yolo_world"
            fallback["debug"]["fallback_reason"] = str(exc)
            return fallback
    result = _generic_fallback.detect(image_b64, media_type)
    logger.info(
        "[live-detector] generic-YOLO: %d items, %d boxes",
        len(result.get("items", [])),
        len(result.get("boxes", [])),
    )
    return result


def detect_final_candidates(image_b64: str, media_type: str = "image/jpeg") -> dict[str, Any] | None:
    if FINAL_DETECTOR_BACKEND != "grounding_dino":
        return None
    try:
        return _grounding_dino.detect(image_b64, media_type)
    except Exception as exc:
        logger.warning("Grounding DINO final detection unavailable, falling back to tracked live results: %s", exc)
        return {
            "items": [],
            "boxes": [],
            "candidates": [],
            "debug": {
                "detector": "grounding_dino",
                "fallback": True,
                "fallback_reason": str(exc),
                "vocabulary": list(DEMO_FINAL_VOCABULARY),
            },
        }
