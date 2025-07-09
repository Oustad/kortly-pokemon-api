"""Main card scanning endpoint for Pokemon card scanner."""

import base64
import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from ..config import get_config
from ..models.schemas import (
    AuthenticityInfo,
    CardTypeInfo,
    CostInfo,
    ErrorResponse,
    GeminiAnalysis,
    LanguageInfo,
    MatchScore,
    PokemonCard,
    ProcessingInfo,
    QualityFeedback,
    ScanRequest,
    ScanResponse,
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
from ..services.error_handler import (
    ErrorType,
    create_image_quality_error,
    create_non_tcg_card_error,
    create_card_back_error,
    create_non_pokemon_card_error,
    create_no_match_error,
    create_service_error,
    raise_pokemon_scanner_error,
    handle_unexpected_error,
)
from ..services.gemini_service import GeminiService
from ..services.image_processor import ImageProcessor
from ..services.metrics_service import get_metrics_service, RequestMetrics
from ..services.processing_pipeline import ProcessingPipeline
from ..services.tcg_client import PokemonTcgClient
from ..services.tcg_search_service import TCGSearchService
from ..services.webhook_service import send_error_webhook
from ..utils.cost_tracker import CostTracker

logger = logging.getLogger(__name__)
config = get_config()

router = APIRouter(prefix="/api/v1", tags=["scanner"])

# Constants
MINIMUM_SCORE_THRESHOLD = 750  # Cards below this score are likely wrong matches


@router.post("/scan", responses={500: {"model": ErrorResponse}})
async def scan_pokemon_card(request: ScanRequest):
    """
    Scan a Pokemon card and return detailed information.

    This endpoint:
    1. Validates and processes the input image
    2. Uses Gemini AI to identify the card
    3. Searches the Pokemon TCG database for matches
    4. Returns the best match with pricing and detailed information

    Args:
        request: The scan request containing image data and options

    Returns:
        ScanResponse with card details, pricing, and match confidence

    Raises:
        HTTPException: Various errors for invalid input or processing failures
    """
    start_time = time.time()

    try:
        logger.info("📸 Processing card scan request...")
        try:
            image_data = base64.b64decode(request.image)
        except Exception as e:
            logger.error(f"Invalid base64 image data: {e}")
            raise HTTPException(status_code=400, detail="Invalid base64 image data")

        logger.debug("🔧 Initializing services...")
        try:
            gemini_service = GeminiService(api_key=config.google_api_key)
        except Exception as e:
            logger.error(f"Failed to initialize Gemini service: {e}")
            error_details = create_service_error(
                service_name="Gemini AI",
                original_error=str(e),
                request_id=None
            )
            raise_pokemon_scanner_error(error_details)

        try:
            pipeline = ProcessingPipeline(gemini_service)
        except Exception as e:
            logger.error(f"Failed to initialize processing pipeline: {e}")
            error_details = create_service_error(
                service_name="processing_pipeline",
                original_error=str(e),
                request_id=None
            )
            raise_pokemon_scanner_error(error_details)

        cost_tracker = None
        if request.options.include_cost_tracking and config.enable_cost_tracking:
            cost_tracker = CostTracker()

        logger.info("🎨 Processing image through AI pipeline...")
        try:
            pipeline_result = await pipeline.process_image(
                image_data,
                filename=request.filename,
                user_preferences=request.options.model_dump() if request.options else None
            )
        except Exception as e:
            logger.error(f"Pipeline processing failed: {e}")
            handle_unexpected_error(e, context="pipeline_processing")

        if not pipeline_result.get("success", False):
            error_type = pipeline_result.get("error_type", "unknown")
            error_message = pipeline_result.get("error", "Unknown error occurred")

            # Map error types to appropriate error responses
            if error_type == "image_quality":
                quality_score = pipeline_result.get("quality_score", 0)
                error_details = create_image_quality_error(
                    quality_score=quality_score,
                    issues=pipeline_result.get("quality_issues", []),
                    request_id=None
                )
            elif error_type == "non_tcg_card":
                quality_score = pipeline_result.get("quality_score", 0)
                error_details = create_non_tcg_card_error(
                    quality_score=quality_score,
                    request_id=None
                )
            elif error_type == "card_back":
                quality_score = pipeline_result.get("quality_score", 0)
                error_details = create_card_back_error(quality_score=quality_score)
            elif error_type == "non_pokemon":
                quality_score = pipeline_result.get("quality_score", 0)
                error_details = create_non_pokemon_card_error(quality_score=quality_score)
            else:
                # Generic error
                error_details = create_service_error(
                    service_name="processing_pipeline",
                    original_error=error_message,
                    request_id=None
                )

            raise_pokemon_scanner_error(error_details)

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
        
        # Parse the Gemini response
        parse_start = time.time()
        parsed_data = parse_gemini_response(gemini_data["response"])
        parse_time = (time.time() - parse_start) * 1000
        logger.debug(f"⏱️ Response parsing took {parse_time:.1f}ms")
        
        # Extract card type info from parsed data
        card_type_info_dict = parsed_data.get("card_type_info")
        
        # Convert card_type_info dict to CardTypeInfo object if present
        card_type_info = None
        if card_type_info_dict and isinstance(card_type_info_dict, dict):
            card_type_info = CardTypeInfo(**card_type_info_dict)

        # Extract language and authenticity info from parsed data
        language_info_dict = parsed_data.get("language_info")
        authenticity_info_dict = parsed_data.get("authenticity_info")
        
        # Convert to objects if present
        language_info = LanguageInfo(**language_info_dict) if language_info_dict else None
        authenticity_info = AuthenticityInfo(**authenticity_info_dict) if authenticity_info_dict else None
        
        # Prepare Gemini analysis
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
            }
        )

        # Track Gemini costs
        gemini_cost = 0.0
        if cost_tracker:
            gemini_cost = cost_tracker.track_gemini_usage(
                prompt_tokens=gemini_data.get("prompt_tokens", 0),
                response_tokens=gemini_data.get("response_tokens", 0),
                includes_image=True,
                operation="identify_card",
            )

        logger.info("🎯 Searching Pokemon TCG database...")
        tcg_start = time.time()

        # Use API key for production capacity (20,000 requests/day vs 1,000)
        tcg_client = PokemonTcgClient(api_key=config.pokemon_tcg_api_key)
        
        tcg_search_service = TCGSearchService()
        tcg_search_start = time.time()
        all_search_results, search_attempts, tcg_matches = await tcg_search_service.search_for_card(
            parsed_data, tcg_client
        )
        tcg_search_time = (time.time() - tcg_search_start) * 1000
        logger.info(f"⏱️ TCG search completed in {tcg_search_time:.1f}ms with {len(all_search_results)} results")
        
        best_match_card = None
        all_match_scores = []
        all_scored_matches = []

        if parsed_data.get("name") and all_search_results:
            # Select the best match using intelligent scoring and get all matches
            best_match_data, all_scored_matches = select_best_match(all_search_results, parsed_data)

            # Check if no good match was found due to low scores
            if best_match_data is None and all_scored_matches:
                highest_score = all_scored_matches[0]["score"] if all_scored_matches else 0
                highest_card = all_scored_matches[0] if all_scored_matches else None

                logger.warning(f"❌ Card not found: Highest score {highest_score} below threshold {MINIMUM_SCORE_THRESHOLD}")
                if highest_card:
                    logger.info(f"   📊 Best candidate: {highest_card.get('card_name')} #{highest_card.get('card_number')} from {highest_card.get('set_name')}")

                # Create detailed error with search information
                search_details = {
                    "highest_score": highest_score,
                    "required_score": MINIMUM_SCORE_THRESHOLD,
                    "score_gap": MINIMUM_SCORE_THRESHOLD - highest_score
                }

                error_details = create_no_match_error(
                    search_params=parsed_data,
                    request_id=None
                )
                error_details.details.update(search_details)
                error_details.suggestions = [
                    "Try a clearer image with better lighting",
                    "Ensure the card is fully visible and centered",
                    "Make sure the image is not blurry or distorted",
                    "Check that it's a Pokemon trading card (not a different card game)"
                ]

                raise_pokemon_scanner_error(error_details)

            logger.info(f"📊 Processing {len(all_scored_matches)} scored matches for detailed response")

            # Process all scored matches
            for match_info in all_scored_matches:
                # Create PokemonCard object for this match
                card_data = match_info["card"]
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

            if best_match_data:
                for card in tcg_matches:
                    if card.id == best_match_data["id"]:
                        best_match_card = card
                        break

            if request.options.include_cost_tracking and config.enable_cost_tracking:
                cost_tracker.track_tcg_usage("search")
        else:
            logger.info("⚠️ TCG search skipped - no Pokemon name identified")

        tcg_time = (time.time() - tcg_start) * 1000

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
            actual_time_ms=processing_metadata['actual_time_ms'] + tcg_time,
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

        cost_info = None
        if request.options.include_cost_tracking:
            cost_info = CostInfo(
                gemini_cost=gemini_cost,
                total_cost=gemini_cost,
                cost_breakdown={
                    "gemini_image": CostTracker.GEMINI_COSTS["image_processing"],
                    "gemini_tokens": gemini_cost - CostTracker.GEMINI_COSTS["image_processing"],
                    "tcg_api": 0.0,
                },
            )

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
                quality_score = processing_info.quality_score if hasattr(processing_info, 'quality_score') else None
                error_details = create_card_back_error(quality_score=quality_score)
                raise_pokemon_scanner_error(error_details)

            elif card_type == "non_pokemon":
                # Non-Pokemon card detected - return user-friendly error
                quality_score = processing_info.quality_score if hasattr(processing_info, 'quality_score') else None
                error_details = create_non_pokemon_card_error(quality_score=quality_score)
                raise_pokemon_scanner_error(error_details)

            elif card_type == "unknown":
                # Unknown cards - consider failed if no data extracted
                scan_success = parsed_data.get("name") is not None
                if not scan_success:
                    error_message = "Could not determine card type or extract card data"
        else:
            # Fallback to original logic if no card type info
            scan_success = True  # Default to success for now

        total_time = (time.time() - start_time) * 1000

        best_match_score = 0
        if all_scored_matches:
            best_match_score = all_scored_matches[0].get("score", 0)

        logger.info(f"✅ Scan complete: {len(tcg_matches) if tcg_matches else 0} matches found in {total_time:.0f}ms")

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

        return create_simplified_response(
            best_match=best_match_card,
            processing_info=processing_info,
            gemini_analysis=gemini_analysis,
            all_match_scores=all_scored_matches,
            best_match_score=best_match_score
        )

    except HTTPException as e:
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
        total_time = (time.time() - start_time) * 1000

        error_context = {
            "filename": request.filename,
            "processing_time_ms": int(total_time),
            "error_type": type(e).__name__,
        }

        await send_error_webhook(
            error_message=f"Card scan failed: {str(e)}",
            level="ERROR",
            endpoint="/api/v1/scan",
            context=error_context,
            traceback=str(e),
        )

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

        # Handle unexpected error with proper error response
        handle_unexpected_error(e, context="card_scan")