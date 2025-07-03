"""Pydantic schemas for Pokemon card scanner API."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ScanOptions(BaseModel):
    """Options for card scanning."""
    optimize_for_speed: bool = Field(default=True, description="Optimize for faster processing")
    include_cost_tracking: bool = Field(default=True, description="Track API usage costs")
    retry_on_truncation: bool = Field(default=True, description="Retry if response is truncated")
    quality_threshold: Optional[int] = Field(None, description="Minimum quality score (0-100)")
    max_processing_time: Optional[int] = Field(None, description="Maximum processing time in ms")
    prefer_speed: Optional[bool] = Field(None, description="Prefer speed over quality")
    prefer_quality: Optional[bool] = Field(None, description="Prefer quality over speed")
    response_format: str = Field(default="simplified", description="Response format: 'simplified' (default) or 'detailed'")


class ScanRequest(BaseModel):
    """Request model for card scanning."""
    image: str = Field(..., description="Base64 encoded image data")
    filename: Optional[str] = Field(None, description="Original filename")
    options: ScanOptions = Field(default_factory=ScanOptions)


class CardTypeInfo(BaseModel):
    """Card type detection information."""
    card_type: str = Field(..., description="Card type: pokemon_front, pokemon_back, non_pokemon, unknown")
    is_pokemon_card: bool = Field(..., description="Whether this is a Pokemon card")
    card_side: str = Field(..., description="Card side: front, back, unknown")


class LanguageInfo(BaseModel):
    """Language detection and translation information."""
    detected_language: str = Field(..., description="Detected language code (en, fr, ja, etc.)")
    original_name: Optional[str] = Field(None, description="Pokemon name as written on card")
    translated_name: Optional[str] = Field(None, description="English translation of Pokemon name")
    is_translation: bool = Field(default=False, description="Whether name was translated")
    translation_note: Optional[str] = Field(None, description="Note about translation performed")


class AuthenticityInfo(BaseModel):
    """Authenticity and readability assessment information."""
    authenticity_score: Optional[int] = Field(None, description="Authenticity score (0-100, 100=authentic)")
    readability_score: Optional[int] = Field(None, description="Text readability score (0-100, 100=perfectly readable)")


class GeminiAnalysis(BaseModel):
    """Gemini's analysis of the Pokemon card."""
    raw_response: str = Field(..., description="Full Gemini response")
    structured_data: Optional[Dict[str, Any]] = Field(None, description="Extracted structured data")
    card_type_info: Optional[CardTypeInfo] = Field(None, description="Card type detection information")
    language_info: Optional[LanguageInfo] = Field(None, description="Language detection and translation info")
    authenticity_info: Optional[AuthenticityInfo] = Field(None, description="Authenticity assessment information")
    confidence: Optional[float] = Field(None, description="Confidence score (0-1)")
    tokens_used: Optional[Dict[str, int]] = Field(None, description="Token usage")


class PokemonCard(BaseModel):
    """Pokemon card data from TCG API."""
    id: str = Field(..., description="Unique card ID")
    name: str = Field(..., description="Pokemon name")
    set_name: Optional[str] = Field(None, description="Set name")
    number: Optional[str] = Field(None, description="Card number")
    types: Optional[List[str]] = Field(None, description="Pokemon types")
    hp: Optional[str] = Field(None, description="HP value")
    rarity: Optional[str] = Field(None, description="Card rarity")
    images: Optional[Dict[str, str]] = Field(None, description="Card images")
    market_prices: Optional[Dict[str, Any]] = Field(None, description="Market price data")


class QualityFeedback(BaseModel):
    """Quality assessment feedback."""
    overall: str = Field(..., description="Overall quality rating")
    issues: List[str] = Field(default_factory=list, description="Identified quality issues")
    suggestions: List[str] = Field(default_factory=list, description="Improvement suggestions")


class ProcessingInfo(BaseModel):
    """Information about the processing steps."""
    quality_score: float = Field(..., description="Image quality score (0-100)")
    quality_feedback: QualityFeedback = Field(..., description="Quality assessment feedback")
    processing_tier: str = Field(default="enhanced", description="Processing tier (always enhanced for comprehensive analysis)")
    target_time_ms: int = Field(..., description="Target processing time")
    actual_time_ms: float = Field(..., description="Actual processing time")
    model_used: str = Field(..., description="AI model used for analysis")
    image_enhanced: bool = Field(..., description="Whether image enhancement was applied")
    performance_rating: str = Field(..., description="Performance rating vs target")
    timing_breakdown: Dict[str, float] = Field(..., description="Detailed timing breakdown")
    processing_log: List[str] = Field(default_factory=list, description="Processing step log")


class CostInfo(BaseModel):
    """Cost information for the request."""
    gemini_cost: float = Field(..., description="Gemini API cost in USD")
    total_cost: float = Field(..., description="Total cost in USD")
    cost_breakdown: Dict[str, float] = Field(..., description="Detailed cost breakdown")


class SimplifiedScanResponse(BaseModel):
    """Simplified response model for card scanning."""
    name: str = Field(..., description="Pokemon name")
    set_name: Optional[str] = Field(None, description="Set name")
    number: Optional[str] = Field(None, description="Card number")
    hp: Optional[str] = Field(None, description="HP value")
    types: Optional[List[str]] = Field(None, description="Pokemon types")
    rarity: Optional[str] = Field(None, description="Card rarity")
    image: Optional[str] = Field(None, description="Card image URL")
    market_prices: Optional[Dict[str, float]] = Field(None, description="Market price data")
    quality_score: float = Field(..., description="Image quality score (0-100)")


class MatchScore(BaseModel):
    """Detailed scoring information for a TCG match."""
    card: PokemonCard = Field(..., description="The Pokemon card")
    score: int = Field(..., description="Total match score")
    score_breakdown: Dict[str, int] = Field(..., description="Detailed scoring breakdown")
    confidence: str = Field(..., description="Confidence level (high/medium/low)")
    reasoning: List[str] = Field(default_factory=list, description="Human-readable match reasoning")


class ScanResponse(BaseModel):
    """Response model for card scanning."""
    success: bool = Field(..., description="Whether scan was successful")
    card_identification: Optional[GeminiAnalysis] = Field(None, description="Gemini's card analysis")
    tcg_matches: Optional[List[PokemonCard]] = Field(None, description="Matching cards from TCG API")
    all_tcg_matches: Optional[List[MatchScore]] = Field(None, description="All TCG matches with detailed scoring")
    best_match: Optional[PokemonCard] = Field(None, description="Best matching card")
    processing: ProcessingInfo = Field(..., description="Processing details and quality metrics")
    cost_info: Optional[CostInfo] = Field(None, description="Cost tracking information")
    processed_image_filename: Optional[str] = Field(None, description="Filename of saved processed image")
    error: Optional[str] = Field(None, description="Error message if scan failed")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    services: Dict[str, Any] = Field(..., description="Service availability and metrics")


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")