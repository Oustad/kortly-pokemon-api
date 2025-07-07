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
    MatchScore,
    PokemonCard,
    ProcessingInfo,
    QualityFeedback,
    ScanRequest,
    ScanResponse,
    SimplifiedScanResponse,
)
from ..services.card_matcher import (
    calculate_match_score_detailed,
    correct_set_based_on_number_pattern,
    correct_xy_set_based_on_number,
    extract_set_name_from_symbol,
    get_set_family,
    is_pokemon_variant_match,
    is_xy_family_match,
    select_best_match,
)
from ..services.response_parser import (
    contains_vague_indicators,
    create_simplified_response,
    parse_gemini_response,
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

# Constants
MINIMUM_SCORE_THRESHOLD = 750  # Cards below this score are likely wrong matches


# _get_set_family function moved to card_matcher service


# _is_xy_family_match function moved to card_matcher service


# _get_set_from_total_count function moved to card_matcher service


# _correct_set_based_on_number_pattern function moved to card_matcher service


# _correct_xy_set_based_on_number function moved to card_matcher service


# _extract_set_name_from_symbol function moved to card_matcher service


def is_valid_set_name(set_name: Optional[str]) -> bool:
    """
    Check if set name is valid for TCG API query.
    
    Args:
        set_name: Set name from Gemini output
        
    Returns:
        True if valid for API query, False otherwise
    """
    if not set_name or not isinstance(set_name, str):
        return False
    
    # Invalid phrases that indicate Gemini couldn't identify the set
    invalid_phrases = [
        "not visible", "likely", "but", "era", "possibly", "unknown",
        "can't see", "cannot see", "unclear", "maybe", "appears to be",
        "looks like", "seems like", "hard to tell", "difficult to see"
    ]
    
    set_lower = set_name.lower()
    
    # Check for invalid phrases
    if any(phrase in set_lower for phrase in invalid_phrases):
        return False
    
    # Check for overly long descriptions (real set names are typically < 50 chars)
    if len(set_name) > 50:
        return False
    
    # Check for commas (indicates descriptive text)
    if "," in set_name:
        return False
    
    return True


def is_valid_card_number(number: Optional[str]) -> bool:
    """
    Check if card number is valid for TCG API query.
    
    Args:
        number: Card number from Gemini output
        
    Returns:
        True if valid for API query, False otherwise
    """
    if not number or not isinstance(number, str):
        return False
    
    # Remove whitespace
    number = number.strip()
    
    # Invalid phrases that indicate Gemini couldn't identify the number
    invalid_phrases = [
        "not visible", "unknown", "unclear", "can't see", "cannot see",
        "hard to tell", "difficult", "n/a", "none", "not found"
    ]
    
    number_lower = number.lower()
    
    # Check for invalid phrases
    if any(phrase in number_lower for phrase in invalid_phrases):
        return False
    
    # Check for spaces in the middle (indicates descriptive text)
    if " " in number:
        return False
    
    # Allow alphanumeric with optional letters (e.g., "123", "SV001", "177a", "TG12")
    # Also allow hyphens for promos (e.g., "SWSH001", "XY-P001")
    if not re.match(r'^[A-Za-z0-9\-]+$', number):
        return False
    
    # Must have at least one digit
    if not any(c.isdigit() for c in number):
        return False
    
    return True


# _is_pokemon_variant_match function moved to card_matcher service


# contains_vague_indicators function moved to response_parser service




# calculate_match_score function moved to card_matcher service

# calculate_match_score function moved to card_matcher service


# calculate_match_score_detailed function moved to card_matcher service

# calculate_match_score_detailed function moved to card_matcher service


# select_best_match function moved to card_matcher service


# create_simplified_response function moved to response_parser service


# parse_gemini_response function moved to response_parser service


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
            error_message = pipeline_result.get('error', 'Processing pipeline failed')
            error_detail = {
                "message": error_message,
                "error_type": "image_quality" if "quality too low" in error_message.lower() else "processing_failed",
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
        
        # Log the extracted parameters for debugging
        logger.info(f"🎯 Extracted TCG search parameters from Gemini:")
        logger.info(f"   📛 Name: '{parsed_data.get('name')}'")
        logger.info(f"   🏷️ Set: '{parsed_data.get('set_name')}'")
        logger.info(f"   🔢 Number: '{parsed_data.get('number')}'")
        if parsed_data.get('set_size'):
            logger.info(f"   📊 Set Size: {parsed_data.get('set_size')} cards")
        logger.info(f"   ❤️ HP: '{parsed_data.get('hp')}'")
        logger.info(f"   🎨 Types: {parsed_data.get('types')}")
        
        # Check authenticity score to filter out non-TCG Pokemon cards (prioritize over vague indicators)
        authenticity_score = parsed_data.get('authenticity_info', {}).get('authenticity_score', 100)
        if authenticity_score is not None and authenticity_score < 60:
            logger.warning(f"⚠️ Low authenticity score ({authenticity_score}) - likely non-TCG Pokemon card")
            
            # Get quality score from pipeline if available
            quality_score = 0
            if 'processing' in pipeline_result:
                quality_score = float(pipeline_result['processing'].get('quality_score', 0))
            
            # Create quality feedback for non-TCG cards
            quality_feedback = QualityFeedback(
                overall="poor",
                issues=[
                    "This appears to be a Pokemon card but not an official TCG card",
                    "Possible sticker, collectible, or fan-made card detected"
                ],
                suggestions=[
                    "Ensure you're scanning an official Pokemon Trading Card Game card",
                    "Check for proper TCG formatting and official set symbols",
                    "Avoid stickers, collectibles, or promotional items"
                ]
            )
            
            error_detail = {
                "message": "This appears to be a Pokemon-related item but not an official TCG card. Please scan an official Pokemon Trading Card Game card.",
                "error_type": "non_tcg_card",
                "quality_feedback": quality_feedback.dict(),
                "quality_score": quality_score,
                "authenticity_score": authenticity_score
            }
            
            raise HTTPException(
                status_code=400,
                detail=json.dumps(error_detail)
            )
        
        # Check if Gemini response contains vague indicators suggesting poor image quality
        if contains_vague_indicators(parsed_data):
            logger.warning("⚠️ Gemini response contains vague indicators - image quality likely too low")
            
            # Get quality score from pipeline if available
            quality_score = 0
            if 'processing' in pipeline_result:
                quality_score = float(pipeline_result['processing'].get('quality_score', 0))
            
            # Create quality feedback
            quality_feedback = QualityFeedback(
                overall="poor",
                issues=[
                    "Image too blurry to read card details clearly",
                    "Card text and numbers are not legible"
                ],
                suggestions=[
                    "Ensure the card is well-lit with no shadows",
                    "Hold the camera steady and wait for auto-focus",
                    "Try taking the photo from directly above the card",
                    "Clean the camera lens if needed"
                ]
            )
            
            error_detail = {
                "message": "Image quality too low to identify card details. The card text and numbers are not clearly visible.",
                "error_type": "image_quality",
                "quality_feedback": quality_feedback.dict(),
                "quality_score": quality_score
            }
            
            raise HTTPException(
                status_code=400,
                detail=json.dumps(error_detail)
            )
        
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

        # Create authenticity info object
        authenticity_info = None
        if parsed_data.get("authenticity_info"):
            from ..models.schemas import AuthenticityInfo
            authenticity_info = AuthenticityInfo(**parsed_data["authenticity_info"])

        # Create Gemini analysis object
        gemini_analysis = GeminiAnalysis(
            raw_response=gemini_data["response"],
            structured_data=parsed_data,
            card_type_info=card_type_info,
            language_info=language_info,
            authenticity_info=authenticity_info,
            confidence=0.9 if parsed_data.get("name") else 0.5,
            tokens_used={
                "prompt": gemini_data.get("prompt_tokens", 0),
                "response": gemini_data.get("response_tokens", 0),
            },
        )
        
        # Check for foil card certainty threshold filtering
        quality_result = pipeline_result.get('quality_result')
        if quality_result and authenticity_info:
            # Check if foil interference affects card certainty
            foil_assessment = quality_result.get('details', {}).get('foil_assessment')
            if foil_assessment:
                interference_level = foil_assessment.get('interference_level')
                foil_score = foil_assessment.get('foil_interference_score', 0)
                readability_score = authenticity_info.readability_score
                
                # If high foil interference + low readability, route to expected non-identification
                if (interference_level == 'high' and 
                    foil_score > 60 and 
                    readability_score is not None and 
                    readability_score < 50):
                    
                    logger.info(f"🚨 Foil interference threshold exceeded: foil_score={foil_score:.1f}, readability={readability_score}")
                    logger.info("   → Routing to expected non-identification due to foil interference")
                    
                    # Override success to false to prevent wrong matches
                    error_message = "Pokemon card identified but foil interference affects readability - skipping search to prevent wrong matches"
                    
                    # Prepare response with no TCG matches
                    response = ScanResponse(
                        success=False,
                        card_identification=gemini_analysis,
                        tcg_matches=None,
                        all_tcg_matches=None,
                        best_match=None,
                        processing=processing_info,
                        cost_info=None,
                        processed_image_filename=None,
                        error=error_message,
                    )
                    
                    # Return early - don't search TCG database
                    total_time = (time.time() - start_time) * 1000
                    logger.info(f"⚠️ Foil interference scan complete in {total_time:.0f}ms - no TCG search performed")
                    
                    # Return simplified response if requested (default)
                    if request.options.response_format != "detailed":
                        return create_simplified_response(
                            best_match=None,
                            processing_info=processing_info,
                            gemini_analysis=gemini_analysis
                        )
                    
                    return response
        
        # Check for scratch/damage detection - after foil interference check
        # Get quality score from processing info since quality_result is not in pipeline_result
        processing_info_dict = pipeline_result.get('processing', {})
        quality_score = processing_info_dict.get('quality_score', 100)
        
        logger.debug(f"🔍 Scratch detection entry: quality_score={quality_score}, authenticity_info={authenticity_info is not None}")
        if authenticity_info:
            readability_score = authenticity_info.readability_score
            # quality_score already retrieved above from processing_info_dict
            
            logger.debug(f"🔍 Scratch detection check: readability={readability_score}, quality={quality_score}")
            
            # Check if card is too damaged to identify accurately
            if (readability_score is not None and 
                quality_score is not None and 
                readability_score < 75 and 
                quality_score < 60):
                
                logger.debug(f"✅ Initial scratch conditions met: readability {readability_score} < 75, quality {quality_score} < 60")
                
                # Additional check: if card number is incomplete (ends with "/"), it's likely damaged
                card_number = parsed_data.get('number', '')
                has_incomplete_number = card_number.endswith('/')
                
                # Combined confidence score
                combined_confidence = (readability_score + quality_score) / 2
                
                logger.debug(f"🔍 Scratch detection details: card_number='{card_number}', incomplete={has_incomplete_number}, combined_confidence={combined_confidence:.1f}")
                
                if combined_confidence < 65 or (readability_score < 75 and has_incomplete_number):
                    logger.info(f"🚨 SCRATCH DETECTION TRIGGERED: combined_confidence={combined_confidence:.1f} < 65 OR (readability={readability_score} < 75 AND incomplete={has_incomplete_number})")
                    
                    
                    # Override success to false to prevent wrong matches
                    error_message = "Pokemon card appears heavily damaged or scratched - skipping search to prevent incorrect identification"
                    
                    # Create processing info for early return
                    quality_feedback = QualityFeedback(
                        overall="poor",
                        issues=["Card appears heavily damaged or scratched"],
                        suggestions=["Use a card in better condition", "Ensure better lighting and focus"]
                    )
                    
                    processing_info = ProcessingInfo(
                        quality_score=quality_score,
                        quality_feedback=quality_feedback,
                        processing_tier=processing_info_dict.get('processing_tier', 'enhanced'),
                        target_time_ms=processing_info_dict.get('target_time_ms', 0),
                        actual_time_ms=int((time.time() - start_time) * 1000),
                        model_used=processing_info_dict.get('model_used', 'gemini'),
                        image_enhanced=processing_info_dict.get('image_enhanced', True),
                        performance_rating=processing_info_dict.get('performance_rating', 'poor'),
                        timing_breakdown=processing_info_dict.get('timing_breakdown', {})
                    )
                    
                    # Prepare response with no TCG matches
                    response = ScanResponse(
                        success=False,
                        card_identification=gemini_analysis,
                        tcg_matches=None,
                        all_tcg_matches=None,
                        best_match=None,
                        processing=processing_info,
                        cost_info=None,
                        processed_image_filename=None,
                        error=error_message,
                    )
                    
                    # Return early - don't search TCG database
                    total_time = (time.time() - start_time) * 1000
                    logger.info(f"⚠️ Damage detection scan complete in {total_time:.0f}ms - no TCG search performed")
                    
                    # Return simplified response if requested (default)
                    if request.options.response_format != "detailed":
                        return create_simplified_response(
                            best_match=None,
                            processing_info=processing_info,
                            gemini_analysis=gemini_analysis
                        )
                    
                    return response
        
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
        logger.info(f"🔍 Search parameters: name='{parsed_data.get('name')}', set='{parsed_data.get('set_name')}', number='{parsed_data.get('number')}', hp='{parsed_data.get('hp')}'")
        tcg_start = time.time()
        
        # Use API key for production capacity (20,000 requests/day vs 1,000)
        tcg_client = PokemonTcgClient(api_key=config.pokemon_tcg_api_key)
        tcg_matches = []
        search_attempts = []
        best_match_card = None
        all_match_scores = []  # Initialize here so it's always available
        
        if parsed_data.get("name"):
            all_search_results = []  # Collect results from all strategies
            
            # Strategy 1: HIGHEST PRIORITY - Set + Number + Name (exact match)
            # Only run if both set name and number are valid
            if parsed_data.get("set_name") and parsed_data.get("number"):
                set_valid = is_valid_set_name(parsed_data.get("set_name"))
                number_valid = is_valid_card_number(parsed_data.get("number"))
                
                if set_valid and number_valid:
                    logger.info("🎯 Strategy 1: Set + Number + Name (PRIORITY)")
                    logger.info(f"   🔍 Searching for: name='{parsed_data['name']}', set='{parsed_data.get('set_name')}', number='{parsed_data.get('number')}'")
                    strategy1_results = await tcg_client.search_cards(
                        name=parsed_data["name"],
                        set_name=parsed_data.get("set_name"),
                        number=parsed_data.get("number"),
                        page_size=5,
                        fuzzy=False,
                    )
                    if strategy1_results.get("data"):
                        all_search_results.extend(strategy1_results["data"])
                        logger.info(f"✅ Strategy 1 found {len(strategy1_results['data'])} exact matches")
                        for result in strategy1_results["data"][:3]:  # Log first 3 matches
                            logger.info(f"   📄 Found: {result.get('name')} #{result.get('number')} from {result.get('set', {}).get('name')}")
                    else:
                        logger.info("   ❌ Strategy 1: No exact matches found")
                else:
                    logger.info(f"   ⚠️ Strategy 1 skipped: Invalid parameters - Set valid: {set_valid}, Number valid: {number_valid}")
                    if not set_valid:
                        logger.info(f"      Invalid set: '{parsed_data.get('set_name')}'")
                    if not number_valid:
                        logger.info(f"      Invalid number: '{parsed_data.get('number')}'")
                
                if set_valid and number_valid:
                    search_attempts.append({
                        "strategy": "set_number_name_exact",
                        "query": {
                        "name": parsed_data["name"],
                        "set_name": parsed_data.get("set_name"),
                        "number": parsed_data.get("number"),
                    },
                    "results": len(strategy1_results.get("data", [])),
                })
                
                # Strategy 1.25: Cross-set Number + Name (when Gemini gets set wrong but number right)
                if len(all_search_results) == 0 and parsed_data.get("number") and parsed_data.get("name"):
                    # Only run if number is valid
                    if is_valid_card_number(parsed_data.get("number")):
                        logger.info("🔄 Strategy 1.25: Cross-set Number + Name (ignore potentially wrong set)")
                        logger.info(f"   🔍 Searching for: name='{parsed_data['name']}', number='{parsed_data.get('number')}'")
                        strategy1_25_results = await tcg_client.search_cards(
                            name=parsed_data["name"],
                            number=parsed_data.get("number"),
                            page_size=10,
                            fuzzy=False,
                        )
                        if strategy1_25_results.get("data"):
                            new_results = [card for card in strategy1_25_results["data"] 
                                         if not any(existing["id"] == card["id"] for existing in all_search_results)]
                            all_search_results.extend(new_results)
                            logger.info(f"✅ Strategy 1.25 found {len(new_results)} cross-set matches")
                            
                            # Log which set we actually found the card in
                            if new_results:
                                found_set = new_results[0].get("set", {}).get("name", "Unknown")
                                original_set = parsed_data.get("set_name", "Unknown")
                                if found_set != original_set:
                                    logger.info(f"   🎯 Set correction: '{original_set}' → '{found_set}'")
                        else:
                            logger.info("   ❌ Strategy 1.25: No cross-set matches found")
                        
                        search_attempts.append({
                            "strategy": "cross_set_number_name",
                            "query": {
                                "name": parsed_data["name"],
                                "number": parsed_data.get("number"),
                            },
                            "results": len(strategy1_25_results.get("data", [])),
                        })
                    else:
                        logger.info(f"   ⚠️ Strategy 1.25 skipped: Invalid number '{parsed_data.get('number')}'")
                
                # Strategy 1.5: Set Family + Number + Name (for cases like "XY" -> "XY BREAKpoint")
                if len(all_search_results) == 0 and parsed_data.get("set_name") and parsed_data.get("number"):
                    # Check if number is valid before using set family expansion
                    if is_valid_card_number(parsed_data.get("number")):
                        set_family = get_set_family(parsed_data.get("set_name"))
                        if set_family:
                            logger.info(f"🔄 Strategy 1.5: Set Family expansion for '{parsed_data.get('set_name')}'")
                            logger.info(f"   📚 Set family contains: {set_family}")
                            for family_set in set_family:
                                logger.info(f"   🔍 Searching in family set: '{family_set}'")
                                strategy1_5_results = await tcg_client.search_cards(
                                    name=parsed_data["name"],
                                    set_name=family_set,
                                    number=parsed_data.get("number"),
                                    page_size=3,
                                    fuzzy=False,
                                )
                                if strategy1_5_results.get("data"):
                                    new_results = [card for card in strategy1_5_results["data"] 
                                                 if not any(existing["id"] == card["id"] for existing in all_search_results)]
                                    all_search_results.extend(new_results)
                                    logger.info(f"✅ Strategy 1.5 found {len(new_results)} matches in {family_set}")
                                    for result in new_results[:2]:  # Log first 2 matches
                                        logger.info(f"   📄 Found: {result.get('name')} #{result.get('number')} from {result.get('set', {}).get('name')}")
                                else:
                                    logger.info(f"   ❌ No matches in '{family_set}'")
                                
                            search_attempts.append({
                                "strategy": "set_family_number_name",
                                "query": {
                                    "name": parsed_data["name"],
                                    "set_family": set_family,
                                    "number": parsed_data.get("number"),
                                },
                                "results": len([r for r in all_search_results if "strategy1_5" in str(r)]),
                            })
                    else:
                        logger.info(f"   ⚠️ Strategy 1.5 skipped: Invalid number '{parsed_data.get('number')}'")
            
            # Strategy 2: Set + Name (without number constraint)
            if parsed_data.get("set_name"):
                # Only run if set name is valid
                if is_valid_set_name(parsed_data.get("set_name")):
                    logger.info("🔄 Strategy 2: Set + Name (no number)")
                    logger.info(f"   🔍 Searching for: name='{parsed_data['name']}', set='{parsed_data.get('set_name')}'")
                    strategy2_results = await tcg_client.search_cards(
                        name=parsed_data["name"],
                        set_name=parsed_data.get("set_name"),
                        page_size=10,
                        fuzzy=False,
                    )
                    if strategy2_results.get("data"):
                        # Only add if not already found in strategy 1
                        new_results = [card for card in strategy2_results["data"] 
                                     if not any(existing["id"] == card["id"] for existing in all_search_results)]
                        all_search_results.extend(new_results)
                        logger.info(f"✅ Strategy 2 found {len(new_results)} additional matches")
                        for result in new_results[:3]:  # Log first 3 new matches
                            logger.info(f"   📄 Found: {result.get('name')} #{result.get('number')} from {result.get('set', {}).get('name')}")
                    else:
                        logger.info("   ❌ Strategy 2: No set+name matches found")
                    
                    search_attempts.append({
                        "strategy": "set_name_only",
                        "query": {
                            "name": parsed_data["name"],
                            "set_name": parsed_data.get("set_name"),
                        },
                        "results": len(strategy2_results.get("data", [])),
                    })
                else:
                    logger.info(f"   ⚠️ Strategy 2 skipped: Invalid set name '{parsed_data.get('set_name')}'")
            
            # Strategy 3: Name + HP (cross-set search with HP validation)
            if parsed_data.get("hp") and len(all_search_results) < 5:
                logger.info("🔄 Strategy 3: Name + HP (cross-set)")
                strategy3_results = await tcg_client.search_cards(
                    name=parsed_data["name"],
                    hp=parsed_data.get("hp"),
                    page_size=10,
                    fuzzy=False,
                )
                if strategy3_results.get("data"):
                    new_results = [card for card in strategy3_results["data"] 
                                 if not any(existing["id"] == card["id"] for existing in all_search_results)]
                    all_search_results.extend(new_results)
                    logger.info(f"✅ Strategy 3 found {len(new_results)} HP-matching cards")
                
                search_attempts.append({
                    "strategy": "name_hp_cross_set",
                    "query": {
                        "name": parsed_data["name"],
                        "hp": parsed_data.get("hp"),
                    },
                    "results": len(strategy3_results.get("data", [])),
                })
            
            # Strategy 4: Special case for Hidden Fates Shiny Vault numbers
            if parsed_data.get("set_name") == "Hidden Fates" and parsed_data.get("number") and len(all_search_results) < 3:
                logger.info("🔄 Strategy 4: Hidden Fates with SV prefix")
                sv_number = f"SV{parsed_data['number']}"
                strategy4_results = await tcg_client.search_cards(
                    name=parsed_data["name"],
                    set_name=parsed_data.get("set_name"),
                    number=sv_number,
                    page_size=5,
                    fuzzy=False,
                )
                if strategy4_results.get("data"):
                    new_results = [card for card in strategy4_results["data"] 
                                 if not any(existing["id"] == card["id"] for existing in all_search_results)]
                    all_search_results.extend(new_results)
                    logger.info(f"✅ Strategy 4 found {len(new_results)} SV-prefixed cards")
                
                search_attempts.append({
                    "strategy": "hidden_fates_sv_prefix",
                    "query": {
                        "name": parsed_data["name"],
                        "set_name": parsed_data.get("set_name"),
                        "number": sv_number,
                    },
                    "results": len(strategy4_results.get("data", [])),
                })
            
            # Strategy 5: Fallback - Name only (fuzzy search)
            if len(all_search_results) < 5:
                logger.info("🔄 Strategy 5: Fallback name-only (fuzzy)")
                strategy5_results = await tcg_client.search_cards(
                    name=parsed_data["name"],
                    page_size=15,
                    fuzzy=True,
                )
                if strategy5_results.get("data"):
                    new_results = [card for card in strategy5_results["data"] 
                                 if not any(existing["id"] == card["id"] for existing in all_search_results)]
                    all_search_results.extend(new_results[:10])  # Limit fallback results
                    logger.info(f"✅ Strategy 5 found {len(new_results[:10])} fallback matches")
                
                search_attempts.append({
                    "strategy": "fuzzy_name_only_fallback",
                    "query": {
                        "name": parsed_data["name"],
                    },
                    "results": len(strategy5_results.get("data", [])),
                })
            
            # Use combined results
            tcg_results = {"data": all_search_results}
            
            # Log search strategy results
            logger.info(f"📊 Search Strategy Summary:")
            for attempt in search_attempts:
                logger.info(f"   📊 {attempt['strategy']}: {attempt['results']} results")
            
            logger.info(f"🎯 Total combined search results: {len(all_search_results)} cards found")
            if all_search_results:
                logger.info(f"📋 Sample results:")
                for i, result in enumerate(all_search_results[:5]):  # Show first 5
                    logger.info(f"   {i+1}. {result.get('name')} #{result.get('number')} from {result.get('set', {}).get('name')}")
            
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
            
            # Select the best match using intelligent scoring and get all matches
            best_match_data, all_scored_matches = select_best_match(tcg_card_data, parsed_data)
            
            # Check if no good match was found due to low scores
            if best_match_data is None and all_scored_matches:
                highest_score = all_scored_matches[0]["score"] if all_scored_matches else 0
                highest_card = all_scored_matches[0] if all_scored_matches else None
                
                logger.warning(f"❌ Card not found: Highest score {highest_score} below threshold {MINIMUM_SCORE_THRESHOLD}")
                if highest_card:
                    logger.info(f"   📊 Best candidate: {highest_card.get('card_name')} #{highest_card.get('card_number')} from {highest_card.get('set_name')}")
                
                error_detail = {
                    "message": "Card not found: No matching Pokemon cards found in database",
                    "error_type": "card_not_found",
                    "details": {
                        "highest_score": highest_score,
                        "required_score": MINIMUM_SCORE_THRESHOLD,
                        "score_gap": MINIMUM_SCORE_THRESHOLD - highest_score
                    },
                    "suggestions": [
                        "Try a clearer image with better lighting",
                        "Ensure the card is fully visible and centered",
                        "Make sure the image is not blurry or distorted",
                        "Check that it's a Pokemon trading card (not a different card game)"
                    ]
                }
                
                raise HTTPException(
                    status_code=404,
                    detail=json.dumps(error_detail)
                )
            
            best_match_card = None
            logger.info(f"📊 Processing {len(all_scored_matches)} scored matches for detailed response")
            
            # Process all scored matches
            for match_info in all_scored_matches:
                # Create PokemonCard object for this match
                card_data = match_info["card_data"]
                pokemon_card = PokemonCard(
                    id=card_data["id"],
                    name=card_data["name"],
                    set_name=card_data.get("set", {}).get("name"),
                    number=card_data.get("number"),
                    types=card_data.get("types"),
                    hp=card_data.get("hp"),
                    rarity=card_data.get("rarity"),
                    images=card_data.get("images"),
                    market_prices=card_data.get("tcgplayer", {}).get("prices") if card_data.get("tcgplayer") else None,
                )
                
                # Determine confidence level
                score = match_info["score"]
                if score >= 1500:
                    confidence = "high"
                elif score >= 500:
                    confidence = "medium"
                else:
                    confidence = "low"
                
                # Generate human-readable reasoning
                reasoning = []
                breakdown = match_info["score_breakdown"]
                
                # Show combination bonuses first (most important)
                if breakdown.get("set_number_name_triple"):
                    reasoning.append(f"🎯 PERFECT MATCH: Set+Number+Name (+{breakdown['set_number_name_triple']})")
                elif breakdown.get("set_number_combo"):
                    reasoning.append(f"🎯 STRONG MATCH: Set+Number (+{breakdown['set_number_combo']})")
                
                if breakdown.get("name_exact"):
                    reasoning.append(f"Exact name match (+{breakdown['name_exact']})")
                elif breakdown.get("name_partial"):
                    reasoning.append(f"Partial name match (+{breakdown['name_partial']})")
                if breakdown.get("number_exact"):
                    reasoning.append(f"Exact number match (+{breakdown['number_exact']})")
                elif breakdown.get("number_partial"):
                    reasoning.append(f"Partial number match (+{breakdown['number_partial']})")
                if breakdown.get("set_exact"):
                    reasoning.append(f"Exact set match (+{breakdown['set_exact']})")
                elif breakdown.get("set_partial"):
                    reasoning.append(f"Partial set match (+{breakdown['set_partial']})")
                if breakdown.get("hp_match"):
                    reasoning.append(f"HP match (+{breakdown['hp_match']})")
                if breakdown.get("type_matches"):
                    reasoning.append(f"Type matches (+{breakdown['type_matches']})")
                if breakdown.get("shiny_vault_bonus"):
                    reasoning.append(f"Shiny Vault bonus (+{breakdown['shiny_vault_bonus']})")
                if breakdown.get("visual_series_match"):
                    reasoning.append(f"🎨 Series match (+{breakdown['visual_series_match']})")
                if breakdown.get("visual_era_match"):
                    reasoning.append(f"🕰️ Era match (+{breakdown['visual_era_match']})")
                if breakdown.get("visual_foil_match"):
                    reasoning.append(f"✨ Foil match (+{breakdown['visual_foil_match']})")
                if breakdown.get("name_tag_team_penalty"):
                    reasoning.append(f"Tag team penalty ({breakdown['name_tag_team_penalty']})")
                if breakdown.get("number_mismatch_penalty"):
                    reasoning.append(f"❌ WRONG NUMBER ({breakdown['number_mismatch_penalty']})")
                
                match_score = MatchScore(
                    card=pokemon_card,
                    score=score,
                    score_breakdown=breakdown,
                    confidence=confidence,
                    reasoning=reasoning
                )
                all_match_scores.append(match_score)
            
            # Find best match card
            if best_match_data:
                # Find the corresponding PokemonCard object
                for card in tcg_matches:
                    if card.id == best_match_data["id"]:
                        best_match_card = card
                        break
            
            # Track TCG usage
            if request.options.include_cost_tracking and config.enable_cost_tracking:
                cost_tracker.track_tcg_usage("search")
        else:
            logger.info("⚠️ TCG search skipped - no Pokemon name identified")
        
        tcg_time = (time.time() - tcg_start) * 1000
        
        
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
            all_tcg_matches=all_match_scores if all_match_scores else None,
            best_match=best_match_card,
            processing=processing_info,
            cost_info=cost_info,
            processed_image_filename=Path(processed_path).name if processed_path else None,
            error=error_message,
        )
        
        logger.info(f"🔍 Response prepared: tcg_matches={len(tcg_matches) if tcg_matches else 0}, all_tcg_matches={len(all_match_scores) if all_match_scores else 0}")
        
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


