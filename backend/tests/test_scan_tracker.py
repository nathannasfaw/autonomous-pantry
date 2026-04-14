from __future__ import annotations

import base64
import io
import unittest

from PIL import Image

from app.services import detector_adapters as da
from app.services import scan_tracker as st
from app.services import yolo_service as ys


def _blank_frame(width: int = 240, height: int = 180) -> str:
    image = Image.new("RGB", (width, height), color=(235, 235, 235))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _detect(raw_detections, width: int = 240, height: int = 180):
    return ys.process_detections(raw_detections, width=width, height=height)


class TestScanTracker(unittest.TestCase):
    def setUp(self):
        st.TRACKER_STATES.clear()
        self.scan_session_id = "scan-test"
        self.image_b64 = _blank_frame()

    def test_merges_same_object_across_frames(self):
        first = _detect([{"raw_class": "Milk", "confidence": 0.72, "xyxy": [20, 20, 100, 150]}])
        second = _detect([{"raw_class": "Milk", "confidence": 0.75, "xyxy": [24, 24, 104, 154]}])

        result_one = st.update_scan(
            scan_session_id=self.scan_session_id,
            image_b64=self.image_b64,
            detect_result=first,
            conversation_id="conv-1",
        )
        result_two = st.update_scan(
            scan_session_id=self.scan_session_id,
            image_b64=self.image_b64,
            detect_result=second,
            conversation_id="conv-1",
        )

        self.assertEqual(len(result_one["items"]), 1)
        self.assertEqual(len(result_two["items"]), 1)
        self.assertEqual(result_one["items"][0]["track_id"], result_two["items"][0]["track_id"])
        self.assertEqual(result_two["items"][0]["seen_count"], 2)

    def test_keeps_distinct_objects_separate(self):
        result = st.update_scan(
            scan_session_id=self.scan_session_id,
            image_b64=self.image_b64,
            detect_result=_detect(
                [
                    {"raw_class": "Apple", "confidence": 0.82, "xyxy": [20, 20, 70, 90]},
                    {"raw_class": "Apple", "confidence": 0.80, "xyxy": [150, 30, 210, 100]},
                ]
            ),
            conversation_id="conv-1",
        )

        self.assertEqual(len(result["items"]), 2)
        self.assertNotEqual(result["items"][0]["track_id"], result["items"][1]["track_id"])

    def test_best_crop_selection_prefers_higher_quality_detection(self):
        first = _detect([{"raw_class": "Cheese", "confidence": 0.70, "xyxy": [40, 40, 100, 100]}])
        second = _detect([{"raw_class": "Cheese", "confidence": 0.84, "xyxy": [28, 30, 145, 150]}])

        st.update_scan(
            scan_session_id=self.scan_session_id,
            image_b64=self.image_b64,
            detect_result=first,
            conversation_id="conv-1",
        )
        st.update_scan(
            scan_session_id=self.scan_session_id,
            image_b64=self.image_b64,
            detect_result=second,
            conversation_id="conv-1",
        )

        state = st.TRACKER_STATES[st._tracker_key(self.scan_session_id, "conv-1")]
        track = state["tracks"]["track-1"]
        self.assertEqual(track["crop_revision"], 2)
        self.assertGreater(track["best_box"]["x2"] - track["best_box"]["x1"], 100)

    def test_finalize_verifies_each_track_once_until_crop_changes(self):
        verification_calls = []

        def verify(crop_b64: str, raw_class: str):
            verification_calls.append(raw_class)
            return {"item": f"verified {raw_class.lower()}", "quantity": 1.0, "unit": "count"}

        initial = _detect(
            [
                {"raw_class": "Milk", "confidence": 0.76, "xyxy": [20, 20, 100, 150]},
                {"raw_class": "Apple", "confidence": 0.83, "xyxy": [140, 30, 210, 100]},
            ]
        )
        st.update_scan(
            scan_session_id=self.scan_session_id,
            image_b64=self.image_b64,
            detect_result=initial,
            conversation_id="conv-1",
        )

        first_finalize = st.finalize_scan(
            scan_session_id=self.scan_session_id,
            conversation_id="conv-1",
            verify_fn=verify,
        )
        second_finalize = st.finalize_scan(
            scan_session_id=self.scan_session_id,
            conversation_id="conv-1",
            verify_fn=verify,
        )

        self.assertEqual(len(first_finalize["items"]), 2)
        self.assertEqual(len(second_finalize["items"]), 2)
        self.assertEqual(len(verification_calls), 2)

        improved_milk = _detect([{"raw_class": "Milk", "confidence": 0.89, "xyxy": [18, 18, 120, 165]}])
        st.update_scan(
            scan_session_id=self.scan_session_id,
            image_b64=self.image_b64,
            detect_result=improved_milk,
            conversation_id="conv-1",
        )
        st.finalize_scan(
            scan_session_id=self.scan_session_id,
            conversation_id="conv-1",
            verify_fn=verify,
        )

        self.assertEqual(len(verification_calls), 3)

    def test_finalize_drops_unverified_verification_only_tracks(self):
        st.update_scan(
            scan_session_id=self.scan_session_id,
            image_b64=self.image_b64,
            detect_result=_detect([{"raw_class": "Bottle", "confidence": 0.92, "xyxy": [30, 20, 120, 170]}]),
            conversation_id="conv-1",
        )

        result = st.finalize_scan(
            scan_session_id=self.scan_session_id,
            conversation_id="conv-1",
            verify_fn=lambda crop_b64, raw_class: None,
        )

        self.assertEqual(result["items"], [])
        self.assertEqual(result["debug"]["skipped_tracks"][0]["reason"], "verification_only_unverified")

    def test_finalize_returns_review_items_with_verified_status(self):
        st.update_scan(
            scan_session_id=self.scan_session_id,
            image_b64=self.image_b64,
            detect_result=_detect([{"raw_class": "Milk", "confidence": 0.79, "xyxy": [20, 20, 100, 150]}]),
            conversation_id="conv-1",
        )

        result = st.finalize_scan(
            scan_session_id=self.scan_session_id,
            conversation_id="conv-1",
            verify_fn=lambda crop_b64, raw_class: {"item": "whole milk", "quantity": 1.0, "unit": "carton"},
        )

        self.assertEqual(len(result["items"]), 1)
        self.assertTrue(result["items"][0]["verified"])
        self.assertEqual(result["items"][0]["item"], "whole milk")
        self.assertEqual(result["items"][0]["provisional_item"], "milk")

    def test_final_detector_can_add_review_candidate_missing_from_live_tracks(self):
        st.update_scan(
            scan_session_id=self.scan_session_id,
            image_b64=self.image_b64,
            detect_result=_detect([{"raw_class": "Cheese", "confidence": 0.79, "xyxy": [20, 20, 100, 150]}]),
            conversation_id="conv-1",
        )

        def final_detect(image_b64: str, media_type: str):
            del image_b64, media_type
            return da.normalize_open_vocabulary_detections(
                [{"raw_label": "olive oil bottle", "confidence": 0.81, "xyxy": [130, 20, 210, 160]}],
                width=240,
                height=180,
                detector_name="grounding_dino",
            )

        result = st.finalize_scan(
            scan_session_id=self.scan_session_id,
            conversation_id="conv-1",
            verify_fn=lambda crop_b64, raw_class: {"item": raw_class.lower(), "quantity": 1.0, "unit": "count"},
            final_detect_fn=final_detect,
        )

        item_names = {item["provisional_item"] for item in result["items"]}
        self.assertIn("cheese", item_names)
        self.assertIn("olive oil", item_names)
        self.assertTrue(any(entry["decision"] == "added" for entry in result["debug"]["final_merge"]))

    def test_finalize_falls_back_to_tracked_results_when_final_detector_returns_no_candidates(self):
        st.update_scan(
            scan_session_id=self.scan_session_id,
            image_b64=self.image_b64,
            detect_result=_detect([{"raw_class": "Milk", "confidence": 0.79, "xyxy": [20, 20, 100, 150]}]),
            conversation_id="conv-1",
        )

        result = st.finalize_scan(
            scan_session_id=self.scan_session_id,
            conversation_id="conv-1",
            verify_fn=lambda crop_b64, raw_class: {"item": "whole milk", "quantity": 1.0, "unit": "carton"},
            final_detect_fn=lambda image_b64, media_type: {"items": [], "boxes": [], "candidates": [], "debug": {"fallback": True, "fallback_reason": "no final model"}},
        )

        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["final_source"], "tracked_live_detection")
        self.assertEqual(result["debug"]["final_detector"]["fallback_reason"], "no final model")

    def test_demo_target_from_final_detector_skips_claude_verification(self):
        verification_calls = []
        st.update_scan(
            scan_session_id=self.scan_session_id,
            image_b64=self.image_b64,
            detect_result=_detect([{"raw_class": "Bottle", "confidence": 0.82, "xyxy": [20, 20, 100, 150]}]),
            conversation_id="conv-1",
        )

        def verify(crop_b64, raw_class):
            verification_calls.append(raw_class)
            return {"item": raw_class.lower(), "quantity": 1.0, "unit": "count"}

        def final_detect(image_b64: str, media_type: str):
            del image_b64, media_type
            return da.normalize_open_vocabulary_detections(
                [{"raw_label": "olive oil bottle", "confidence": 0.21, "xyxy": [20, 20, 110, 160]}],
                width=240,
                height=180,
                detector_name="grounding_dino",
            )

        result = st.finalize_scan(
            scan_session_id=self.scan_session_id,
            conversation_id="conv-1",
            verify_fn=verify,
            final_detect_fn=final_detect,
        )

        self.assertEqual(verification_calls, [])
        self.assertEqual(result["items"][0]["item"], "olive oil")
        self.assertEqual(result["items"][0]["verification_source"], "final_detector_trusted")


if __name__ == "__main__":
    unittest.main()
