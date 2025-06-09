"""Main FastAPI application for Pokemon card scanner."""

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routes import health, scan

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    logger.info("🚀 Starting Pokemon Card Scanner API...")
    
    # Verify required environment variables
    if not os.getenv("GOOGLE_API_KEY"):
        logger.warning("⚠️ GOOGLE_API_KEY not set. Gemini features will be unavailable.")
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down Pokemon Card Scanner API...")


# Create FastAPI app
app = FastAPI(
    title="Pokemon Card Scanner API",
    description="Production-ready Pokemon card scanner using Gemini AI and Pokemon TCG API",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(scan.router)

# Mount static files for web interface
web_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "web")
if os.path.exists(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    logger.info(f"📁 Serving web interface from {web_dir}")
else:
    logger.warning(f"⚠️ Web directory not found at {web_dir}")


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
            "docs": "/docs",
            "redoc": "/redoc",
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
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    uvicorn.run(
        "src.scanner.main:app",
        host=host,
        port=port,
        reload=True,
    )