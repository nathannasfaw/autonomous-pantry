"""
Vision service: Claude Haiku crop identification.
Used as the accuracy layer on top of YOLO's speed layer.

Flow:
  1. YOLO detects bounding boxes (fast, local)
  2. Each unique new YOLO class gets its crop sent here (once per session)
  3. Claude returns the precise grocery item name
"""

import json
import logging
import os
import re

import anthropic

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


_PROMPT = """What grocery or food item is shown in this image?
YOLO (a computer vision model) detected it as '{yolo_hint}' — use that as a hint but trust what you actually see.

Return ONLY a JSON object, no explanation:
{{"item": "precise item name in lowercase", "quantity": <number>, "unit": "<count|lbs|oz|cups|bottle|bag|can|bunch|cloves|package|jar|box|loaf|head|stick|piece|tbsp|tsp>"}}

Rules:
- Be as specific as possible (e.g. "navel orange" not just "fruit")
- If multiple of the same item are visible, sum the quantity
- If this is clearly NOT a food/grocery item, return: {{"item": null}}"""


def identify_crop(crop_b64: str, yolo_hint: str) -> dict | None:
    """
    Send a cropped bounding-box image to Claude Haiku for precise identification.

    Args:
        crop_b64: Base64-encoded JPEG of the cropped region (no data URI prefix).
        yolo_hint: The YOLO class name detected in this region (e.g. 'sports ball').

    Returns:
        {item, quantity, unit} dict, or None if Claude says it's not a food item.
    """
    client = _get_client()

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": crop_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": _PROMPT.format(yolo_hint=yolo_hint),
                        },
                    ],
                }
            ],
        )

        raw = response.content[0].text.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\n?```$", "", raw)

        result = json.loads(raw)
        if not result.get("item"):
            logger.info("Claude: not a food item (yolo_hint=%r)", yolo_hint)
            return None

        identified = {
            "item": str(result["item"]).lower().strip(),
            "quantity": float(result.get("quantity", 1.0)),
            "unit": str(result.get("unit", "count")),
        }
        logger.info(
            "Claude identified %r → %r (yolo_hint=%r)",
            yolo_hint, identified["item"], yolo_hint,
        )
        return identified

    except Exception as exc:
        logger.warning("Claude crop identification failed: %s", exc)
        return None
