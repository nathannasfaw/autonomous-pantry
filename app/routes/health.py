"""Health check route."""

from datetime import datetime, timezone
from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "service": "autonomous-pantry",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
