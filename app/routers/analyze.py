"""Analyze endpoint for n8n integration."""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1", tags=["analyze"])


class AnalyzeRequest(BaseModel):
    """Request model for analyze endpoint."""
    url: str
    keyword: str


class AnalyzeResponse(BaseModel):
    """Response model for analyze endpoint."""
    status: str
    url: str
    keyword: str
    message: str


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """
    Analyze endpoint stub for n8n integration testing.

    This endpoint validates the n8n -> Python communication pattern.
    Real implementation comes in Phase 2.
    """
    return AnalyzeResponse(
        status="stub",
        url=request.url,
        keyword=request.keyword,
        message="Analyze endpoint ready — data collection not yet implemented"
    )
