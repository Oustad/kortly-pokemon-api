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

from ..config import get_config
from ..models.schemas import (
    CostInfo,
    ErrorResponse,
    GeminiAnalysis,
    PokemonCard,
    ProcessingInfo,
    QualityFeedback,
    ScanRequest,
    ScanResponse,
    SimplifiedScanResponse,
)
from ..services.gemini_service import GeminiService
from ..services.image_processor import ImageProcessor
from ..services.metrics_service import get_metrics_service, RequestMetrics
from ..services.processing_pipeline import ProcessingPipeline
from ..services.tcg_client import PokemonTcgClient
from ..services.webhook_service import send_error_webhook
from ..utils.cost_tracker import CostTracker

logger = logging.getLogger(__name__)
config = get_config()

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


def calculate_match_score(card_data: Dict[str, Any], gemini_params: Dict[str, Any]) -> int:
    """
    Calculate match score for a TCG card based on Gemini parameters.
    
    Args:
        card_data: Card data from TCG API
        gemini_params: Parsed parameters from Gemini
        
    Returns:
        Match score (higher = better match)
    """
    score = 0
    
    # Name matching (very high priority for exact matches)
    if gemini_params.get("name") and card_data.get("name"):
        gemini_name = gemini_params["name"].lower().strip()
        card_name = card_data["name"].lower().strip()
        
        # Exact name match gets highest priority
        if gemini_name == card_name:
            score += 2000  # Very high score for exact name match
        # Penalize tag team cards when searching for single Pokemon
        elif "&" in card_name and "&" not in gemini_name:
            # Card is a tag team but search is for single Pokemon
            if gemini_name in card_name:
                score += 100  # Low score for partial match on tag team
        # Normal partial matches
        elif gemini_name in card_name or card_name in gemini_name:
            score += 300
    
    # Card number match (high priority) - exact match required
    if gemini_params.get("number") and card_data.get("number"):
        gemini_number = str(gemini_params["number"]).strip()
        card_number = str(card_data["number"]).strip()
        
        if gemini_number == card_number:
            score += 1000  # High score for exact number match
        elif gemini_number in card_number or card_number in gemini_number:
            score += 500   # Partial number match (e.g., "60" matches "SV60")
    
    # HP match (high priority)
    if gemini_params.get("hp") and card_data.get("hp"):
        gemini_hp = str(gemini_params["hp"]).strip()
        card_hp = str(card_data["hp"]).strip()
        
        if gemini_hp == card_hp:
            score += 400
    
    # Types match (medium priority)
    card_types = card_data.get("types", [])
    gemini_types = gemini_params.get("types", [])
    if gemini_types and card_types:
        # Count matching types
        matching_types = len([t for t in gemini_types if t in card_types])
        score += matching_types * 100
    
    # Set name match (already handled by search, but good to verify)
    if gemini_params.get("set_name") and card_data.get("set", {}).get("name"):
        gemini_set = gemini_params["set_name"].lower().strip()
        card_set = card_data["set"]["name"].lower().strip()
        
        if gemini_set == card_set:
            score += 200
        elif gemini_set in card_set or card_set in gemini_set:
            score += 100
    
    # Bonus for Shiny Vault cards when appropriate
    if card_data.get("number", "").startswith("SV") and gemini_params.get("set_name") == "Hidden Fates":
        score += 300  # Bonus for Shiny Vault cards from Hidden Fates
    
    return score


def select_best_match(tcg_results: List[Dict[str, Any]], gemini_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Select the best matching card from TCG results based on Gemini parameters.
    
    Args:
        tcg_results: List of card data from TCG API
        gemini_params: Parsed parameters from Gemini
        
    Returns:
        Best matching card data or None
    """
    if not tcg_results:
        return None
    
    best_score = -1
    best_match = None
    match_details = []
    
    for card_data in tcg_results:
        score = calculate_match_score(card_data, gemini_params)
        match_details.append({
            "card_id": card_data.get("id"),
            "card_name": card_data.get("name"),
            "card_number": card_data.get("number"),
            "card_hp": card_data.get("hp"),
            "score": score,
        })
        
        if score > best_score:
            best_score = score
            best_match = card_data
    
    # Log the scoring details for debugging
    logger.info(f"🎯 Best match scoring:")
    for details in sorted(match_details, key=lambda x: x["score"], reverse=True):
        logger.info(f"   {details['card_name']} #{details['card_number']} (ID: {details['card_id']}) - Score: {details['score']}")
    
    if best_match:
        logger.info(f"✅ Selected best match: {best_match.get('name')} #{best_match.get('number')} (Score: {best_score})")
    
    return best_match


def create_simplified_response(
    best_match: Optional[PokemonCard],
    processing_info: ProcessingInfo,
    gemini_analysis: Optional[GeminiAnalysis] = None
) -> SimplifiedScanResponse:
    """Create a simplified response from the scan results."""
    
    # If we have a best match from TCG, use that data
    if best_match:
        # Extract market prices - flatten the structure
        market_prices = None
        if best_match.market_prices:
            market_prices = {}
            # Handle different price structures
            if isinstance(best_match.market_prices, dict):
                # Check for card type variants (normal, holofoil, reverseHolofoil, etc.)
                price_data = None
                
                # Priority order for price variants
                for variant in ['normal', 'holofoil', 'reverseHolofoil', '1stEditionNormal', '1stEditionHolofoil']:
                    if variant in best_match.market_prices:
                        price_data = best_match.market_prices[variant]
                        break
                
                # If no variant found, check for direct price structure
                if not price_data and 'low' in best_match.market_prices:
                    price_data = best_match.market_prices
                
                # Extract prices from the data
                if price_data and isinstance(price_data, dict):
                    market_prices['low'] = price_data.get('low', 0)
                    market_prices['mid'] = price_data.get('mid', 0)
                    market_prices['high'] = price_data.get('high', 0)
                    market_prices['market'] = price_data.get('market', price_data.get('mid', 0))
        
        # Get image URL
        image_url = None
        if best_match.images:
            image_url = best_match.images.get('large') or best_match.images.get('small')
        
        return SimplifiedScanResponse(
            name=best_match.name,
            set_name=best_match.set_name,
            number=best_match.number,
            hp=best_match.hp,
            types=best_match.types,
            rarity=best_match.rarity,
            image=image_url,
            market_prices=market_prices,
            quality_score=processing_info.quality_score
        )
    
    # Fallback to Gemini data if no TCG match
    elif gemini_analysis and gemini_analysis.structured_data:
        data = gemini_analysis.structured_data
        return SimplifiedScanResponse(
            name=data.get('name', 'Unknown'),
            set_name=data.get('set_name'),
            number=data.get('number'),
            hp=data.get('hp'),
            types=data.get('types'),
            rarity=data.get('rarity'),
            image=None,  # No image from Gemini
            market_prices=None,  # No prices without TCG match
            quality_score=processing_info.quality_score
        )
    
    # No data available - this shouldn't happen in normal flow
    raise HTTPException(
        status_code=500,
        detail="No card data available to create response"
    )


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
            
            # Extract card type information (with fallback defaults)
            card_type_info = {}
            if 'card_type' in search_params and search_params['card_type']:
                card_type = str(search_params['card_type']).strip().lower()
                # Validate card type
                valid_types = ['pokemon_front', 'pokemon_back', 'non_pokemon', 'unknown']
                if card_type in valid_types:
                    card_type_info['card_type'] = card_type
                else:
                    card_type_info['card_type'] = 'pokemon_front'  # Default to Pokemon front for safety
            else:
                card_type_info['card_type'] = 'pokemon_front'  # Default assumption
            
            # Extract is_pokemon_card flag
            if 'is_pokemon_card' in search_params:
                is_pokemon = search_params['is_pokemon_card']
                if isinstance(is_pokemon, bool):
                    card_type_info['is_pokemon_card'] = is_pokemon
                elif isinstance(is_pokemon, str):
                    card_type_info['is_pokemon_card'] = is_pokemon.lower() in ['true', '1', 'yes']
                else:
                    card_type_info['is_pokemon_card'] = card_type_info['card_type'] in ['pokemon_front', 'pokemon_back']
            else:
                card_type_info['is_pokemon_card'] = card_type_info['card_type'] in ['pokemon_front', 'pokemon_back']
            
            # Extract card side
            if 'card_side' in search_params and search_params['card_side']:
                card_side = str(search_params['card_side']).strip().lower()
                valid_sides = ['front', 'back', 'unknown']
                if card_side in valid_sides:
                    card_type_info['card_side'] = card_side
                else:
                    card_type_info['card_side'] = 'unknown'
            else:
                # Infer from card_type if not provided
                if card_type_info['card_type'] == 'pokemon_front':
                    card_type_info['card_side'] = 'front'
                elif card_type_info['card_type'] == 'pokemon_back':
                    card_type_info['card_side'] = 'back'
                else:
                    card_type_info['card_side'] = 'unknown'
                    
            cleaned_params['card_type_info'] = card_type_info
            
            # Extract language information
            language_info = {}
            if 'language' in search_params and search_params['language']:
                language_info['detected_language'] = str(search_params['language']).strip().lower()
            else:
                language_info['detected_language'] = 'en'  # Default to English
                
            if 'original_name' in search_params and search_params['original_name']:
                language_info['original_name'] = str(search_params['original_name']).strip()
            
            # Clean name (this may be translated)
            if 'name' in search_params and search_params['name']:
                name = str(search_params['name']).strip()
                # Remove common artifacts
                name = re.sub(r'\s*\(.*?\)', '', name)  # Remove parentheses
                name = re.sub(r'[^\w\s-]', '', name)   # Remove special chars except dash
                name = name.strip()
                if name and len(name) > 1:
                    cleaned_params['name'] = name
                    
                    # Check if translation occurred
                    original_name = language_info.get('original_name', '')
                    if original_name and original_name.lower() != name.lower():
                        language_info['translated_name'] = name
                        language_info['is_translation'] = True
                        language_info['translation_note'] = f"Translated '{original_name}' to '{name}' for database search"
                    else:
                        language_info['is_translation'] = False
                        
            cleaned_params['language_info'] = language_info
            
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
    
    # Add default card type info for fallback parsing
    if search_params:
        search_params['card_type_info'] = {
            'card_type': 'pokemon_front',  # Assume Pokemon front card
            'is_pokemon_card': True,
            'card_side': 'front'
        }
        search_params['language_info'] = {
            'detected_language': 'en',
            'is_translation': False
        }
    
    logger.info(f"📋 Fallback extracted TCG search parameters: {search_params}")
    return search_params


@router.post("/scan", responses={500: {"model": ErrorResponse}})
async def scan_pokemon_card(request: ScanRequest):
    """
    Scan a Pokemon card image and identify it using intelligent processing pipeline.
    
    This endpoint:
    1. Assesses image quality and routes to appropriate processing tier
    2. Uses optimized Gemini AI analysis based on quality score
    3. Searches the Pokemon TCG database for matches
    4. Returns comprehensive card information with quality metrics
    
    Processing time varies by quality: excellent (1s), good (1-2s), poor (2-4s).
    Cost: ~$0.003-0.005 per scan depending on processing tier.
    """
    start_time = time.time()
    cost_tracker = CostTracker()
    
    try:
        # Decode base64 image
        try:
            image_data = base64.b64decode(request.image)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 image data: {str(e)}")
        
        logger.info(f"🔍 Starting intelligent card scan for {request.filename or 'uploaded image'}")
        
        # Save original image for testing
        original_path = save_processed_image(image_data, request.filename or "image", "original")
        
        # Initialize processing pipeline
        gemini_service = GeminiService(api_key=config.google_api_key)
        processing_pipeline = ProcessingPipeline(gemini_service)
        
        # User preferences from request options
        user_preferences = {}
        if request.options.prefer_speed is not None:
            user_preferences['prefer_speed'] = request.options.prefer_speed
        if request.options.prefer_quality is not None:
            user_preferences['prefer_quality'] = request.options.prefer_quality
        if request.options.max_processing_time is not None:
            user_preferences['max_processing_time'] = request.options.max_processing_time
        
        # Run through processing pipeline
        pipeline_result = await processing_pipeline.process_image(
            image_data,
            request.filename or "image",
            user_preferences if user_preferences else None
        )
        
        if not pipeline_result['success']:
            # Extract quality feedback from pipeline error result
            quality_feedback = None
            if 'processing' in pipeline_result and 'quality_feedback' in pipeline_result['processing']:
                quality_feedback = pipeline_result['processing']['quality_feedback']
            
            # Return user-friendly error with quality feedback
            error_detail = {
                "message": pipeline_result.get('error', 'Processing pipeline failed'),
            }
            
            if quality_feedback:
                error_detail["quality_feedback"] = quality_feedback
            
            raise HTTPException(
                status_code=400 if "quality too low" in pipeline_result.get('error', '').lower() else 500,
                detail=json.dumps(error_detail),
            )
        
        # Extract Gemini result and parse for TCG search
        gemini_data = pipeline_result.get('card_data')
        if not gemini_data:
            raise HTTPException(
                status_code=500,
                detail="Processing pipeline did not return card data",
            )
        
        # Check if Gemini processing was successful
        if not gemini_data.get('success', False):
            raise HTTPException(
                status_code=500,
                detail=f"Gemini processing failed: {gemini_data.get('error', 'Unknown error')}",
            )
        
        # Ensure response field exists before parsing
        if 'response' not in gemini_data:
            raise HTTPException(
                status_code=500,
                detail="Gemini response missing required data",
            )
        
        parsed_data = parse_gemini_response(gemini_data["response"])
        
        # Create card type info object
        card_type_info = None
        if parsed_data.get("card_type_info"):
            from ..models.schemas import CardTypeInfo
            card_type_info = CardTypeInfo(**parsed_data["card_type_info"])
            
        # Create language info object
        language_info = None
        if parsed_data.get("language_info"):
            from ..models.schemas import LanguageInfo
            language_info = LanguageInfo(**parsed_data["language_info"])

        # Create Gemini analysis object
        gemini_analysis = GeminiAnalysis(
            raw_response=gemini_data["response"],
            structured_data=parsed_data,
            card_type_info=card_type_info,
            language_info=language_info,
            confidence=0.9 if parsed_data.get("name") else 0.5,
            tokens_used={
                "prompt": gemini_data.get("prompt_tokens", 0),
                "response": gemini_data.get("response_tokens", 0),
            },
        )
        
        # Track Gemini cost
        gemini_cost = 0.0
        if request.options.include_cost_tracking:
            gemini_cost = cost_tracker.track_gemini_usage(
                prompt_tokens=gemini_data.get("prompt_tokens", 0),
                response_tokens=gemini_data.get("response_tokens", 0),
                includes_image=True,
                operation="identify_card",
            )
        
        # Step 3: Search TCG database
        logger.info("🎯 Searching Pokemon TCG database...")
        tcg_start = time.time()
        
        tcg_client = PokemonTcgClient()
        tcg_matches = []
        search_attempts = []
        best_match_card = None
        
        if parsed_data.get("name"):
            # Strategy 1: Try exact match with all parameters
            logger.info("🎯 Strategy 1: Exact search with all parameters")
            tcg_results = await tcg_client.search_cards(
                name=parsed_data["name"],
                set_name=parsed_data.get("set_name"),
                number=parsed_data.get("number"),
                hp=parsed_data.get("hp"),
                types=parsed_data.get("types"),
                page_size=10,
                fuzzy=False,
            )
            search_attempts.append({
                "strategy": "exact_all_params",
                "query": {
                    "name": parsed_data["name"],
                    "set_name": parsed_data.get("set_name"),
                    "number": parsed_data.get("number"),
                    "hp": parsed_data.get("hp"),
                    "types": parsed_data.get("types"),
                },
                "results": len(tcg_results.get("data", [])),
            })
            
            # Strategy 2: If no exact matches, try name + set only
            if not tcg_results.get("data") and parsed_data.get("set_name"):
                logger.info("🔄 Strategy 2: Name + set only")
                tcg_results = await tcg_client.search_cards(
                    name=parsed_data["name"],
                    set_name=parsed_data.get("set_name"),
                    page_size=10,
                    fuzzy=False,
                )
                search_attempts.append({
                    "strategy": "name_set_only",
                    "query": {
                        "name": parsed_data["name"],
                        "set_name": parsed_data.get("set_name"),
                    },
                    "results": len(tcg_results.get("data", [])),
                })
            
            # Strategy 3: If still no matches, try fuzzy search with name + set
            if not tcg_results.get("data") and parsed_data.get("set_name"):
                logger.info("🔄 Strategy 3: Fuzzy search with name + set")
                tcg_results = await tcg_client.search_cards(
                    name=parsed_data["name"],
                    set_name=parsed_data.get("set_name"),
                    page_size=10,
                    fuzzy=True,
                )
                search_attempts.append({
                    "strategy": "fuzzy_name_set",
                    "query": {
                        "name": parsed_data["name"],
                        "set_name": parsed_data.get("set_name"),
                    },
                    "results": len(tcg_results.get("data", [])),
                })
            
            # Strategy 4: Special case for Hidden Fates Shiny Vault numbers
            if not tcg_results.get("data") and parsed_data.get("set_name") == "Hidden Fates" and parsed_data.get("number"):
                logger.info("🔄 Strategy 4: Hidden Fates with SV prefix")
                sv_number = f"SV{parsed_data['number']}"
                tcg_results = await tcg_client.search_cards(
                    name=parsed_data["name"],
                    set_name=parsed_data.get("set_name"),
                    number=sv_number,
                    page_size=10,
                    fuzzy=False,
                )
                search_attempts.append({
                    "strategy": "hidden_fates_sv_prefix",
                    "query": {
                        "name": parsed_data["name"],
                        "set_name": parsed_data.get("set_name"),
                        "number": sv_number,
                    },
                    "results": len(tcg_results.get("data", [])),
                })
            
            # Strategy 5: If still no matches, try fuzzy search with name only
            if not tcg_results.get("data"):
                logger.info("🔄 Strategy 5: Fuzzy search with name only")
                tcg_results = await tcg_client.search_cards(
                    name=parsed_data["name"],
                    page_size=20,  # Increase page size for broader search
                    fuzzy=True,
                )
                search_attempts.append({
                    "strategy": "fuzzy_name_only",
                    "query": {
                        "name": parsed_data["name"],
                    },
                    "results": len(tcg_results.get("data", [])),
                })
            
            # Log search strategy results
            for attempt in search_attempts:
                logger.info(f"   📊 {attempt['strategy']}: {attempt['results']} results")
            
            # Convert to PokemonCard objects and find best match
            tcg_card_data = tcg_results.get("data", [])
            for card_data in tcg_card_data:
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
            
            # Select the best match using intelligent scoring
            best_match_data = select_best_match(tcg_card_data, parsed_data)
            best_match_card = None
            if best_match_data:
                # Find the corresponding PokemonCard object
                for card in tcg_matches:
                    if card.id == best_match_data["id"]:
                        best_match_card = card
                        break
            
            # Track TCG usage
            if request.options.include_cost_tracking and config.enable_cost_tracking:
                cost_tracker.track_tcg_usage("search")
        
        tcg_time = (time.time() - tcg_start) * 1000
        
        # Save processed image for testing
        processed_path = None
        if pipeline_result.get('processed_image_data'):
            processed_path = save_processed_image(
                pipeline_result['processed_image_data'], 
                request.filename or "image", 
                "processed"
            )
        
        # Build comprehensive processing info
        processing_metadata = pipeline_result['processing']
        quality_feedback = QualityFeedback(
            overall=processing_metadata['quality_feedback']['overall'],
            issues=processing_metadata['quality_feedback']['issues'],
            suggestions=processing_metadata['quality_feedback']['suggestions']
        )
        
        processing_info = ProcessingInfo(
            quality_score=processing_metadata['quality_score'],
            quality_feedback=quality_feedback,
            processing_tier=processing_metadata['processing_tier'],
            target_time_ms=processing_metadata['target_time_ms'],
            actual_time_ms=processing_metadata['actual_time_ms'] + tcg_time,  # Include TCG time
            model_used=processing_metadata['model_used'],
            image_enhanced=processing_metadata['image_enhanced'],
            performance_rating=processing_metadata['performance_rating'],
            timing_breakdown={
                **processing_metadata['timing_breakdown'],
                'tcg_search_ms': tcg_time
            },
            processing_log=processing_metadata['processing_log'] + [
                f"TCG search: {tcg_time:.1f}ms",
                f"Found {len(tcg_matches)} matches" if tcg_matches else "No TCG matches found"
            ]
        )
        
        # Prepare cost info
        cost_info = None
        if request.options.include_cost_tracking:
            cost_info = CostInfo(
                gemini_cost=gemini_cost,
                total_cost=gemini_cost,  # TCG API is free
                cost_breakdown={
                    "gemini_image": CostTracker.GEMINI_COSTS["image_processing"],
                    "gemini_tokens": gemini_cost - CostTracker.GEMINI_COSTS["image_processing"],
                    "tcg_api": 0.0,
                },
            )
        
        # Determine success based on card type and results
        scan_success = True
        error_message = None
        
        if card_type_info:
            card_type = card_type_info.card_type
            
            if card_type == "pokemon_front":
                # Pokemon front cards should have TCG matches
                scan_success = best_match_card is not None
                if not scan_success:
                    error_message = "Pokemon card identified but no TCG database matches found"
                    
            elif card_type == "pokemon_back":
                # Card back detected - return user-friendly error
                raise HTTPException(
                    status_code=400,
                    detail=json.dumps({
                        "message": "Card back detected. Please photograph the front of the card.",
                        "quality_feedback": {
                            "overall": processing_info.quality_feedback.overall,
                            "issues": ["Card back detected"],
                            "suggestions": ["Please photograph the front of the card to identify it"]
                        }
                    })
                )
                
            elif card_type == "non_pokemon":
                # Non-Pokemon card detected - return user-friendly error
                raise HTTPException(
                    status_code=400,
                    detail=json.dumps({
                        "message": "Non-Pokemon card detected. This scanner only supports Pokemon TCG cards.",
                        "quality_feedback": {
                            "overall": processing_info.quality_feedback.overall,
                            "issues": ["Non-Pokemon card detected"],
                            "suggestions": ["Please scan a Pokemon TCG card"]
                        }
                    })
                )
                
            elif card_type == "unknown":
                # Unknown cards - consider failed if no data extracted
                scan_success = parsed_data.get("name") is not None
                if not scan_success:
                    error_message = "Could not determine card type or extract card data"
        else:
            # Fallback to original logic if no card type info  
            scan_success = True  # Default to success for now

        # Prepare response
        response = ScanResponse(
            success=scan_success,
            card_identification=gemini_analysis,
            tcg_matches=tcg_matches if tcg_matches else None,
            best_match=best_match_card,
            processing=processing_info,
            cost_info=cost_info,
            error=error_message,
        )
        
        total_time = processing_info.actual_time_ms
        logger.info(
            f"✅ Intelligent scan complete in {total_time:.0f}ms "
            f"(tier: {processing_info.processing_tier}, "
            f"quality: {processing_info.quality_score:.1f})"
            f"{f', cost: ${gemini_cost:.6f}' if cost_info else ''}"
        )
        
        # Record metrics
        metrics_service = get_metrics_service()
        metrics_service.record_request(RequestMetrics(
            timestamp=datetime.now(),
            endpoint="/api/v1/scan",
            method="POST",
            status_code=200,
            processing_time_ms=total_time,
            image_size_bytes=len(image_data),
            gemini_cost=gemini_cost,
            tcg_matches=len(tcg_matches) if tcg_matches else 0,
        ))
        
        # Return simplified response if requested (default)
        if request.options.response_format != "detailed":
            return create_simplified_response(
                best_match=best_match_card,
                processing_info=processing_info,
                gemini_analysis=gemini_analysis
            )
        
        # Return detailed response if explicitly requested
        return response
        
    except HTTPException as e:
        # Log and send webhook for HTTP errors
        error_context = {
            "status_code": e.status_code,
            "filename": request.filename,
            "processing_time_ms": int((time.time() - start_time) * 1000),
        }
        
        # Send webhook notification for critical errors
        if e.status_code >= 500:
            await send_error_webhook(
                error_message=f"HTTP {e.status_code}: {e.detail}",
                level="ERROR",
                endpoint="/api/v1/scan",
                context=error_context,
            )
        
        raise
    except Exception as e:
        logger.error(f"❌ Card scan failed: {str(e)}")
        
        # Calculate total time even on error
        total_time = (time.time() - start_time) * 1000
        
        # Prepare error context
        error_context = {
            "filename": request.filename,
            "processing_time_ms": int(total_time),
            "error_type": type(e).__name__,
        }
        
        # Send webhook notification
        await send_error_webhook(
            error_message=f"Card scan failed: {str(e)}",
            level="ERROR",
            endpoint="/api/v1/scan",
            context=error_context,
            traceback=str(e),
        )
        
        # Record error metrics
        metrics_service = get_metrics_service()
        metrics_service.record_request(RequestMetrics(
            timestamp=datetime.now(),
            endpoint="/api/v1/scan",
            method="POST",
            status_code=500,
            processing_time_ms=total_time,
            image_size_bytes=len(image_data) if 'image_data' in locals() else None,
            error_type=type(e).__name__,
        ))
        
        # Create minimal processing info for error response
        quality_feedback = QualityFeedback(
            overall="unknown",
            issues=["Processing failed"],
            suggestions=["Try uploading a different image"]
        )
        
        processing_info_obj = ProcessingInfo(
            quality_score=0.0,
            quality_feedback=quality_feedback,
            processing_tier="failed",
            target_time_ms=2000,
            actual_time_ms=total_time,
            model_used="none",
            image_enhanced=False,
            performance_rating="failed",
            timing_breakdown={"error_ms": total_time},
            processing_log=[f"Error: {str(e)}"]
        )
        
        return ScanResponse(
            success=False,
            error=str(e),
            processing=processing_info_obj,
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