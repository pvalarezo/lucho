"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Simple liveness probe. Returns OK if the API is running."""
    return {"status": "ok", "service": "Lucho"}
