"""Health check endpoint for service monitoring."""
from fastapi import APIRouter, Depends
from app.dependencies import get_settings
from app.config import Settings

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
async def health_check(settings: Settings = Depends(get_settings)):
    """
    Health check endpoint.

    Returns service status, name, version, and authentication configuration status.
    """
    # Check if Google OAuth is configured (not using placeholder value)
    auth_configured = (
        settings.google_client_id != "" and
        settings.google_client_id != "your-client-id-here" and
        settings.google_client_secret != "" and
        settings.google_client_secret != "your-client-secret-here"
    )

    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": "1.0.0",
        "auth_configured": auth_configured
    }
