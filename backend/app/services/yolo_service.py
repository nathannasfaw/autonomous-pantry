"""
YOLO-based pantry detection service.

Default model: yolov8n-oiv7.pt (Open Images V7, 601 classes — better food coverage).
Override with YOLO_MODEL_PATH env var to use a custom grocery/food model.
Override confidence threshold with YOLO_CONF env var (default 0.35).

First run auto-downloads the model weights via ultralytics (~12 MB for nano).
"""

import base64
import io
import logging
import os

import numpy as np
from PIL import Image
from ultralytics import YOLO

logger = logging.getLogger(__name__)

MODEL_PATH = os.environ.get("YOLO_MODEL_PATH", "yolov8n-oiv7.pt")
CONF_THRESHOLD = float(os.environ.get("YOLO_CONF", "0.20"))

_model: YOLO | None = None


def get_model() -> YOLO:
    global _model
    if _model is None:
        logger.info("Loading YOLO model: %s", MODEL_PATH)
        _model = YOLO(MODEL_PATH)
        logger.info("YOLO ready — %d classes", len(_model.names))
    return _model


# ── class name → pantry item metadata ────────────────────────────────────────
# Keys are OIV7 class names (title-case). A lowercase fallback handles COCO.

_CLASS_MAP: dict[str, dict] = {
    # Produce
    "Apple": {"item": "apple", "unit": "count", "quantity": 1.0},
    "Banana": {"item": "banana", "unit": "count", "quantity": 1.0},
    "Orange": {"item": "orange", "unit": "count", "quantity": 1.0},
    "Lemon": {"item": "lemon", "unit": "count", "quantity": 1.0},
    "Lime": {"item": "lime", "unit": "count", "quantity": 1.0},
    "Grapefruit": {"item": "grapefruit", "unit": "count", "quantity": 1.0},
    "Pineapple": {"item": "pineapple", "unit": "count", "quantity": 1.0},
    "Mango": {"item": "mango", "unit": "count", "quantity": 1.0},
    "Watermelon": {"item": "watermelon", "unit": "count", "quantity": 1.0},
    "Strawberry": {"item": "strawberry", "unit": "count", "quantity": 4.0},
    "Grape": {"item": "grapes", "unit": "bunch", "quantity": 1.0},
    "Peach": {"item": "peach", "unit": "count", "quantity": 1.0},
    "Pear": {"item": "pear", "unit": "count", "quantity": 1.0},
    "Plum": {"item": "plum", "unit": "count", "quantity": 2.0},
    "Coconut": {"item": "coconut", "unit": "count", "quantity": 1.0},
    "Tomato": {"item": "tomato", "unit": "count", "quantity": 2.0},
    "Carrot": {"item": "carrot", "unit": "count", "quantity": 2.0},
    "Broccoli": {"item": "broccoli", "unit": "head", "quantity": 1.0},
    "Onion": {"item": "onion", "unit": "count", "quantity": 1.0},
    "Garlic": {"item": "garlic", "unit": "head", "quantity": 1.0},
    "Potato": {"item": "potato", "unit": "count", "quantity": 2.0},
    "Sweet potato": {"item": "sweet potato", "unit": "count", "quantity": 1.0},
    "Cucumber": {"item": "cucumber", "unit": "count", "quantity": 1.0},
    "Avocado": {"item": "avocado", "unit": "count", "quantity": 1.0},
    "Bell pepper": {"item": "bell pepper", "unit": "count", "quantity": 1.0},
    "Pepper": {"item": "pepper", "unit": "count", "quantity": 1.0},
    "Corn": {"item": "corn", "unit": "count", "quantity": 1.0},
    "Mushroom": {"item": "mushroom", "unit": "count", "quantity": 4.0},
    "Cabbage": {"item": "cabbage", "unit": "head", "quantity": 1.0},
    "Lettuce": {"item": "lettuce", "unit": "head", "quantity": 1.0},
    "Spinach": {"item": "spinach", "unit": "bag", "quantity": 1.0},
    "Zucchini": {"item": "zucchini", "unit": "count", "quantity": 1.0},
    "Asparagus": {"item": "asparagus", "unit": "bunch", "quantity": 1.0},
    "Celery": {"item": "celery", "unit": "bunch", "quantity": 1.0},
    "Radish": {"item": "radish", "unit": "count", "quantity": 3.0},
    # Dairy & eggs
    "Milk": {"item": "milk", "unit": "bottle", "quantity": 1.0},
    "Egg": {"item": "eggs", "unit": "count", "quantity": 2.0},
    "Cheese": {"item": "cheese", "unit": "block", "quantity": 1.0},
    "Butter": {"item": "butter", "unit": "stick", "quantity": 1.0},
    "Cream": {"item": "cream", "unit": "bottle", "quantity": 1.0},
    "Yogurt": {"item": "yogurt", "unit": "cup", "quantity": 1.0},
    # Pantry / packaged
    "Bread": {"item": "bread", "unit": "loaf", "quantity": 1.0},
    "Pasta": {"item": "pasta", "unit": "package", "quantity": 1.0},
    "Rice": {"item": "rice", "unit": "bag", "quantity": 1.0},
    "Cereal": {"item": "cereal", "unit": "box", "quantity": 1.0},
    "Coffee": {"item": "coffee", "unit": "bag", "quantity": 1.0},
    "Tea": {"item": "tea", "unit": "box", "quantity": 1.0},
    "Juice": {"item": "juice", "unit": "bottle", "quantity": 1.0},
    "Bottle": {"item": "bottle", "unit": "bottle", "quantity": 1.0},
    "Tin can": {"item": "canned goods", "unit": "can", "quantity": 1.0},
    "Jar": {"item": "jar", "unit": "jar", "quantity": 1.0},
    "Box": {"item": "box", "unit": "box", "quantity": 1.0},
    # Meat & seafood
    "Chicken": {"item": "chicken", "unit": "lbs", "quantity": 1.0},
    "Pork": {"item": "pork", "unit": "lbs", "quantity": 1.0},
    "Fish": {"item": "fish", "unit": "lbs", "quantity": 1.0},
    "Shrimp": {"item": "shrimp", "unit": "lbs", "quantity": 0.5},
    "Salmon": {"item": "salmon", "unit": "lbs", "quantity": 0.5},
    "Crab": {"item": "crab", "unit": "count", "quantity": 1.0},
    "Lobster": {"item": "lobster", "unit": "count", "quantity": 1.0},
    # COCO fallbacks (lowercase)
    "banana": {"item": "banana", "unit": "count", "quantity": 1.0},
    "apple": {"item": "apple", "unit": "count", "quantity": 1.0},
    "orange": {"item": "orange", "unit": "count", "quantity": 1.0},
    "broccoli": {"item": "broccoli", "unit": "head", "quantity": 1.0},
    "carrot": {"item": "carrot", "unit": "count", "quantity": 2.0},
    "bottle": {"item": "bottle", "unit": "bottle", "quantity": 1.0},
    "sandwich": {"item": "sandwich", "unit": "count", "quantity": 1.0},
    # COCO misidentifies round citrus fruits as sports ball — map it
    "sports ball": {"item": "orange", "unit": "count", "quantity": 1.0},
}

# Build a case-insensitive lookup once
_LOWER_MAP: dict[str, dict] = {k.lower(): v for k, v in _CLASS_MAP.items()}


def _lookup(class_name: str) -> dict | None:
    return _CLASS_MAP.get(class_name) or _LOWER_MAP.get(class_name.lower())


# ── public API ────────────────────────────────────────────────────────────────

def detect(image_b64: str, media_type: str = "image/jpeg") -> dict:
    """
    Run YOLO on a base64-encoded image frame.

    Returns:
        {
          "items":  [ {item, quantity, unit, confidence}, ... ],   # deduplicated
          "boxes":  [ {x1, y1, x2, y2, label, item, confidence}, ... ],  # normalised 0-1
          "width":  int,
          "height": int,
        }
    """
    model = get_model()

    img_bytes = base64.b64decode(image_b64)
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    width, height = img.size
    img_array = np.array(img)

    results = model(img_array, conf=CONF_THRESHOLD, verbose=False)

    best: dict[str, dict] = {}   # item_name → best detection so far
    boxes_out: list[dict] = []

    for result in results:
        iw, ih = result.orig_shape[1], result.orig_shape[0]

        # Log every raw detection so we can see exact class names YOLO uses
        for box in result.boxes:
            cls_id = int(box.cls[0])
            cls_name = model.names[cls_id]
            conf = round(float(box.conf[0]), 3)
            logger.info("  RAW detection: class=%r  conf=%.3f", cls_name, conf)

        for box in result.boxes:
            cls_id = int(box.cls[0])
            cls_name = model.names[cls_id]
            conf = round(float(box.conf[0]), 3)

            meta = _lookup(cls_name)

            if meta is None:
                continue   # not a pantry item — skip

            x1, y1, x2, y2 = box.xyxy[0].tolist()
            boxes_out.append({
                "x1": round(x1 / iw, 4),
                "y1": round(y1 / ih, 4),
                "x2": round(x2 / iw, 4),
                "y2": round(y2 / ih, 4),
                "label": cls_name,
                "item": meta["item"],
                "confidence": conf,
            })

            item_name = meta["item"]
            if item_name not in best or conf > best[item_name]["confidence"]:
                best[item_name] = {
                    "item": item_name,
                    "quantity": meta["quantity"],
                    "unit": meta["unit"],
                    "confidence": conf,
                }

    items = list(best.values())
    logger.info(
        "YOLO result: %d unique items, %d boxes (conf threshold=%.2f)",
        len(items), len(boxes_out), CONF_THRESHOLD,
    )
    return {"items": items, "boxes": boxes_out, "width": width, "height": height}
