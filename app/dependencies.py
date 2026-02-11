"""Shared dependency injections for FastAPI routes."""
from app.config import get_settings

# Re-export for convenience
__all__ = ["get_settings"]
