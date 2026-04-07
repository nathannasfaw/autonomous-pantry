"""
Pantry routes: YOLO-based camera scan and persistent pantry management.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import pantry_store, session_manager
from app.services.vision_service import identify_crop
from app.services.yolo_service import detect

logger = logging.getLogger(__name__)

router = APIRouter()


class ScanRequest(BaseModel):
    image: str
    media_type: str = "image/jpeg"
    conversation_id: str | None = None


class ScanResponse(BaseModel):
    items: list[dict]
    boxes: list[dict]
    width: int
    height: int
    merged_into_session: bool = False


class CropRequest(BaseModel):
    image: str
    yolo_class: str


class PantryUpdateRequest(BaseModel):
    conversation_id: str
    items: list[dict]
    replace: bool = False


@router.post("/scan", response_model=ScanResponse)
async def scan_pantry(request: ScanRequest):
    """
    Run YOLO detection on a captured frame.
    When a conversation id is supplied, the scan is persisted as pantry data,
    but it is not routed into the chat message stream.
    """
    if not request.image:
        raise HTTPException(status_code=400, detail="No image data provided")

    try:
        result = detect(request.image, request.media_type)
    except Exception as exc:
        logger.exception("YOLO scan failed")
        raise HTTPException(status_code=500, detail=f"YOLO scan failed: {exc}") from exc

    merged = False
    if request.conversation_id:
        session = session_manager.get_session(request.conversation_id)
        if session is not None:
            session["pantry_state"] = pantry_store.upsert_items(session["client_id"], result["items"])
            merged = True
            logger.info(
                "Persisted %d scanned items for session %s",
                len(result["items"]),
                request.conversation_id,
            )

    return ScanResponse(
        items=result["items"],
        boxes=result["boxes"],
        width=result["width"],
        height=result["height"],
        merged_into_session=merged,
    )


@router.post("/identify-crop")
async def identify_crop_endpoint(request: CropRequest):
    if not request.image:
        raise HTTPException(status_code=400, detail="No image data")

    result = identify_crop(request.image, request.yolo_class)
    if result is None:
        return {"item": None}
    return result


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
