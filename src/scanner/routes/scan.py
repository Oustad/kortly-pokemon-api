"""Main card scanning endpoint for Pokemon card scanner."""

import base64
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..models.schemas import (
    CostInfo,
    ErrorResponse,
    GeminiAnalysis,
    PokemonCard,
    ProcessingInfo,
    ScanRequest,
    ScanResponse,
)
from ..services.gemini_service import GeminiService
from ..services.image_processor import ImageProcessor
from ..services.tcg_client import PokemonTcgClient
from ..utils.cost_tracker import CostTracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["scanner"])


def save_processed_image(image_data: bytes, original_filename: str, stage: str = "processed") -> Optional[str]:
    """
    Save processed image to disk for testing and debugging purposes.
    
    Args:
        image_data: The image data as bytes
        original_filename: Original filename for reference
        stage: Stage of processing ("original" or "processed")
        
    Returns:
        Relative path to saved image or None if failed
    """
    try:
        # Create processed_images directory if it doesn't exist
        processed_dir = Path("processed_images")
        processed_dir.mkdir(exist_ok=True)
        
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Remove last 3 microsecond digits
        
        # Create filename
        name_without_ext = Path(original_filename).stem if original_filename else "image"
        extension = ".jpg"  # Always save as JPEG since we process to JPEG
        filename = f"{name_without_ext}_{stage}_{timestamp}{extension}"
        
        # Full path
        file_path = processed_dir / filename
        
        # Save the image
        with open(file_path, "wb") as f:
            f.write(image_data)
        
        logger.info(f"💾 Saved {stage} image: {file_path}")
        return str(file_path)
        
    except Exception as e:
        logger.error(f"❌ Failed to save {stage} image: {str(e)}")
        return None


def parse_gemini_response(gemini_response: str) -> Dict[str, Any]:
    """
    Parse Gemini's response to extract structured TCG search parameters.
    
    Args:
        gemini_response: Raw text response from Gemini with TCG_SEARCH_START/END markers
        
    Returns:
        Dictionary with parsed search parameters
    """
    # First try to extract structured JSON from TCG_SEARCH markers
    tcg_pattern = r'TCG_SEARCH_START\s*(\{.*?\})\s*TCG_SEARCH_END'
    match = re.search(tcg_pattern, gemini_response, re.DOTALL | re.IGNORECASE)
    
    if match:
        try:
            json_str = match.group(1).strip()
            # Clean up any potential issues with the JSON
            json_str = re.sub(r'[\n\r\t]', ' ', json_str)  # Remove newlines/tabs
            json_str = re.sub(r'\s+', ' ', json_str)       # Normalize whitespace
            
            search_params = json.loads(json_str)
            
            # Clean up the extracted parameters
            cleaned_params = {}
            
            # Clean name
            if 'name' in search_params and search_params['name']:
                name = str(search_params['name']).strip()
                # Remove common artifacts
                name = re.sub(r'\s*\(.*?\)', '', name)  # Remove parentheses
                name = re.sub(r'[^\w\s-]', '', name)   # Remove special chars except dash
                name = name.strip()
                if name and len(name) > 1:
                    cleaned_params['name'] = name
            
            # Clean set_name
            if 'set_name' in search_params and search_params['set_name']:
                set_name = str(search_params['set_name']).strip()
                if set_name and set_name.lower() not in ['unknown', 'n/a', 'not visible']:
                    cleaned_params['set_name'] = set_name
            
            # Clean number
            if 'number' in search_params and search_params['number']:
                number = str(search_params['number']).strip()
                # Extract just digits
                number_match = re.search(r'(\d+)', number)
                if number_match:
                    cleaned_params['number'] = number_match.group(1)
            
            # Clean HP
            if 'hp' in search_params and search_params['hp']:
                hp = str(search_params['hp']).strip()
                # Extract just digits
                hp_match = re.search(r'(\d+)', hp)
                if hp_match:
                    cleaned_params['hp'] = hp_match.group(1)
            
            # Clean types
            if 'types' in search_params and search_params['types']:
                types = search_params['types']
                if isinstance(types, list):
                    valid_types = []
                    known_types = [
                        'Fire', 'Water', 'Grass', 'Electric', 'Psychic', 'Fighting',
                        'Dark', 'Metal', 'Fairy', 'Dragon', 'Normal', 'Flying',
                        'Bug', 'Rock', 'Ghost', 'Ice', 'Steel', 'Poison', 'Ground'
                    ]
                    for ptype in types:
                        ptype_clean = str(ptype).strip().title()
                        if ptype_clean in known_types:
                            valid_types.append(ptype_clean)
                    if valid_types:
                        cleaned_params['types'] = valid_types[:2]  # Limit to 2 types
            
            # Add supertype if not present
            if 'supertype' in search_params:
                cleaned_params['supertype'] = search_params['supertype']
            
            logger.info(f"✅ Extracted structured TCG search parameters: {cleaned_params}")
            return cleaned_params
            
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Failed to parse structured JSON from Gemini: {e}")
    
    # Fallback to regex parsing if structured format fails
    logger.info("🔄 Falling back to regex parsing...")
    search_params = {}
    
    # Extract Pokemon name (most important)
    name_patterns = [
        r"(?:Name|Pokemon|Card):\s*([^\n\r]+)",
        r"1\.\s*([^\n\r]+)",
        r"Pokemon name:\s*([^\n\r]+)"
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, gemini_response, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            # Clean up common artifacts
            name = re.sub(r'\s*\(.*?\)', '', name)  # Remove parentheses
            name = re.sub(r'[^\w\s-]', '', name)   # Remove special chars except dash
            name = name.strip()
            if name and len(name) > 2:
                search_params['name'] = name
                break
    
    logger.info(f"📋 Fallback extracted TCG search parameters: {search_params}")
    return search_params


@router.post("/scan", response_model=ScanResponse, responses={500: {"model": ErrorResponse}})
async def scan_pokemon_card(request: ScanRequest):
    """
    Scan a Pokemon card image and identify it.
    
    This endpoint:
    1. Processes the image for optimal analysis
    2. Uses Gemini AI to identify the card
    3. Searches the Pokemon TCG database for matches
    4. Returns comprehensive card information
    
    The entire process typically takes 1-2 seconds and costs ~$0.003 per scan.
    """
    start_time = time.time()
    
    # Initialize services
    gemini_service = GeminiService()
    tcg_client = PokemonTcgClient()
    image_processor = ImageProcessor()
    cost_tracker = CostTracker()
    
    # Initialize processing info
    processing_info = {
        "image_processing": {},
        "gemini_processing": {},
        "tcg_search": {},
        "total_time_ms": 0,
    }
    
    try:
        # Decode base64 image
        try:
            image_data = base64.b64decode(request.image)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 image data: {str(e)}")
        
        logger.info(f"🔍 Starting card scan for {request.filename or 'uploaded image'}")
        
        # Save original image for testing
        original_path = save_processed_image(image_data, request.filename or "image", "original")
        
        # Step 1: Process image
        image_start = time.time()
        processed_data, image_info = image_processor.process_image(
            image_data,
            filename=request.filename or "",
        )
        image_time = (time.time() - image_start) * 1000
        
        # Save processed image for testing
        processed_path = save_processed_image(processed_data, request.filename or "image", "processed")
        
        processing_info["image_processing"] = {
            **image_info,
            "processing_time_ms": int(image_time),
            "original_path": original_path,
            "processed_path": processed_path,
        }
        
        # Step 2: Identify card with Gemini
        logger.info("🤖 Identifying card with Gemini AI...")
        gemini_start = time.time()
        
        gemini_result = await gemini_service.identify_pokemon_card(
            processed_data,
            optimize_for_speed=request.options.optimize_for_speed,
            retry_unlimited=request.options.retry_on_truncation,
        )
        
        gemini_time = (time.time() - gemini_start) * 1000
        processing_info["gemini_processing"] = {
            "processing_time_ms": int(gemini_time),
            "truncated": gemini_result.get("truncated", False),
            "finish_reason": gemini_result.get("finish_reason"),
        }
        
        if not gemini_result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Gemini analysis failed: {gemini_result.get('error')}",
            )
        
        # Track Gemini cost
        if request.options.include_cost_tracking:
            gemini_cost = cost_tracker.track_gemini_usage(
                prompt_tokens=gemini_result.get("prompt_tokens", 0),
                response_tokens=gemini_result.get("response_tokens", 0),
                includes_image=True,
                operation="identify_card",
            )
        
        # Parse Gemini response
        parsed_data = parse_gemini_response(gemini_result["response"])
        
        # Create Gemini analysis object
        gemini_analysis = GeminiAnalysis(
            raw_response=gemini_result["response"],
            structured_data=parsed_data,
            confidence=0.9 if parsed_data.get("name") else 0.5,
            tokens_used={
                "prompt": gemini_result.get("prompt_tokens", 0),
                "response": gemini_result.get("response_tokens", 0),
            },
        )
        
        # Step 3: Search TCG database
        logger.info("🎯 Searching Pokemon TCG database...")
        tcg_start = time.time()
        
        tcg_matches = []
        if parsed_data.get("name"):
            # Try exact match first
            tcg_results = await tcg_client.search_cards(
                name=parsed_data["name"],
                set_name=parsed_data.get("set_name"),
                number=parsed_data.get("number"),
                hp=parsed_data.get("hp"),
                types=parsed_data.get("types"),
                page_size=10,
                fuzzy=False,
            )
            
            # If no exact matches, try fuzzy search
            if not tcg_results.get("data"):
                logger.info("🔄 No exact matches, trying fuzzy search...")
                tcg_results = await tcg_client.search_cards(
                    name=parsed_data["name"],
                    set_name=parsed_data.get("set_name"),
                    page_size=10,
                    fuzzy=True,
                )
            
            # Convert to PokemonCard objects
            for card_data in tcg_results.get("data", []):
                tcg_matches.append(PokemonCard(
                    id=card_data["id"],
                    name=card_data["name"],
                    set_name=card_data.get("set", {}).get("name"),
                    number=card_data.get("number"),
                    types=card_data.get("types"),
                    hp=card_data.get("hp"),
                    rarity=card_data.get("rarity"),
                    images=card_data.get("images"),
                    market_prices=card_data.get("tcgplayer", {}).get("prices") if card_data.get("tcgplayer") else None,
                ))
            
            # Track TCG usage
            if request.options.include_cost_tracking:
                cost_tracker.track_tcg_usage("search")
        
        tcg_time = (time.time() - tcg_start) * 1000
        processing_info["tcg_search"] = {
            "processing_time_ms": int(tcg_time),
            "query": parsed_data,
            "matches_found": len(tcg_matches),
        }
        
        # Calculate total time
        total_time = (time.time() - start_time) * 1000
        processing_info["total_time_ms"] = int(total_time)
        
        # Prepare cost info
        cost_info = None
        if request.options.include_cost_tracking:
            session_summary = cost_tracker.get_session_summary()
            cost_info = CostInfo(
                gemini_cost=gemini_cost,
                total_cost=gemini_cost,  # TCG API is free
                cost_breakdown={
                    "gemini_image": CostTracker.GEMINI_COSTS["image_processing"],
                    "gemini_tokens": gemini_cost - CostTracker.GEMINI_COSTS["image_processing"],
                    "tcg_api": 0.0,
                },
            )
        
        # Prepare response
        response = ScanResponse(
            success=True,
            card_identification=gemini_analysis,
            tcg_matches=tcg_matches if tcg_matches else None,
            best_match=tcg_matches[0] if tcg_matches else None,
            processing_info=ProcessingInfo(**processing_info),
            cost_info=cost_info,
        )
        
        logger.info(
            f"✅ Scan complete in {total_time:.0f}ms"
            f"{f', cost: ${gemini_cost:.6f}' if cost_info else ''}"
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Card scan failed: {str(e)}")
        
        # Calculate total time even on error
        total_time = (time.time() - start_time) * 1000
        processing_info["total_time_ms"] = int(total_time)
        
        return ScanResponse(
            success=False,
            error=str(e),
            processing_info=ProcessingInfo(**processing_info),
        )


@router.get("/processed-images/list")
async def list_processed_images():
    """
    List all processed images for testing purposes.
    
    Returns a list of available processed images with metadata.
    """
    try:
        processed_dir = Path("processed_images")
        if not processed_dir.exists():
            return {"images": []}
        
        images = []
        for image_file in processed_dir.glob("*.jpg"):
            try:
                stat = image_file.stat()
                # Parse filename to extract info
                parts = image_file.stem.split('_')
                if len(parts) >= 3:
                    name = '_'.join(parts[:-2])  # Everything except stage and timestamp
                    stage = parts[-2]
                    timestamp = parts[-1]
                else:
                    name = image_file.stem
                    stage = "unknown"
                    timestamp = ""
                
                images.append({
                    "filename": image_file.name,
                    "path": str(image_file),
                    "url": f"/api/v1/processed-images/{image_file.name}",
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "stage": stage,
                    "original_name": name,
                    "timestamp": timestamp,
                })
            except Exception as e:
                logger.warning(f"Error processing image file {image_file}: {e}")
                continue
        
        # Sort by modification time, newest first
        images.sort(key=lambda x: x["modified"], reverse=True)
        
        return {"images": images}
        
    except Exception as e:
        logger.error(f"Error listing processed images: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/processed-images/{filename}")
async def get_processed_image(filename: str):
    """
    Serve a processed image file.
    
    Args:
        filename: Name of the image file to serve
        
    Returns:
        The image file
    """
    try:
        processed_dir = Path("processed_images")
        file_path = processed_dir / filename
        
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="Image not found")
        
        # Verify it's actually an image file
        if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            raise HTTPException(status_code=400, detail="Invalid image file type")
        
        return FileResponse(
            path=str(file_path),
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=3600"}  # Cache for 1 hour
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving image {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))