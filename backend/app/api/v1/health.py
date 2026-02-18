"""Health-check endpoint — useful for Docker, load balancers, and CI."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Return a simple OK status."""
    return {"status": "healthy"}
