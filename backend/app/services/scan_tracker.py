"""
Pantry scan tracking service.

Separates the fast live detector loop from the slower final verification step:

* `/pantry/scan` updates sticky provisional tracks using YOLO detections only
* `/pantry/finalize-scan` verifies the best crop for each final tracked item once

This keeps the live camera responsive while still producing better final items.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import time
from typing import Any, Callable

from PIL import Image
from app.services.detector_adapters import is_demo_target_item

logger = logging.getLogger(__name__)

TRACK_MATCH_IOU = float(os.environ.get("PANTRY_SCAN_TRACK_IOU", "0.32"))
TRACK_MATCH_CENTER_RATIO = float(os.environ.get("PANTRY_SCAN_TRACK_CENTER_RATIO", "0.20"))
TRACK_STICKY_FRAMES = int(os.environ.get("PANTRY_SCAN_STICKY_FRAMES", "8"))
TRACKER_EXPIRY_SECONDS = int(os.environ.get("PANTRY_SCAN_EXPIRY_SECONDS", "900"))
FINAL_DUPLICATE_IOU = float(os.environ.get("PANTRY_SCAN_FINAL_DUP_IOU", "0.55"))
MAX_DEMO_TRACKS = int(os.environ.get("PANTRY_SCAN_MAX_DEMO_TRACKS", "3"))

TRACKER_STATES: dict[str, dict[str, Any]] = {}


def _tracker_key(scan_session_id: str, conversation_id: str | None = None) -> str:
    conversation_part = conversation_id or "anonymous"
    return f"{conversation_part}:{scan_session_id}"


def _now() -> float:
    return time.monotonic()


def reset_scan_session(scan_session_id: str, conversation_id: str | None = None) -> None:
    TRACKER_STATES.pop(_tracker_key(scan_session_id, conversation_id), None)


def _cleanup_expired_states(now: float) -> None:
    for key, state in list(TRACKER_STATES.items()):
        if now - float(state.get("updated_at", now)) > TRACKER_EXPIRY_SECONDS:
            TRACKER_STATES.pop(key, None)


def _get_state(scan_session_id: str, conversation_id: str | None = None) -> dict[str, Any]:
    now = _now()
    _cleanup_expired_states(now)
    key = _tracker_key(scan_session_id, conversation_id)
    if key not in TRACKER_STATES:
        TRACKER_STATES[key] = {
            "scan_session_id": scan_session_id,
            "conversation_id": conversation_id,
            "frame_index": 0,
            "next_track_id": 1,
            "tracks": {},
            "latest_frame_b64": None,
            "latest_media_type": "image/jpeg",
            "latest_dimensions": None,
            "updated_at": now,
        }
    TRACKER_STATES[key]["updated_at"] = now
    return TRACKER_STATES[key]


def _load_image(image_b64: str) -> Image.Image:
    img_bytes = base64.b64decode(image_b64)
    return Image.open(io.BytesIO(img_bytes)).convert("RGB")


def _crop_to_b64(image: Image.Image, box: dict[str, float]) -> str:
    crop = image.crop(
        (
            int(max(0.0, box["crop_x1"])),
            int(max(0.0, box["crop_y1"])),
            int(min(image.width, box["crop_x2"])),
            int(min(image.height, box["crop_y2"])),
        )
    )
    if crop.width <= 0 or crop.height <= 0:
        crop = image
    buf = io.BytesIO()
    crop.save(buf, format="JPEG", quality=88)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _box_iou(box_a: dict[str, float], box_b: dict[str, float]) -> float:
    inter_x1 = max(box_a["x1"], box_b["x1"])
    inter_y1 = max(box_a["y1"], box_b["y1"])
    inter_x2 = min(box_a["x2"], box_b["x2"])
    inter_y2 = min(box_a["y2"], box_b["y2"])

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    if inter_area <= 0:
        return 0.0

    area_a = max(0.0, box_a["x2"] - box_a["x1"]) * max(0.0, box_a["y2"] - box_a["y1"])
    area_b = max(0.0, box_b["x2"] - box_b["x1"]) * max(0.0, box_b["y2"] - box_b["y1"])
    union = area_a + area_b - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union


def _center_distance_ratio(box_a: dict[str, float], box_b: dict[str, float], width: int, height: int) -> float:
    ax = (box_a["x1"] + box_a["x2"]) / 2.0
    ay = (box_a["y1"] + box_a["y2"]) / 2.0
    bx = (box_b["x1"] + box_b["x2"]) / 2.0
    by = (box_b["y1"] + box_b["y2"]) / 2.0
    dx = ax - bx
    dy = ay - by
    diagonal = max((width**2 + height**2) ** 0.5, 1.0)
    return ((dx**2 + dy**2) ** 0.5) / diagonal


def _detection_quality(candidate: dict[str, Any], width: int, height: int) -> float:
    center_x = ((candidate["x1"] + candidate["x2"]) / 2.0) / max(width, 1)
    center_y = ((candidate["y1"] + candidate["y2"]) / 2.0) / max(height, 1)
    center_penalty = abs(center_x - 0.5) + abs(center_y - 0.5)
    touches_edge = (
        candidate["crop_x1"] <= 0.0
        or candidate["crop_y1"] <= 0.0
        or candidate["crop_x2"] >= float(width)
        or candidate["crop_y2"] >= float(height)
    )
    edge_penalty = 0.08 if touches_edge else 0.0
    return (
        float(candidate["selection_score"])
        + min(float(candidate["area_ratio"]) * 2.5, 0.18)
        - (center_penalty * 0.06)
        - edge_penalty
    )


def _build_pixel_box(candidate: dict[str, Any]) -> dict[str, float]:
    return {
        "x1": float(candidate["x1"]),
        "y1": float(candidate["y1"]),
        "x2": float(candidate["x2"]),
        "y2": float(candidate["y2"]),
        "crop_x1": float(candidate["crop_x1"]),
        "crop_y1": float(candidate["crop_y1"]),
        "crop_x2": float(candidate["crop_x2"]),
        "crop_y2": float(candidate["crop_y2"]),
        "area_ratio": float(candidate["area_ratio"]),
    }


def _tracks_are_compatible(track: dict[str, Any], candidate: dict[str, Any], width: int, height: int) -> bool:
    same_provisional = track["provisional_item"] == candidate["item"]
    same_raw_class = track["raw_class"] == candidate["raw_class"]
    iou = _box_iou(track["last_box"], candidate)
    center_ratio = _center_distance_ratio(track["last_box"], candidate, width, height)
    return (same_provisional or same_raw_class) and (
        iou >= TRACK_MATCH_IOU or center_ratio <= TRACK_MATCH_CENTER_RATIO
    )


def _create_track(
    state: dict[str, Any],
    candidate: dict[str, Any],
    image: Image.Image,
    frame_index: int,
    timestamp: float,
) -> dict[str, Any]:
    track_id = f"track-{state['next_track_id']}"
    state["next_track_id"] += 1
    pixel_box = _build_pixel_box(candidate)
    crop_score = _detection_quality(candidate, image.width, image.height)
    crop_b64 = _crop_to_b64(image, pixel_box)
    track = {
        "track_id": track_id,
        "raw_class": candidate["raw_class"],
        "provisional_item": candidate["item"],
        "quantity": candidate["quantity"],
        "unit": candidate["unit"],
        "verification_only": bool(candidate["verification_only"]),
        "confidence_history": [float(candidate["confidence"])],
        "best_confidence": float(candidate["confidence"]),
        "seen_count": 1,
        "first_seen_frame": frame_index,
        "last_seen_frame": frame_index,
        "first_seen_at": timestamp,
        "last_seen_at": timestamp,
        "last_box": pixel_box,
        "best_box": dict(pixel_box),
        "best_crop_b64": crop_b64,
        "best_crop_score": crop_score,
        "crop_revision": 1,
        "verified_revision": 0,
        "verified_result": None,
    }
    state["tracks"][track_id] = track
    return track


def _update_track(
    track: dict[str, Any],
    candidate: dict[str, Any],
    image: Image.Image,
    frame_index: int,
    timestamp: float,
) -> None:
    track["raw_class"] = candidate["raw_class"]
    track["last_box"] = _build_pixel_box(candidate)
    track["last_seen_frame"] = frame_index
    track["last_seen_at"] = timestamp
    track["seen_count"] += 1
    track["confidence_history"].append(float(candidate["confidence"]))
    track["confidence_history"] = track["confidence_history"][-8:]
    track["best_confidence"] = max(track["best_confidence"], float(candidate["confidence"]))

    already_verified = int(track.get("verified_revision", 0)) > 0
    if not track["verification_only"] and candidate["verification_only"]:
        pass
    elif track["verification_only"] and not candidate["verification_only"]:
        track["verification_only"] = False
        if not already_verified:
            track["provisional_item"] = candidate["item"]
            track["quantity"] = candidate["quantity"]
            track["unit"] = candidate["unit"]
    elif not already_verified and float(candidate["confidence"]) >= track["best_confidence"] - 0.03:
        track["provisional_item"] = candidate["item"]
        track["quantity"] = candidate["quantity"]
        track["unit"] = candidate["unit"]

    candidate_score = _detection_quality(candidate, image.width, image.height)
    if candidate_score > float(track["best_crop_score"]) + 0.01:
        track["best_box"] = _build_pixel_box(candidate)
        track["best_crop_b64"] = _crop_to_b64(image, track["best_box"])
        track["best_crop_score"] = candidate_score
        track["crop_revision"] += 1


def _best_track_match(
    tracks: list[dict[str, Any]],
    candidate: dict[str, Any],
    width: int,
    height: int,
) -> dict[str, Any] | None:
    matches = [track for track in tracks if _tracks_are_compatible(track, candidate, width, height)]
    if not matches:
        return None
    matches.sort(
        key=lambda track: (
            _box_iou(track["last_box"], candidate),
            -_center_distance_ratio(track["last_box"], candidate, width, height),
            track["best_confidence"],
        ),
        reverse=True,
    )
    return matches[0]


def _active_tracks(state: dict[str, Any], frame_index: int) -> list[dict[str, Any]]:
    return [
        track
        for track in state["tracks"].values()
        if frame_index - int(track["last_seen_frame"]) <= TRACK_STICKY_FRAMES
    ]


def _track_box_payload(track: dict[str, Any], width: int, height: int, frame_index: int) -> dict[str, Any]:
    box = track["last_box"]
    live_verified = int(track.get("verified_revision", 0)) > 0
    return {
        "track_id": track["track_id"],
        "x1": round(box["x1"] / width, 4),
        "y1": round(box["y1"] / height, 4),
        "x2": round(box["x2"] / width, 4),
        "y2": round(box["y2"] / height, 4),
        "item": track["provisional_item"],
        "confidence": round(track["best_confidence"], 4),
        "provisional": not live_verified,
        "live_verified": live_verified,
        "verification_only": track["verification_only"],
        "raw_class": track["raw_class"],
        "stale_frames": frame_index - int(track["last_seen_frame"]),
    }


def _track_item_payload(track: dict[str, Any], frame_index: int) -> dict[str, Any]:
    live_verified = int(track.get("verified_revision", 0)) > 0
    return {
        "track_id": track["track_id"],
        "item": track["provisional_item"],
        "quantity": track["quantity"],
        "unit": track["unit"],
        "confidence": round(track["best_confidence"], 4),
        "provisional": not live_verified,
        "live_verified": live_verified,
        "verification_only": track["verification_only"],
        "raw_class": track["raw_class"],
        "detector": track.get("detector", "live_detector"),
        "seen_count": track["seen_count"],
        "stale_frames": frame_index - int(track["last_seen_frame"]),
    }


def _candidate_from_track(track: dict[str, Any]) -> dict[str, Any]:
    return {
        "track_id": track["track_id"],
        "raw_class": track["raw_class"],
        "provisional_item": track["provisional_item"],
        "quantity": track["quantity"],
        "unit": track["unit"],
        "verification_only": track["verification_only"],
        "best_confidence": track["best_confidence"],
        "best_box": dict(track["best_box"]),
        "best_crop_b64": track["best_crop_b64"],
        "best_crop_score": track["best_crop_score"],
        "crop_revision": track["crop_revision"],
        "verified_revision": track["verified_revision"],
        "verified_result": track["verified_result"],
        "source_detector": track.get("detector", "live_detector"),
        "source": "tracked_live_detection",
    }


def _crop_from_image(image: Image.Image, box: dict[str, float]) -> str:
    return _crop_to_b64(image, box)


def _final_detector_match(
    review_candidate: dict[str, Any],
    final_candidate: dict[str, Any],
    width: int,
    height: int,
) -> bool:
    iou = _box_iou(review_candidate["best_box"], final_candidate)
    center_ratio = _center_distance_ratio(review_candidate["best_box"], final_candidate, width, height)
    same_item = review_candidate["provisional_item"] == final_candidate["item"]
    return iou >= TRACK_MATCH_IOU or (same_item and center_ratio <= TRACK_MATCH_CENTER_RATIO)


def _merge_final_detections(
    review_candidates: list[dict[str, Any]],
    final_detect_result: dict[str, Any] | None,
    latest_image: Image.Image | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:
    if final_detect_result is None:
        return review_candidates, [], None

    final_candidates = list(final_detect_result.get("candidates", []))
    if not final_candidates:
        return review_candidates, [], final_detect_result.get("debug")

    width = int(final_detect_result.get("width") or (latest_image.width if latest_image else 1))
    height = int(final_detect_result.get("height") or (latest_image.height if latest_image else 1))
    merge_debug: list[dict[str, Any]] = []
    final_only_counter = 0

    for final_candidate in sorted(final_candidates, key=lambda item: item["selection_score"], reverse=True):
        matched = next(
            (
                review_candidate
                for review_candidate in review_candidates
                if _final_detector_match(review_candidate, final_candidate, width, height)
            ),
            None,
        )
        if matched is not None:
            previous_item = matched["provisional_item"]
            matched["source"] = "live_plus_final_detection"
            matched["source_detector"] = final_candidate.get("detector", "grounding_dino")
            matched["raw_class"] = final_candidate["raw_class"]
            if matched["verification_only"] or final_candidate["confidence"] >= matched["best_confidence"] - 0.08:
                matched["provisional_item"] = final_candidate["item"]
                matched["quantity"] = final_candidate["quantity"]
                matched["unit"] = final_candidate["unit"]
                matched["verification_only"] = bool(final_candidate["verification_only"])
            if latest_image is not None and final_candidate["selection_score"] > matched["best_crop_score"] - 0.02:
                matched["best_box"] = _build_pixel_box(final_candidate)
                matched["best_crop_b64"] = _crop_from_image(latest_image, matched["best_box"])
                matched["best_crop_score"] = float(final_candidate["selection_score"])
                matched["crop_revision"] += 1
            matched["best_confidence"] = max(matched["best_confidence"], float(final_candidate["confidence"]))
            merge_debug.append(
                {
                    "track_id": matched["track_id"],
                    "decision": "refined",
                    "from_item": previous_item,
                    "to_item": matched["provisional_item"],
                    "detector": final_candidate.get("detector"),
                    "raw_label": final_candidate.get("raw_label"),
                }
            )
            continue

        if latest_image is None:
            continue

        final_only_counter += 1
        best_box = _build_pixel_box(final_candidate)
        review_candidates.append(
            {
                "track_id": f"final-{final_only_counter}",
                "raw_class": final_candidate["raw_class"],
                "provisional_item": final_candidate["item"],
                "quantity": final_candidate["quantity"],
                "unit": final_candidate["unit"],
                "verification_only": bool(final_candidate["verification_only"]),
                "best_confidence": float(final_candidate["confidence"]),
                "best_box": best_box,
                "best_crop_b64": _crop_from_image(latest_image, best_box),
                "best_crop_score": float(final_candidate["selection_score"]),
                "crop_revision": 1,
                "verified_revision": 0,
                "verified_result": None,
                "source_detector": final_candidate.get("detector", "grounding_dino"),
                "source": "final_detector_only",
            }
        )
        merge_debug.append(
            {
                "track_id": f"final-{final_only_counter}",
                "decision": "added",
                "item": final_candidate["item"],
                "detector": final_candidate.get("detector"),
                "raw_label": final_candidate.get("raw_label"),
            }
        )

    return review_candidates, merge_debug, final_detect_result.get("debug")


def update_scan(
    *,
    scan_session_id: str,
    image_b64: str,
    detect_result: dict[str, Any],
    conversation_id: str | None = None,
    verify_fn: Callable[[str, str], dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    state = _get_state(scan_session_id, conversation_id)
    state["frame_index"] += 1
    state["latest_frame_b64"] = image_b64
    state["latest_media_type"] = "image/jpeg"
    frame_index = int(state["frame_index"])
    timestamp = _now()
    image = _load_image(image_b64)
    state["latest_dimensions"] = (image.width, image.height)
    width = int(detect_result["width"])
    height = int(detect_result["height"])

    frame_events: list[dict[str, Any]] = []
    active_tracks = _active_tracks(state, frame_index)

    for candidate in sorted(detect_result.get("candidates", []), key=lambda item: item["selection_score"], reverse=True):
        track = _best_track_match(active_tracks, candidate, width, height)
        if track is None:
            if len(active_tracks) >= MAX_DEMO_TRACKS:
                frame_events.append(
                    {
                        "event": "discarded",
                        "item": candidate["item"],
                        "raw_class": candidate["raw_class"],
                        "reason": "max_demo_tracks_reached",
                    }
                )
                continue
            track = _create_track(state, candidate, image, frame_index, timestamp)
            track["detector"] = candidate.get("detector", "live_detector")
            # Inline Claude verification: run once on first detection of each new track.
            # This gives correct item names during live scan without a separate finalize
            # wait.  finalize_scan will skip tracks whose verified_revision is current.
            if verify_fn is not None and track.get("best_crop_b64"):
                try:
                    result = verify_fn(track["best_crop_b64"], track["raw_class"])
                    if result:
                        track["provisional_item"] = result["item"]
                        track["quantity"] = result["quantity"]
                        track["unit"] = result["unit"]
                        track["verified_revision"] = track["crop_revision"]
                        track["verified_result"] = result
                        logger.info(
                            "Live verified track %s → %r", track["track_id"], result["item"]
                        )
                except Exception as exc:
                    logger.warning("Live verification failed for track %s: %s", track["track_id"], exc)
            active_tracks.append(track)
            frame_events.append(
                {
                    "track_id": track["track_id"],
                    "event": "created",
                    "item": track["provisional_item"],
                    "raw_class": track["raw_class"],
                    "verified": track.get("verified_revision", 0) > 0,
                }
            )
            continue

        previous_revision = track["crop_revision"]
        _update_track(track, candidate, image, frame_index, timestamp)
        track["detector"] = candidate.get("detector", track.get("detector", "live_detector"))
        frame_events.append(
            {
                "track_id": track["track_id"],
                "event": "updated",
                "item": track["provisional_item"],
                "raw_class": track["raw_class"],
                "crop_updated": track["crop_revision"] != previous_revision,
            }
        )

    visible_tracks = sorted(
        _active_tracks(state, frame_index),
        key=lambda track: (track["verification_only"], -track["best_confidence"], track["track_id"]),
    )
    boxes = [_track_box_payload(track, width, height, frame_index) for track in visible_tracks]
    items = [_track_item_payload(track, frame_index) for track in visible_tracks]

    debug = dict(detect_result.get("debug") or {})
    debug["tracking"] = {
        "frame_index": frame_index,
        "active_tracks": len(visible_tracks),
        "events": frame_events,
    }
    return {
        "scan_session_id": scan_session_id,
        "items": items,
        "boxes": boxes,
        "width": width,
        "height": height,
        "debug": debug,
    }


def _dedupe_final_tracks(tracks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    debug: list[dict[str, Any]] = []
    for track in sorted(tracks, key=lambda item: (item["verification_only"], -item["best_crop_score"], -item["best_confidence"])):
        duplicate = next(
            (
                chosen
                for chosen in kept
                if chosen["provisional_item"] == track["provisional_item"]
                and _box_iou(chosen["best_box"], track["best_box"]) >= FINAL_DUPLICATE_IOU
            ),
            None,
        )
        if duplicate is not None:
            debug.append(
                {
                    "track_id": track["track_id"],
                    "decision": "discarded",
                    "reason": "duplicate_final_track",
                    "duplicate_of": duplicate["track_id"],
                }
            )
            continue
        kept.append(track)
        debug.append({"track_id": track["track_id"], "decision": "kept"})
    return kept, debug


def finalize_scan(
    *,
    scan_session_id: str,
    conversation_id: str | None = None,
    verify_fn: Callable[[str, str], dict[str, Any] | None],
    final_detect_fn: Callable[[str, str], dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    state = _get_state(scan_session_id, conversation_id)
    frame_index = int(state["frame_index"])
    review_candidates = []
    for track in _active_tracks(state, frame_index):
        if not track["best_crop_b64"] or track["seen_count"] < 1:
            continue
        track["source"] = track.get("source", "tracked_live_detection")
        track["source_detector"] = track.get("source_detector", track.get("detector", "live_detector"))
        review_candidates.append(track)
    final_detector_result = None
    final_detector_debug = None
    final_merge_debug: list[dict[str, Any]] = []
    latest_image = None
    if state.get("latest_frame_b64"):
        latest_image = _load_image(state["latest_frame_b64"])
    if final_detect_fn is not None and state.get("latest_frame_b64"):
        try:
            final_detector_result = final_detect_fn(state["latest_frame_b64"], state.get("latest_media_type", "image/jpeg"))
        except Exception as exc:
            final_detector_debug = {"fallback": True, "fallback_reason": str(exc)}
    review_candidates, final_merge_debug, detector_debug = _merge_final_detections(
        review_candidates,
        final_detector_result,
        latest_image,
    )
    if detector_debug is not None:
        final_detector_debug = detector_debug

    candidate_tracks, dedupe_debug = _dedupe_final_tracks(review_candidates)

    verification_calls = 0
    skipped_tracks: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []

    for track in candidate_tracks:
        verified_result = track.get("verified_result")
        trust_final_detector = (
            track.get("source") in {"live_plus_final_detection", "final_detector_only"}
            and is_demo_target_item(track["provisional_item"])
        )
        if trust_final_detector:
            verified_result = {
                "item": track["provisional_item"],
                "quantity": float(track["quantity"]),
                "unit": str(track["unit"]),
            }
            track["verified_result"] = verified_result
            track["verified_revision"] = track["crop_revision"]
        elif track["verified_revision"] != track["crop_revision"]:
            verification_calls += 1
            verified_result = verify_fn(track["best_crop_b64"], track["raw_class"])
            track["verified_result"] = verified_result
            track["verified_revision"] = track["crop_revision"]

        if verified_result is None and track["verification_only"]:
            skipped_tracks.append(
                {
                    "track_id": track["track_id"],
                    "reason": "verification_only_unverified",
                    "provisional_item": track["provisional_item"],
                }
            )
            continue

        item_name = verified_result["item"] if verified_result else track["provisional_item"]
        quantity = float(verified_result["quantity"]) if verified_result else float(track["quantity"])
        unit = str(verified_result["unit"]) if verified_result else str(track["unit"])
        items.append(
            {
                "track_id": track["track_id"],
                "item": item_name,
                "quantity": quantity,
                "unit": unit,
                "confidence": round(track["best_confidence"], 4),
                "verified": bool(verified_result),
                "verification_source": (
                    "final_detector_trusted"
                    if trust_final_detector
                    else ("claude" if verified_result else "provisional_detector")
                ),
                "provisional_item": track["provisional_item"],
                "raw_class": track["raw_class"],
                "final_source": track.get("source", "tracked_live_detection"),
                "detector": track.get("source_detector", track.get("detector", "live_detector")),
            }
        )
        logger.info("Final confirmed: %s", item_name)

    return {
        "scan_session_id": scan_session_id,
        "items": items,
        "debug": {
            "tracking": {
                "frame_index": frame_index,
                "active_tracks": len(candidate_tracks),
                "verification_calls": verification_calls,
            },
            "final_detector": final_detector_debug,
            "final_merge": final_merge_debug,
            "final_dedupe": dedupe_debug,
            "skipped_tracks": skipped_tracks,
        },
    }
