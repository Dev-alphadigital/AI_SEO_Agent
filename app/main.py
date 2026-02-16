"""FastAPI application entry point."""
import os

from fastapi import FastAPI
from app.routers import health, analyze, auth
from app.config import get_settings

app = FastAPI(
    title="AI SEO Agent",
    version="1.0.0"
)

# Include routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(analyze.router)

# Ensure output directory exists on startup
os.makedirs("output", exist_ok=True)


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.api_port)
