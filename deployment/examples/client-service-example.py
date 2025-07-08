"""
Example client service showing how to call the internal Pokemon Card Scanner microservice.

This example demonstrates calling the Pokemon Card Scanner from another Google Cloud service
with proper authentication using Google Cloud identity tokens.
"""

import os
import asyncio
import logging
from typing import Optional

import google.auth.transport.requests
import google.oauth2.id_token
import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pokemon Card Scanner service configuration
POKEMON_SCANNER_URL = os.getenv(
    "POKEMON_SCANNER_URL", 
    "https://pokemon-card-scanner-abc123-uc.a.run.app"
)

app = FastAPI(title="Pokemon Scanner Client Example")


class PokemonScannerClient:
    """Client for calling the internal Pokemon Card Scanner microservice."""
    
    def __init__(self, service_url: str):
        self.service_url = service_url
        self.auth_request = google.auth.transport.requests.Request()
    
    async def get_identity_token(self) -> str:
        """Get Google Cloud identity token for service-to-service authentication."""
        try:
            # Get identity token with the target service URL as audience
            token = google.oauth2.id_token.fetch_id_token(
                self.auth_request, 
                self.service_url
            )
            return token
        except Exception as e:
            logger.error(f"Failed to get identity token: {e}")
            raise HTTPException(
                status_code=500, 
                detail="Authentication failed - unable to get service identity token"
            )
    
    async def scan_card(self, image_data: bytes, filename: str) -> dict:
        """
        Send card image to Pokemon Card Scanner microservice.
        
        Args:
            image_data: Raw image bytes
            filename: Original filename
            
        Returns:
            Scan result dictionary
        """
        try:
            # Get authentication token
            token = await self.get_identity_token()
            
            # Prepare headers with authorization
            headers = {
                "Authorization": f"Bearer {token}"
            }
            
            # Prepare files for multipart upload
            files = {
                "image": (filename, image_data, "image/jpeg")
            }
            
            # Make async HTTP request to internal service
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.service_url}/api/v1/scan",
                    headers=headers,
                    files=files
                )
                
                if response.status_code != 200:
                    logger.error(f"Scanner service error: {response.status_code} - {response.text}")
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Pokemon scanner service error: {response.text}"
                    )
                
                return response.json()
                
        except httpx.TimeoutException:
            logger.error("Request to Pokemon scanner service timed out")
            raise HTTPException(
                status_code=504,
                detail="Pokemon scanner service timeout"
            )
        except Exception as e:
            logger.error(f"Error calling Pokemon scanner service: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Internal service communication error: {str(e)}"
            )
    
    async def health_check(self) -> dict:
        """Check health of the Pokemon Card Scanner service."""
        try:
            token = await self.get_identity_token()
            headers = {"Authorization": f"Bearer {token}"}
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.service_url}/api/v1/health",
                    headers=headers
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"status": "unhealthy", "error": response.text}
                    
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}


# Initialize client
scanner_client = PokemonScannerClient(POKEMON_SCANNER_URL)


@app.post("/scan-pokemon-card")
async def scan_pokemon_card(image: UploadFile = File(...)):
    """
    Endpoint that accepts an image upload and forwards it to the internal 
    Pokemon Card Scanner microservice.
    """
    # Validate file type
    if not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400, 
            detail="File must be an image"
        )
    
    # Read image data
    image_data = await image.read()
    
    # Forward to internal scanner service
    result = await scanner_client.scan_card(image_data, image.filename)
    
    return {
        "status": "success",
        "scanner_result": result,
        "original_filename": image.filename
    }


@app.get("/scanner-health")
async def check_scanner_health():
    """Check the health of the internal Pokemon Card Scanner service."""
    health_result = await scanner_client.health_check()
    return {
        "pokemon_scanner_health": health_result,
        "client_service": "healthy"
    }


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Pokemon Scanner Client Example",
        "description": "Example service showing how to call internal Pokemon Card Scanner",
        "pokemon_scanner_url": POKEMON_SCANNER_URL,
        "endpoints": {
            "scan": "/scan-pokemon-card",
            "health": "/scanner-health"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)