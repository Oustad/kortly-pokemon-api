"""Health check endpoints for Pokemon card scanner."""

import logging
import os

from fastapi import APIRouter

from ..models.schemas import HealthResponse
from ..services.gemini_service import GeminiService
from ..services.tcg_client import PokemonTcgClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Check the health status of all services.
    
    Returns the overall system status and individual service availability.
    """
    services_status = {}
    
    # Check Gemini service
    try:
        gemini_service = GeminiService(api_key=os.getenv("GOOGLE_API_KEY"))
        # Just check if we can initialize the service
        gemini_available = gemini_service._api_key is not None
        services_status["gemini"] = gemini_available
    except Exception as e:
        logger.error(f"Gemini health check failed: {e}")
        services_status["gemini"] = False
    
    # Check TCG client
    try:
        tcg_client = PokemonTcgClient()
        stats = tcg_client.get_rate_limit_stats()
        tcg_available = stats["remaining_requests"] > 0
        services_status["tcg_api"] = tcg_available
        services_status["tcg_remaining_requests"] = stats["remaining_requests"]
    except Exception as e:
        logger.error(f"TCG API health check failed: {e}")
        services_status["tcg_api"] = False
    
    # Check image processing
    try:
        from ..services.image_processor import ImageProcessor, HEIC_SUPPORTED
        services_status["image_processor"] = True
        services_status["heic_support"] = HEIC_SUPPORTED
    except Exception as e:
        logger.error(f"Image processor health check failed: {e}")
        services_status["image_processor"] = False
    
    # Determine overall status
    all_healthy = all([
        services_status.get("gemini", False),
        services_status.get("tcg_api", False),
        services_status.get("image_processor", False),
    ])
    
    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        version="1.0.0",
        services=services_status,
    )


@router.get("/ready")
async def readiness_check():
    """
    Simple readiness check for container orchestration.
    
    Returns 200 if the service is ready to accept requests.
    """
    return {"ready": True}