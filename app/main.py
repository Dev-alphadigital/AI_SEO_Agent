"""FastAPI application entry point."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.routers import health, analyze, auth, reoptimize
from app.config import get_settings
from app.services.page_scraper import close_browser


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    os.makedirs("output", exist_ok=True)
    yield
    # Shutdown
    await close_browser()


app = FastAPI(
    title="AI SEO Agent",
    version="1.0.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(analyze.router)
app.include_router(reoptimize.router)


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.api_port)
