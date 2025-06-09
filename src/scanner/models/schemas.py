"""Pydantic schemas for Pokemon card scanner API."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ScanOptions(BaseModel):
    """Options for card scanning."""
    optimize_for_speed: bool = Field(default=True, description="Optimize for faster processing")
    include_cost_tracking: bool = Field(default=True, description="Track API usage costs")
    retry_on_truncation: bool = Field(default=True, description="Retry if response is truncated")


class ScanRequest(BaseModel):
    """Request model for card scanning."""
    image: str = Field(..., description="Base64 encoded image data")
    filename: Optional[str] = Field(None, description="Original filename")
    options: ScanOptions = Field(default_factory=ScanOptions)


class GeminiAnalysis(BaseModel):
    """Gemini's analysis of the Pokemon card."""
    raw_response: str = Field(..., description="Full Gemini response")
    structured_data: Optional[Dict[str, Any]] = Field(None, description="Extracted structured data")
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


class ProcessingInfo(BaseModel):
    """Information about the processing steps."""
    image_processing: Dict[str, Any] = Field(..., description="Image processing details")
    gemini_processing: Dict[str, Any] = Field(..., description="Gemini processing details")
    tcg_search: Dict[str, Any] = Field(..., description="TCG search details")
    total_time_ms: int = Field(..., description="Total processing time in milliseconds")


class CostInfo(BaseModel):
    """Cost information for the request."""
    gemini_cost: float = Field(..., description="Gemini API cost in USD")
    total_cost: float = Field(..., description="Total cost in USD")
    cost_breakdown: Dict[str, float] = Field(..., description="Detailed cost breakdown")


class ScanResponse(BaseModel):
    """Response model for card scanning."""
    success: bool = Field(..., description="Whether scan was successful")
    card_identification: Optional[GeminiAnalysis] = Field(None, description="Gemini's card analysis")
    tcg_matches: Optional[List[PokemonCard]] = Field(None, description="Matching cards from TCG API")
    best_match: Optional[PokemonCard] = Field(None, description="Best matching card")
    processing_info: ProcessingInfo = Field(..., description="Processing details")
    cost_info: Optional[CostInfo] = Field(None, description="Cost tracking information")
    error: Optional[str] = Field(None, description="Error message if scan failed")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    services: Dict[str, bool] = Field(..., description="Service availability")


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")