from __future__ import annotations

import unittest

from app.services import yolo_service as ys


class TestYoloClassNormalization(unittest.TestCase):
    def test_normalize_class_name(self):
        self.assertEqual(ys._normalize_class_name("Tin can"), "tin can")
        self.assertEqual(ys._normalize_class_name("Olive_Oil"), "olive oil")

    def test_lookup_exact_rule(self):
        rule = ys._lookup("Milk")
        self.assertIsNotNone(rule)
        self.assertEqual(rule["item"], "milk")
        self.assertFalse(rule["verification_only"])

    def test_lookup_pattern_rule(self):
        rule = ys._lookup("Cooking Oil")
        self.assertIsNotNone(rule)
        self.assertEqual(rule["item"], "olive oil")

    def test_lookup_generic_container_marks_verification_only(self):
        rule = ys._lookup("Bottle")
        self.assertIsNotNone(rule)
        self.assertTrue(rule["verification_only"])


class TestYoloCropAndFiltering(unittest.TestCase):
    def test_pad_box_adds_context_without_exceeding_bounds(self):
        padded = ys._pad_box(10, 20, 50, 60, 100, 100, padding_ratio=0.25)
        self.assertEqual(padded, (0.0, 10.0, 60.0, 70.0))

    def test_process_detections_discards_boxes_below_threshold(self):
        result = ys.process_detections(
            [{"raw_class": "Milk", "confidence": 0.15, "xyxy": [10, 10, 80, 90]}],
            width=100,
            height=100,
        )
        self.assertEqual(result["items"], [])
        self.assertEqual(result["boxes"], [])
        self.assertEqual(result["debug"]["discarded"][0]["reason"], "below_class_threshold")

    def test_process_detections_discards_tiny_boxes(self):
        result = ys.process_detections(
            [{"raw_class": "Apple", "confidence": 0.95, "xyxy": [1, 1, 5, 5]}],
            width=400,
            height=400,
        )
        self.assertEqual(result["items"], [])
        self.assertEqual(result["debug"]["discarded"][0]["reason"], "box_too_small")


class TestYoloDedupeAndSelection(unittest.TestCase):
    def test_same_raw_class_keeps_distinct_candidates(self):
        result = ys.process_detections(
            [
                {"raw_class": "Milk", "confidence": 0.62, "xyxy": [20, 20, 120, 220]},
                {"raw_class": "Milk", "confidence": 0.70, "xyxy": [170, 30, 280, 250]},
            ],
            width=300,
            height=300,
        )
        self.assertEqual(len(result["boxes"]), 2)
        self.assertEqual(result["boxes"][0]["label"], "Milk")
        self.assertEqual(result["boxes"][1]["label"], "Milk #2")
        self.assertAlmostEqual(result["items"][1]["confidence"], 0.62, places=2)

    def test_overlapping_candidates_are_suppressed(self):
        result = ys.process_detections(
            [
                {"raw_class": "Milk", "confidence": 0.78, "xyxy": [20, 20, 120, 220]},
                {"raw_class": "Milk", "confidence": 0.64, "xyxy": [24, 26, 118, 216]},
            ],
            width=300,
            height=300,
        )
        self.assertEqual(len(result["boxes"]), 1)
        discarded_reasons = [entry["reason"] for entry in result["debug"]["discarded"]]
        self.assertIn("overlapping_lower_ranked_candidate", discarded_reasons)

    def test_generic_container_survives_as_verification_only_candidate(self):
        result = ys.process_detections(
            [{"raw_class": "Bottle", "confidence": 0.88, "xyxy": [20, 20, 120, 220]}],
            width=300,
            height=300,
        )
        self.assertEqual(len(result["items"]), 1)
        self.assertTrue(result["items"][0]["verification_only"])
        self.assertTrue(result["boxes"][0]["verification_only"])

    def test_output_contains_padded_crop_box_metadata(self):
        result = ys.process_detections(
            [{"raw_class": "Cheese", "confidence": 0.81, "xyxy": [50, 40, 150, 140]}],
            width=200,
            height=200,
        )
        box = result["boxes"][0]
        self.assertLess(box["crop_x1"], box["x1"])
        self.assertLess(box["crop_y1"], box["y1"])
        self.assertGreater(box["crop_x2"], box["x2"])
        self.assertGreater(box["crop_y2"], box["y2"])

    def test_pantry_friendly_output_for_common_item(self):
        result = ys.process_detections(
            [{"raw_class": "Pasta", "confidence": 0.73, "xyxy": [30, 30, 180, 220]}],
            width=240,
            height=240,
        )
        self.assertEqual(result["items"][0]["item"], "pasta")
        self.assertEqual(result["items"][0]["unit"], "package")
        self.assertFalse(result["items"][0]["verification_only"])


if __name__ == "__main__":
    unittest.main()
