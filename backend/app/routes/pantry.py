"""
Pantry routes: YOLO-based camera scan and persistent pantry management.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.detector_adapters import detect_final_candidates, detect_live_frame
from app.services import pantry_store, scan_tracker, session_manager
from app.services.vision_service import identify_crop

logger = logging.getLogger(__name__)

router = APIRouter()


class ScanRequest(BaseModel):
    image: str
    media_type: str = "image/jpeg"
    conversation_id: str | None = None
    scan_session_id: str | None = None


class ScanResponse(BaseModel):
    items: list[dict]
    boxes: list[dict]
    width: int
    height: int
    merged_into_session: bool = False
    debug: dict | None = None
    scan_session_id: str | None = None


class CropRequest(BaseModel):
    image: str
    yolo_class: str


class FinalizeScanRequest(BaseModel):
    scan_session_id: str
    conversation_id: str | None = None


class FinalizeScanResponse(BaseModel):
    items: list[dict]
    debug: dict | None = None
    scan_session_id: str


class ResetScanRequest(BaseModel):
    scan_session_id: str
    conversation_id: str | None = None


class PantryUpdateRequest(BaseModel):
    conversation_id: str
    items: list[dict]
    replace: bool = False


@router.post("/scan", response_model=ScanResponse)
async def scan_pantry(request: ScanRequest):
    """
    Run YOLO detection on a captured frame.
    Live scanning is detector-only; final verification happens in /finalize-scan.
    """
    if not request.image:
        raise HTTPException(status_code=400, detail="No image data provided")

    try:
        detect_result = detect_live_frame(request.image, request.media_type)
    except Exception as exc:
        logger.exception("YOLO scan failed")
        raise HTTPException(status_code=500, detail=f"YOLO scan failed: {exc}") from exc

    result = detect_result
    if request.scan_session_id:
        result = scan_tracker.update_scan(
            scan_session_id=request.scan_session_id,
            conversation_id=request.conversation_id,
            image_b64=request.image,
            detect_result=detect_result,
            verify_fn=identify_crop,
        )

    return ScanResponse(
        items=result["items"],
        boxes=result["boxes"],
        width=result["width"],
        height=result["height"],
        merged_into_session=False,
        debug=result.get("debug"),
        scan_session_id=result.get("scan_session_id"),
    )


@router.post("/identify-crop")
async def identify_crop_endpoint(request: CropRequest):
    if not request.image:
        raise HTTPException(status_code=400, detail="No image data")

    result = identify_crop(request.image, request.yolo_class)
    if result is None:
        return {"item": None}
    return result


@router.post("/finalize-scan", response_model=FinalizeScanResponse)
async def finalize_scan_endpoint(request: FinalizeScanRequest):
    try:
        result = scan_tracker.finalize_scan(
            scan_session_id=request.scan_session_id,
            conversation_id=request.conversation_id,
            verify_fn=identify_crop,
            final_detect_fn=detect_final_candidates,
        )
    except Exception as exc:
        logger.exception("Pantry scan finalization failed")
        raise HTTPException(status_code=500, detail=f"Pantry scan finalization failed: {exc}") from exc

    return FinalizeScanResponse(
        items=result["items"],
        debug=result.get("debug"),
        scan_session_id=result["scan_session_id"],
    )


@router.post("/reset-scan")
async def reset_scan_endpoint(request: ResetScanRequest):
    scan_tracker.reset_scan_session(request.scan_session_id, request.conversation_id)
    return {"status": "ok"}


@router.post("/update")
async def update_pantry(request: PantryUpdateRequest):
    """
    Confirm and persist pantry items. This is a data update path, not a chat path.
    """
    session = session_manager.get_session(request.conversation_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if request.replace:
        session["pantry_state"] = pantry_store.replace_items(session["client_id"], request.items)
    else:
        session["pantry_state"] = pantry_store.upsert_items(session["client_id"], request.items)

    return {"status": "ok", "pantry": session["pantry_state"]}


@router.get("/{conversation_id}")
async def get_pantry(conversation_id: str):
    """Return the current persistent pantry state for a session."""
    session = session_manager.get_session(conversation_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    session["pantry_state"] = pantry_store.get_items(session["client_id"])
    return {"pantry": session["pantry_state"]}
