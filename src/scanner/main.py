"""Main FastAPI application for Pokemon card scanner."""

import logging
import logging.config
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_config
from .middleware.security import RateLimitMiddleware, SecurityHeadersMiddleware
from .routes import health, metrics, scan
from .services.webhook_service import send_error_webhook

load_dotenv()
config = get_config()
logging.config.dictConfig(config.get_log_config())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    logger.info("🚀 Starting Pokemon Card Scanner API...")
    
    # Verify configuration including API keys
    try:
        config.validate(require_api_key=True)
        logger.info(f"✅ Configuration validated (Environment: {config.environment})")
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        raise
    
    yield
    
    logger.info("👋 Shutting down Pokemon Card Scanner API...")


app = FastAPI(
    title="Pokemon Card Scanner API",
    description="Production-ready Pokemon card scanner using Gemini AI and Pokemon TCG API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if config.enable_api_docs else None,
    redoc_url="/redoc" if config.enable_api_docs else None,
    openapi_url="/openapi.json" if config.enable_api_docs else None,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    import traceback
    
    error_message = f"Unhandled exception: {str(exc)}"
    error_traceback = traceback.format_exc()
    
    logger.error(f"❌ {error_message}")
    logger.debug(error_traceback)
    
    # Send webhook notification
    await send_error_webhook(
        error_message=error_message,
        level="CRITICAL",
        endpoint=str(request.url.path),
        user_agent=request.headers.get("user-agent"),
        traceback=error_traceback,
        context={
            "method": request.method,
            "url": str(request.url),
            "client_ip": request.client.host if request.client else None,
        },
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if config.debug else "An unexpected error occurred",
        },
    )

app.include_router(health.router)
app.include_router(scan.router)
app.include_router(metrics.router)



@app.get("/api/v1/info")
async def api_info():
    """Get API information."""
    return {
        "name": "Pokemon Card Scanner API",
        "version": "1.0.0",
        "description": "Scan Pokemon cards with AI-powered identification",
        "endpoints": {
            "scan": "/api/v1/scan",
            "health": "/api/v1/health",
            "docs": "/docs" if config.enable_api_docs else None,
            "redoc": "/redoc" if config.enable_api_docs else None,
        },
        "features": [
            "HEIC/JPEG/PNG image support",
            "Gemini 2.5 Flash AI identification",
            "Pokemon TCG database integration",
            "Real-time cost tracking",
            "Sub-2-second processing",
        ],
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.scanner.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_config=config.get_log_config(),
    )