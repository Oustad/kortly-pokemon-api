"""Centralized error handling service for Pokemon card scanner."""

import json
import logging
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import HTTPException

from ..models.schemas import QualityFeedback

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Enumeration of error types with their characteristics."""
    
    # Client Errors (4xx)
    INVALID_INPUT = ("invalid_input", 400, "Invalid input data provided")
    INVALID_IMAGE = ("invalid_image", 400, "Invalid or corrupted image data")
    IMAGE_TOO_LARGE = ("image_too_large", 413, "Image file size exceeds maximum limit")
    UNSUPPORTED_FORMAT = ("unsupported_format", 415, "Unsupported image format")
    IMAGE_QUALITY_TOO_LOW = ("image_quality_too_low", 400, "Image quality too low for processing")
    NON_TCG_CARD = ("non_tcg_card", 400, "Not an official Pokemon TCG card")
    CARD_BACK_DETECTED = ("card_back_detected", 400, "Card back detected - please scan the front")
    NON_POKEMON_CARD = ("non_pokemon_card", 400, "Not a Pokemon card")
    NO_CARD_FOUND = ("no_card_found", 404, "No matching card found in database")
    FEATURE_DISABLED = ("feature_disabled", 404, "Requested feature is disabled")
    RATE_LIMITED = ("rate_limited", 429, "Rate limit exceeded")
    
    # Server Errors (5xx)
    PROCESSING_FAILED = ("processing_failed", 500, "Card processing failed")
    AI_SERVICE_ERROR = ("ai_service_error", 502, "AI service temporarily unavailable")
    DATABASE_ERROR = ("database_error", 503, "Card database temporarily unavailable")
    INTERNAL_ERROR = ("internal_error", 500, "Internal server error")
    SERVICE_UNAVAILABLE = ("service_unavailable", 503, "Service temporarily unavailable")
    TIMEOUT_ERROR = ("timeout_error", 504, "Processing timeout exceeded")
    
    def __init__(self, error_code: str, status_code: int, default_message: str):
        self.error_code = error_code
        self.status_code = status_code
        self.default_message = default_message


class ErrorDetails:
    """Structured error details for consistent API responses."""
    
    def __init__(
        self,
        error_type: ErrorType,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        quality_feedback: Optional[QualityFeedback] = None,
        suggestions: Optional[list] = None,
        quality_score: Optional[float] = None,
        authenticity_score: Optional[int] = None,
        request_id: Optional[str] = None
    ):
        self.error_type = error_type
        self.message = message or error_type.default_message
        self.details = details or {}
        self.quality_feedback = quality_feedback
        self.suggestions = suggestions or []
        self.quality_score = quality_score
        self.authenticity_score = authenticity_score
        self.request_id = request_id
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error details to dictionary for JSON response."""
        response = {
            "message": self.message,
            "error_type": self.error_type.error_code,
            "error_code": self.error_type.error_code,  # Legacy compatibility
        }
        
        # Add optional fields only if they have values
        if self.details:
            response["details"] = self.details
        
        if self.quality_feedback:
            response["quality_feedback"] = self.quality_feedback.dict()
        
        if self.suggestions:
            response["suggestions"] = self.suggestions
        
        if self.quality_score is not None:
            response["quality_score"] = self.quality_score
        
        if self.authenticity_score is not None:
            response["authenticity_score"] = self.authenticity_score
        
        if self.request_id:
            response["request_id"] = self.request_id
        
        return response


class PokemonScannerError(Exception):
    """Base exception for Pokemon scanner errors with structured details."""
    
    def __init__(self, error_details: ErrorDetails):
        self.error_details = error_details
        super().__init__(error_details.message)


def create_image_quality_error(
    quality_score: Optional[float] = None,
    specific_issues: Optional[list] = None,
    request_id: Optional[str] = None
) -> ErrorDetails:
    """Create a standardized image quality error."""
    
    default_issues = [
        "Image too blurry to read card details clearly",
        "Card text and numbers are not legible"
    ]
    
    default_suggestions = [
        "Ensure the card is well-lit with no shadows",
        "Hold the camera steady and wait for auto-focus", 
        "Try taking the photo from directly above the card",
        "Clean the camera lens if needed"
    ]
    
    quality_feedback = QualityFeedback(
        overall="poor",
        issues=specific_issues or default_issues,
        suggestions=default_suggestions
    )
    
    return ErrorDetails(
        error_type=ErrorType.IMAGE_QUALITY_TOO_LOW,
        quality_feedback=quality_feedback,
        quality_score=quality_score,
        request_id=request_id
    )


def create_non_tcg_card_error(
    authenticity_score: Optional[int] = None,
    quality_score: Optional[float] = None,
    request_id: Optional[str] = None
) -> ErrorDetails:
    """Create a standardized non-TCG card error."""
    
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
    
    return ErrorDetails(
        error_type=ErrorType.NON_TCG_CARD,
        message="This appears to be a Pokemon-related item but not an official TCG card. Please scan an official Pokemon Trading Card Game card.",
        quality_feedback=quality_feedback,
        authenticity_score=authenticity_score,
        quality_score=quality_score,
        request_id=request_id
    )


def create_card_back_error(
    quality_score: Optional[float] = None,
    request_id: Optional[str] = None
) -> ErrorDetails:
    """Create a standardized card back error."""
    
    quality_feedback = QualityFeedback(
        overall="good",
        issues=["Card back detected instead of front"],
        suggestions=[
            "Flip the card over to show the front side",
            "Ensure the Pokemon artwork and card details are visible"
        ]
    )
    
    return ErrorDetails(
        error_type=ErrorType.CARD_BACK_DETECTED,
        message="Card back detected. Please flip the card and scan the front side with the Pokemon artwork.",
        quality_feedback=quality_feedback,
        quality_score=quality_score,
        request_id=request_id
    )


def create_non_pokemon_card_error(
    detected_type: Optional[str] = None,
    quality_score: Optional[float] = None,
    request_id: Optional[str] = None
) -> ErrorDetails:
    """Create a standardized non-Pokemon card error."""
    
    message = "This appears to be a card but not a Pokemon card."
    if detected_type:
        message = f"This appears to be a {detected_type}, not a Pokemon card."
    
    suggestions = [
        "Please scan a Pokemon Trading Card Game card",
        "Ensure the card has Pokemon artwork and TCG formatting"
    ]
    
    if detected_type:
        suggestions.insert(0, f"Detected card type: {detected_type}")
    
    quality_feedback = QualityFeedback(
        overall="good",
        issues=["Non-Pokemon card detected"],
        suggestions=suggestions
    )
    
    return ErrorDetails(
        error_type=ErrorType.NON_POKEMON_CARD,
        message=message,
        quality_feedback=quality_feedback,
        quality_score=quality_score,
        request_id=request_id
    )


def create_no_match_error(
    search_params: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> ErrorDetails:
    """Create a standardized no match found error."""
    
    suggestions = [
        "Verify the card is from an official Pokemon TCG set",
        "Check that the image shows the card clearly",
        "Try a different angle or better lighting"
    ]
    
    details = {}
    if search_params:
        details["attempted_search"] = {
            "name": search_params.get("name"),
            "set": search_params.get("set_name"), 
            "number": search_params.get("number")
        }
        # Filter out None values
        details["attempted_search"] = {k: v for k, v in details["attempted_search"].items() if v is not None}
    
    return ErrorDetails(
        error_type=ErrorType.NO_CARD_FOUND,
        message="No matching Pokemon card found in our database",
        details=details,
        suggestions=suggestions,
        request_id=request_id
    )


def create_rate_limit_error(
    limit: int,
    window: str = "minute",
    retry_after: Optional[int] = None,
    request_id: Optional[str] = None
) -> ErrorDetails:
    """Create a standardized rate limit error."""
    
    message = f"Rate limit exceeded. Maximum {limit} requests per {window}."
    details = {
        "limit": limit,
        "window": window
    }
    
    if retry_after:
        details["retry_after_seconds"] = retry_after
        message += f" Try again in {retry_after} seconds."
    
    return ErrorDetails(
        error_type=ErrorType.RATE_LIMITED,
        message=message,
        details=details,
        suggestions=["Please wait before making another request"],
        request_id=request_id
    )


def create_processing_timeout_error(
    timeout_seconds: int,
    request_id: Optional[str] = None
) -> ErrorDetails:
    """Create a standardized processing timeout error."""
    
    return ErrorDetails(
        error_type=ErrorType.TIMEOUT_ERROR,
        message=f"Processing timeout exceeded ({timeout_seconds}s). Please try again with a simpler image.",
        details={"timeout_seconds": timeout_seconds},
        suggestions=[
            "Try with a higher quality, less complex image",
            "Ensure good lighting and clear focus",
            "Retry the request"
        ],
        request_id=request_id
    )


def create_service_error(
    service_name: str,
    original_error: Optional[str] = None,
    is_temporary: bool = True,
    request_id: Optional[str] = None
) -> ErrorDetails:
    """Create a standardized service error."""
    
    if service_name.lower() in ["gemini", "ai", "vision"]:
        error_type = ErrorType.AI_SERVICE_ERROR
        message = "AI vision service is temporarily unavailable"
    elif service_name.lower() in ["tcg", "database", "api"]:
        error_type = ErrorType.DATABASE_ERROR
        message = "Card database service is temporarily unavailable"
    else:
        error_type = ErrorType.SERVICE_UNAVAILABLE
        message = f"{service_name} service is temporarily unavailable"
    
    if not is_temporary:
        error_type = ErrorType.INTERNAL_ERROR
        message = f"Error in {service_name} service"
    
    details = {"service": service_name}
    if original_error:
        details["original_error"] = original_error
    
    suggestions = ["Please try again in a few moments"]
    if not is_temporary:
        suggestions = ["Please contact support if this issue persists"]
    
    return ErrorDetails(
        error_type=error_type,
        message=message,
        details=details,
        suggestions=suggestions,
        request_id=request_id
    )


def raise_pokemon_scanner_error(error_details: ErrorDetails) -> None:
    """Raise an HTTPException with structured error details."""
    
    # Log the error with appropriate level
    log_message = f"{error_details.error_type.error_code}: {error_details.message}"
    if error_details.request_id:
        log_message = f"[{error_details.request_id}] {log_message}"
    
    if error_details.error_type.status_code >= 500:
        logger.error(log_message)
    elif error_details.error_type.status_code == 429:
        logger.warning(f"Rate limit: {log_message}")
    else:
        logger.info(f"Client error: {log_message}")
    
    # Create HTTPException with structured detail
    raise HTTPException(
        status_code=error_details.error_type.status_code,
        detail=json.dumps(error_details.to_dict())
    )


def handle_unexpected_error(
    error: Exception,
    context: str = "processing",
    request_id: Optional[str] = None
) -> None:
    """Handle unexpected errors by converting them to structured errors."""
    
    logger.exception(f"Unexpected error during {context}: {str(error)}")
    
    error_details = ErrorDetails(
        error_type=ErrorType.INTERNAL_ERROR,
        message=f"An unexpected error occurred during {context}",
        details={"context": context},
        suggestions=["Please try again or contact support if the issue persists"],
        request_id=request_id
    )
    
    raise_pokemon_scanner_error(error_details)


def is_client_error(status_code: int) -> bool:
    """Check if status code represents a client error (4xx)."""
    return 400 <= status_code < 500


def is_server_error(status_code: int) -> bool:
    """Check if status code represents a server error (5xx)."""
    return status_code >= 500


def should_retry(error_type: ErrorType) -> bool:
    """Determine if an error type is retryable."""
    retryable_types = {
        ErrorType.AI_SERVICE_ERROR,
        ErrorType.DATABASE_ERROR,
        ErrorType.SERVICE_UNAVAILABLE,
        ErrorType.TIMEOUT_ERROR,
        ErrorType.INTERNAL_ERROR,  # Sometimes retryable
    }
    return error_type in retryable_types


def get_retry_delay(error_type: ErrorType) -> int:
    """Get recommended retry delay in seconds for error type."""
    if error_type == ErrorType.RATE_LIMITED:
        return 60  # 1 minute for rate limits
    elif error_type in [ErrorType.AI_SERVICE_ERROR, ErrorType.DATABASE_ERROR]:
        return 30   # 30 seconds for service errors
    elif error_type == ErrorType.TIMEOUT_ERROR:
        return 10   # 10 seconds for timeouts
    else:
        return 5    # 5 seconds default