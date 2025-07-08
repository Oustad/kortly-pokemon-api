"""Unit tests for ErrorHandler service - simplified version."""

import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException

from src.scanner.services.error_handler import (
    ErrorType,
    ErrorDetails,
    raise_pokemon_scanner_error,
    handle_unexpected_error,
    is_client_error,
    is_server_error,
    should_retry,
    get_retry_delay
)


class TestErrorHandler:
    """Test cases for ErrorHandler functions."""

    def test_error_type_enum(self):
        """Test ErrorType enum values."""
        # Test client errors
        assert ErrorType.INVALID_INPUT.status_code == 400
        assert ErrorType.INVALID_INPUT.error_code == "invalid_input"
        
        assert ErrorType.IMAGE_QUALITY_TOO_LOW.status_code == 400
        assert ErrorType.RATE_LIMITED.status_code == 429
        
        # Test server errors
        assert ErrorType.PROCESSING_FAILED.status_code == 500
        assert ErrorType.AI_SERVICE_ERROR.status_code == 502
        assert ErrorType.SERVICE_UNAVAILABLE.status_code == 503

    def test_error_details_creation(self):
        """Test ErrorDetails creation."""
        error_details = ErrorDetails(
            error_type=ErrorType.IMAGE_QUALITY_TOO_LOW,
            message="Custom message",
            details={"quality_score": 35.5},
            quality_score=35.5
        )
        
        assert error_details.error_type == ErrorType.IMAGE_QUALITY_TOO_LOW
        assert error_details.message == "Custom message"
        assert error_details.details["quality_score"] == 35.5
        assert error_details.quality_score == 35.5

    def test_raise_pokemon_scanner_error(self):
        """Test raising PokemonScannerError."""
        error_details = ErrorDetails(
            error_type=ErrorType.NO_CARD_FOUND,
            message="No matching card found"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            raise_pokemon_scanner_error(error_details)
        
        assert exc_info.value.status_code == 404

    def test_handle_unexpected_error(self):
        """Test handling unexpected errors."""
        original_error = ValueError("Test error")
        
        # handle_unexpected_error raises an exception, so we need to catch it
        with patch('src.scanner.services.error_handler.logger') as mock_logger:
            with pytest.raises(HTTPException) as exc_info:
                handle_unexpected_error(original_error, "test.jpg")
        
        # Should raise HTTPException with 500 status
        assert exc_info.value.status_code == 500
        
        # Should log the error
        mock_logger.error.assert_called_once()

    def test_is_client_error(self):
        """Test client error detection."""
        assert is_client_error(400) is True
        assert is_client_error(404) is True
        assert is_client_error(429) is True
        assert is_client_error(500) is False
        assert is_client_error(503) is False

    def test_is_server_error(self):
        """Test server error detection."""
        assert is_server_error(500) is True
        assert is_server_error(502) is True
        assert is_server_error(503) is True
        assert is_server_error(400) is False
        assert is_server_error(404) is False

    def test_should_retry(self):
        """Test retry logic for different error types."""
        # Should retry server errors
        assert should_retry(ErrorType.AI_SERVICE_ERROR) is True
        assert should_retry(ErrorType.TIMEOUT_ERROR) is True
        assert should_retry(ErrorType.SERVICE_UNAVAILABLE) is True
        
        # Should not retry client errors
        assert should_retry(ErrorType.INVALID_INPUT) is False
        assert should_retry(ErrorType.IMAGE_QUALITY_TOO_LOW) is False
        assert should_retry(ErrorType.NO_CARD_FOUND) is False

    def test_get_retry_delay(self):
        """Test retry delay calculation."""
        # Different error types should have different delays
        ai_delay = get_retry_delay(ErrorType.AI_SERVICE_ERROR)
        timeout_delay = get_retry_delay(ErrorType.TIMEOUT_ERROR)
        
        assert ai_delay > 0
        assert timeout_delay > 0
        assert isinstance(ai_delay, int)
        assert isinstance(timeout_delay, int)