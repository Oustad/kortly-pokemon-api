"""API client for testing the Pokemon card scanner."""

import asyncio
import time
from typing import Dict, Any, Optional
import aiohttp
import json


class ScannerAPIClient:
    """Client for calling the Pokemon card scanner API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.scan_endpoint = f"{self.base_url}/api/v1/scan"
        self.health_endpoint = f"{self.base_url}/api/v1/health"
        
    async def check_health(self) -> bool:
        """
        Check if the API server is running and healthy.
        
        Returns:
            True if server is healthy, False otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.health_endpoint, timeout=5) as response:
                    return response.status == 200
        except Exception:
            return False
    
    async def scan_card(
        self, 
        image_base64: str, 
        filename: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Scan a Pokemon card using the API.
        
        Args:
            image_base64: Base64 encoded image data
            filename: Original filename for context
            options: Additional scan options
            
        Returns:
            API response as dictionary
        """
        request_data = {
            "image": image_base64,
            "filename": filename,
            "options": options or {
                "optimize_for_speed": True,
                "include_cost_tracking": True,
                "retry_on_truncation": True
            }
        }
        
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.scan_endpoint,
                    json=request_data,
                    timeout=aiohttp.ClientTimeout(total=60)  # 60 second timeout
                ) as response:
                    response_data = await response.json()
                    processing_time = (time.time() - start_time) * 1000
                    
                    # Add timing information
                    response_data["_test_metadata"] = {
                        "request_time_ms": processing_time,
                        "status_code": response.status,
                        "success": response.status == 200
                    }
                    
                    return response_data
                    
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Request timed out after 60 seconds",
                "_test_metadata": {
                    "request_time_ms": (time.time() - start_time) * 1000,
                    "status_code": 408,
                    "success": False
                }
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Request failed: {str(e)}",
                "_test_metadata": {
                    "request_time_ms": (time.time() - start_time) * 1000,
                    "status_code": 0,
                    "success": False
                }
            }
    
    async def scan_multiple(
        self, 
        image_data_list: list,
        max_concurrent: int = 3
    ) -> list:
        """
        Scan multiple images with controlled concurrency.
        
        Args:
            image_data_list: List of (image_base64, filename) tuples
            max_concurrent: Maximum concurrent requests
            
        Returns:
            List of API responses
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scan_with_semaphore(image_base64: str, filename: str):
            async with semaphore:
                return await self.scan_card(image_base64, filename)
        
        tasks = [
            scan_with_semaphore(image_base64, filename)
            for image_base64, filename in image_data_list
        ]
        
        return await asyncio.gather(*tasks, return_exceptions=True)