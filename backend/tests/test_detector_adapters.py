from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services import detector_adapters as da


class TestDetectorNormalization(unittest.TestCase):
    def test_oil_bottle_normalizes_to_olive_oil(self):
        rule = da.normalize_pantry_label("Oil Bottle")
        self.assertIsNotNone(rule)
        self.assertEqual(rule["item"], "olive oil")
        self.assertEqual(rule["unit"], "bottle")

    def test_cheese_package_normalizes_to_mozzarella(self):
        rule = da.normalize_pantry_label("cheese package")
        self.assertIsNotNone(rule)
        self.assertEqual(rule["item"], "mozzarella cheese")
        self.assertEqual(rule["unit"], "package")

    def test_pasta_sauce_normalizes_to_tomato_sauce(self):
        rule = da.normalize_pantry_label("Pasta Sauce Jar")
        self.assertIsNotNone(rule)
        self.assertEqual(rule["item"], "tomato sauce")

    def test_non_demo_item_is_rejected(self):
        self.assertIsNone(da.normalize_pantry_label("banana"))

    def test_open_vocab_normalization_discards_non_demo_items(self):
        result = da.normalize_open_vocabulary_detections(
            [
                {"raw_label": "olive oil bottle", "confidence": 0.12, "xyxy": [20, 20, 120, 140]},
                {"raw_label": "apple", "confidence": 0.94, "xyxy": [130, 30, 200, 140]},
            ],
            width=240,
            height=180,
            detector_name="yolo_world",
        )
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["item"], "olive oil")
        self.assertEqual(result["debug"]["discarded"][0]["reason"], "not_demo_target")

    def test_live_detection_caps_candidates_per_frame(self):
        result = da.normalize_open_vocabulary_detections(
            [
                {"raw_label": "olive oil bottle", "confidence": 0.18, "xyxy": [20, 20, 120, 170]},
                {"raw_label": "mozzarella cheese", "confidence": 0.17, "xyxy": [130, 20, 210, 160]},
                {"raw_label": "tomato sauce jar", "confidence": 0.16, "xyxy": [30, 30, 80, 80]},
            ],
            width=240,
            height=180,
            detector_name="yolo_world",
        )
        self.assertEqual(len(result["items"]), da.DEMO_MAX_LIVE_CANDIDATES)
        discarded_reasons = [entry["reason"] for entry in result["debug"]["discarded"]]
        self.assertIn("frame_candidate_limit", discarded_reasons)


class TestDetectorFallbacks(unittest.TestCase):
    def test_live_detector_falls_back_to_generic_yolo(self):
        with patch.object(da._live_yolo_world, "detect", side_effect=RuntimeError("world unavailable")):
            with patch.object(
                da._generic_fallback,
                "detect",
                return_value={"items": [], "boxes": [], "candidates": [], "width": 100, "height": 100, "debug": {}},
            ) as generic_detect:
                result = da.detect_live_frame("ZmFrZQ==")

        self.assertTrue(generic_detect.called)
        self.assertEqual(result["debug"]["requested_detector"], "yolo_world")
        self.assertEqual(result["debug"]["fallback_reason"], "world unavailable")

    def test_final_detector_returns_debuggable_fallback_when_unavailable(self):
        with patch.object(da._grounding_dino, "detect", side_effect=RuntimeError("dino unavailable")):
            result = da.detect_final_candidates("ZmFrZQ==")

        self.assertEqual(result["items"], [])
        self.assertTrue(result["debug"]["fallback"])
        self.assertEqual(result["debug"]["fallback_reason"], "dino unavailable")


if __name__ == "__main__":
    unittest.main()
