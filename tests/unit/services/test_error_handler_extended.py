"""Extended tests for error_handler.py to achieve higher coverage."""

import pytest
import json
from unittest.mock import Mock, patch
from fastapi import HTTPException

from src.scanner.services.error_handler import (
    ErrorType,
    ErrorDetails,
    PokemonScannerError,
    create_image_quality_error,
    create_non_tcg_card_error,
    create_card_back_error,
    create_non_pokemon_card_error,
    create_no_match_error,
    create_rate_limit_error,
    create_processing_timeout_error,
    create_service_error,
    raise_pokemon_scanner_error,
    handle_unexpected_error,
    is_client_error,
    is_server_error,
    should_retry,
    get_retry_delay
)
from src.scanner.models.schemas import QualityFeedback


class TestErrorType:
    """Test the ErrorType enum."""

    def test_error_type_attributes(self):
        """Test that ErrorType enum has correct attributes."""
        error_type = ErrorType.INVALID_INPUT
        
        assert error_type.error_code == "invalid_input"
        assert error_type.status_code == 400
        assert error_type.default_message == "Invalid input data provided"

    def test_all_error_types_have_required_attributes(self):
        """Test that all error types have required attributes."""
        for error_type in ErrorType:
            assert hasattr(error_type, 'error_code')
            assert hasattr(error_type, 'status_code')
            assert hasattr(error_type, 'default_message')
            assert isinstance(error_type.error_code, str)
            assert isinstance(error_type.status_code, int)
            assert isinstance(error_type.default_message, str)

    def test_client_error_status_codes(self):
        """Test that client errors have 4xx status codes."""
        client_errors = [
            ErrorType.INVALID_INPUT,
            ErrorType.INVALID_IMAGE,
            ErrorType.IMAGE_TOO_LARGE,
            ErrorType.UNSUPPORTED_FORMAT,
            ErrorType.IMAGE_QUALITY_TOO_LOW,
            ErrorType.NON_TCG_CARD,
            ErrorType.CARD_BACK_DETECTED,
            ErrorType.NON_POKEMON_CARD,
            ErrorType.NO_CARD_FOUND,
            ErrorType.FEATURE_DISABLED,
            ErrorType.RATE_LIMITED
        ]
        
        for error_type in client_errors:
            assert 400 <= error_type.status_code < 500

    def test_server_error_status_codes(self):
        """Test that server errors have 5xx status codes."""
        server_errors = [
            ErrorType.PROCESSING_FAILED,
            ErrorType.AI_SERVICE_ERROR,
            ErrorType.DATABASE_ERROR,
            ErrorType.INTERNAL_ERROR,
            ErrorType.SERVICE_UNAVAILABLE,
            ErrorType.TIMEOUT_ERROR
        ]
        
        for error_type in server_errors:
            assert error_type.status_code >= 500

    def test_specific_error_types(self):
        """Test specific error type values."""
        assert ErrorType.RATE_LIMITED.status_code == 429
        assert ErrorType.IMAGE_TOO_LARGE.status_code == 413
        assert ErrorType.UNSUPPORTED_FORMAT.status_code == 415
        assert ErrorType.NO_CARD_FOUND.status_code == 404
        assert ErrorType.AI_SERVICE_ERROR.status_code == 502
        assert ErrorType.DATABASE_ERROR.status_code == 503
        assert ErrorType.TIMEOUT_ERROR.status_code == 504


class TestErrorDetails:
    """Test the ErrorDetails class."""

    def test_error_details_initialization_minimal(self):
        """Test ErrorDetails initialization with minimal parameters."""
        error_details = ErrorDetails(ErrorType.INVALID_INPUT)
        
        assert error_details.error_type == ErrorType.INVALID_INPUT
        assert error_details.message == ErrorType.INVALID_INPUT.default_message
        assert error_details.details == {}
        assert error_details.quality_feedback is None
        assert error_details.suggestions == []
        assert error_details.quality_score is None
        assert error_details.authenticity_score is None
        assert error_details.request_id is None

    def test_error_details_initialization_complete(self):
        """Test ErrorDetails initialization with all parameters."""
        quality_feedback = QualityFeedback(
            overall="poor",
            issues=["blurry"],
            suggestions=["better lighting"]
        )
        
        error_details = ErrorDetails(
            error_type=ErrorType.IMAGE_QUALITY_TOO_LOW,
            message="Custom message",
            details={"key": "value"},
            quality_feedback=quality_feedback,
            suggestions=["suggestion 1", "suggestion 2"],
            quality_score=25.5,
            authenticity_score=30,
            request_id="req-123"
        )
        
        assert error_details.error_type == ErrorType.IMAGE_QUALITY_TOO_LOW
        assert error_details.message == "Custom message"
        assert error_details.details == {"key": "value"}
        assert error_details.quality_feedback == quality_feedback
        assert error_details.suggestions == ["suggestion 1", "suggestion 2"]
        assert error_details.quality_score == 25.5
        assert error_details.authenticity_score == 30
        assert error_details.request_id == "req-123"

    def test_error_details_default_values(self):
        """Test ErrorDetails default value handling."""
        error_details = ErrorDetails(
            error_type=ErrorType.INVALID_INPUT,
            details=None,
            suggestions=None
        )
        
        assert error_details.details == {}
        assert error_details.suggestions == []

    def test_to_dict_minimal(self):
        """Test to_dict with minimal error details."""
        error_details = ErrorDetails(ErrorType.INVALID_INPUT)
        result = error_details.to_dict()
        
        expected = {
            "message": ErrorType.INVALID_INPUT.default_message,
            "error_type": "invalid_input",
            "error_code": "invalid_input"
        }
        
        assert result == expected

    def test_to_dict_complete(self):
        """Test to_dict with complete error details."""
        quality_feedback = QualityFeedback(
            overall="poor",
            issues=["blurry"],
            suggestions=["better lighting"]
        )
        
        error_details = ErrorDetails(
            error_type=ErrorType.IMAGE_QUALITY_TOO_LOW,
            message="Custom message",
            details={"key": "value"},
            quality_feedback=quality_feedback,
            suggestions=["suggestion 1"],
            quality_score=25.5,
            authenticity_score=30,
            request_id="req-123"
        )
        
        result = error_details.to_dict()
        
        assert result["message"] == "Custom message"
        assert result["error_type"] == "image_quality_too_low"
        assert result["error_code"] == "image_quality_too_low"
        assert result["details"] == {"key": "value"}
        assert result["quality_feedback"] == quality_feedback.model_dump()
        assert result["suggestions"] == ["suggestion 1"]
        assert result["quality_score"] == 25.5
        assert result["authenticity_score"] == 30
        assert result["request_id"] == "req-123"

    def test_to_dict_selective_fields(self):
        """Test to_dict only includes fields with values."""
        error_details = ErrorDetails(
            error_type=ErrorType.INVALID_INPUT,
            quality_score=75.0,
            request_id="req-456"
        )
        
        result = error_details.to_dict()
        
        # Should include these fields
        assert "message" in result
        assert "error_type" in result
        assert "error_code" in result
        assert "quality_score" in result
        assert "request_id" in result
        
        # Should not include these fields
        assert "details" not in result
        assert "quality_feedback" not in result
        assert "suggestions" not in result
        assert "authenticity_score" not in result

    def test_to_dict_empty_collections(self):
        """Test to_dict with empty collections."""
        error_details = ErrorDetails(
            error_type=ErrorType.INVALID_INPUT,
            details={},
            suggestions=[]
        )
        
        result = error_details.to_dict()
        
        # Empty collections should not be included
        assert "details" not in result
        assert "suggestions" not in result


class TestPokemonScannerError:
    """Test the PokemonScannerError exception."""

    def test_pokemon_scanner_error_initialization(self):
        """Test PokemonScannerError initialization."""
        error_details = ErrorDetails(
            error_type=ErrorType.INVALID_INPUT,
            message="Test error message"
        )
        
        error = PokemonScannerError(error_details)
        
        assert error.error_details == error_details
        assert str(error) == "Test error message"

    def test_pokemon_scanner_error_inheritance(self):
        """Test that PokemonScannerError inherits from Exception."""
        error_details = ErrorDetails(ErrorType.INVALID_INPUT)
        error = PokemonScannerError(error_details)
        
        assert isinstance(error, Exception)


class TestCreateImageQualityError:
    """Test the create_image_quality_error function."""

    def test_create_image_quality_error_minimal(self):
        """Test creating image quality error with minimal parameters."""
        error_details = create_image_quality_error()
        
        assert error_details.error_type == ErrorType.IMAGE_QUALITY_TOO_LOW
        assert error_details.quality_feedback is not None
        assert error_details.quality_feedback.overall == "poor"
        assert len(error_details.quality_feedback.issues) == 2
        assert len(error_details.quality_feedback.suggestions) == 4

    def test_create_image_quality_error_complete(self):
        """Test creating image quality error with all parameters."""
        specific_issues = ["Too dark", "Motion blur"]
        
        error_details = create_image_quality_error(
            quality_score=15.5,
            specific_issues=specific_issues,
            request_id="req-789"
        )
        
        assert error_details.error_type == ErrorType.IMAGE_QUALITY_TOO_LOW
        assert error_details.quality_score == 15.5
        assert error_details.request_id == "req-789"
        assert error_details.quality_feedback.issues == specific_issues

    def test_create_image_quality_error_default_issues(self):
        """Test that default issues are used when none provided."""
        error_details = create_image_quality_error()
        
        expected_issues = [
            "Image too blurry to read card details clearly",
            "Card text and numbers are not legible"
        ]
        
        assert error_details.quality_feedback.issues == expected_issues

    def test_create_image_quality_error_suggestions(self):
        """Test that appropriate suggestions are included."""
        error_details = create_image_quality_error()
        
        suggestions = error_details.quality_feedback.suggestions
        assert "Ensure the card is well-lit with no shadows" in suggestions
        assert "Hold the camera steady and wait for auto-focus" in suggestions
        assert "Try taking the photo from directly above the card" in suggestions
        assert "Clean the camera lens if needed" in suggestions


class TestCreateNonTcgCardError:
    """Test the create_non_tcg_card_error function."""

    def test_create_non_tcg_card_error_minimal(self):
        """Test creating non-TCG card error with minimal parameters."""
        error_details = create_non_tcg_card_error()
        
        assert error_details.error_type == ErrorType.NON_TCG_CARD
        assert error_details.quality_feedback is not None
        assert error_details.quality_feedback.overall == "poor"
        assert len(error_details.quality_feedback.issues) == 2
        assert len(error_details.quality_feedback.suggestions) == 3

    def test_create_non_tcg_card_error_complete(self):
        """Test creating non-TCG card error with all parameters."""
        error_details = create_non_tcg_card_error(
            authenticity_score=25,
            quality_score=80.0,
            request_id="req-abc"
        )
        
        assert error_details.error_type == ErrorType.NON_TCG_CARD
        assert error_details.authenticity_score == 25
        assert error_details.quality_score == 80.0
        assert error_details.request_id == "req-abc"

    def test_create_non_tcg_card_error_message(self):
        """Test the error message content."""
        error_details = create_non_tcg_card_error()
        
        expected_message = "This appears to be a Pokemon-related item but not an official TCG card. Please scan an official Pokemon Trading Card Game card."
        assert error_details.message == expected_message

    def test_create_non_tcg_card_error_quality_feedback(self):
        """Test quality feedback content."""
        error_details = create_non_tcg_card_error()
        
        assert "This appears to be a Pokemon card but not an official TCG card" in error_details.quality_feedback.issues
        assert "Possible sticker, collectible, or fan-made card detected" in error_details.quality_feedback.issues
        assert "Ensure you're scanning an official Pokemon Trading Card Game card" in error_details.quality_feedback.suggestions


class TestCreateCardBackError:
    """Test the create_card_back_error function."""

    def test_create_card_back_error_minimal(self):
        """Test creating card back error with minimal parameters."""
        error_details = create_card_back_error()
        
        assert error_details.error_type == ErrorType.CARD_BACK_DETECTED
        assert error_details.quality_feedback is not None
        assert error_details.quality_feedback.overall == "good"

    def test_create_card_back_error_complete(self):
        """Test creating card back error with all parameters."""
        error_details = create_card_back_error(
            quality_score=85.0,
            request_id="req-def"
        )
        
        assert error_details.quality_score == 85.0
        assert error_details.request_id == "req-def"

    def test_create_card_back_error_message(self):
        """Test the error message content."""
        error_details = create_card_back_error()
        
        expected_message = "Card back detected. Please flip the card and scan the front side with the Pokemon artwork."
        assert error_details.message == expected_message

    def test_create_card_back_error_quality_feedback(self):
        """Test quality feedback content."""
        error_details = create_card_back_error()
        
        assert "Card back detected instead of front" in error_details.quality_feedback.issues
        assert "Flip the card over to show the front side" in error_details.quality_feedback.suggestions
        assert "Ensure the Pokemon artwork and card details are visible" in error_details.quality_feedback.suggestions


class TestCreateNonPokemonCardError:
    """Test the create_non_pokemon_card_error function."""

    def test_create_non_pokemon_card_error_minimal(self):
        """Test creating non-Pokemon card error with minimal parameters."""
        error_details = create_non_pokemon_card_error()
        
        assert error_details.error_type == ErrorType.NON_POKEMON_CARD
        assert error_details.message == "This appears to be a card but not a Pokemon card."

    def test_create_non_pokemon_card_error_with_detected_type(self):
        """Test creating non-Pokemon card error with detected type."""
        error_details = create_non_pokemon_card_error(
            detected_type="Magic: The Gathering card"
        )
        
        assert error_details.message == "This appears to be a Magic: The Gathering card, not a Pokemon card."
        assert "Detected card type: Magic: The Gathering card" in error_details.quality_feedback.suggestions

    def test_create_non_pokemon_card_error_complete(self):
        """Test creating non-Pokemon card error with all parameters."""
        error_details = create_non_pokemon_card_error(
            detected_type="Yu-Gi-Oh! card",
            quality_score=90.0,
            request_id="req-ghi"
        )
        
        assert error_details.quality_score == 90.0
        assert error_details.request_id == "req-ghi"
        assert "Yu-Gi-Oh! card" in error_details.message

    def test_create_non_pokemon_card_error_suggestions(self):
        """Test that appropriate suggestions are included."""
        error_details = create_non_pokemon_card_error()
        
        suggestions = error_details.quality_feedback.suggestions
        assert "Please scan a Pokemon Trading Card Game card" in suggestions
        assert "Ensure the card has Pokemon artwork and TCG formatting" in suggestions


class TestCreateNoMatchError:
    """Test the create_no_match_error function."""

    def test_create_no_match_error_minimal(self):
        """Test creating no match error with minimal parameters."""
        error_details = create_no_match_error()
        
        assert error_details.error_type == ErrorType.NO_CARD_FOUND
        assert error_details.message == "No matching Pokemon card found in our database"
        assert error_details.details == {}

    def test_create_no_match_error_with_search_params(self):
        """Test creating no match error with search parameters."""
        search_params = {
            "name": "Pikachu",
            "set_name": "Base Set",
            "number": "25"
        }
        
        error_details = create_no_match_error(
            search_params=search_params,
            request_id="req-jkl"
        )
        
        assert error_details.request_id == "req-jkl"
        assert "attempted_search" in error_details.details
        assert error_details.details["attempted_search"]["name"] == "Pikachu"
        assert error_details.details["attempted_search"]["set"] == "Base Set"
        assert error_details.details["attempted_search"]["number"] == "25"

    def test_create_no_match_error_filters_none_values(self):
        """Test that None values are filtered from search params."""
        search_params = {
            "name": "Charizard",
            "set_name": None,
            "number": "6"
        }
        
        error_details = create_no_match_error(search_params=search_params)
        
        attempted_search = error_details.details["attempted_search"]
        assert attempted_search["name"] == "Charizard"
        assert attempted_search["number"] == "6"
        assert "set" not in attempted_search

    def test_create_no_match_error_suggestions(self):
        """Test that appropriate suggestions are included."""
        error_details = create_no_match_error()
        
        assert "Verify the card is from an official Pokemon TCG set" in error_details.suggestions
        assert "Check that the image shows the card clearly" in error_details.suggestions
        assert "Try a different angle or better lighting" in error_details.suggestions


class TestCreateRateLimitError:
    """Test the create_rate_limit_error function."""

    def test_create_rate_limit_error_minimal(self):
        """Test creating rate limit error with minimal parameters."""
        error_details = create_rate_limit_error(limit=10)
        
        assert error_details.error_type == ErrorType.RATE_LIMITED
        assert error_details.message == "Rate limit exceeded. Maximum 10 requests per minute."
        assert error_details.details["limit"] == 10
        assert error_details.details["window"] == "minute"

    def test_create_rate_limit_error_complete(self):
        """Test creating rate limit error with all parameters."""
        error_details = create_rate_limit_error(
            limit=5,
            window="hour",
            retry_after=3600,
            request_id="req-mno"
        )
        
        assert error_details.message == "Rate limit exceeded. Maximum 5 requests per hour. Try again in 3600 seconds."
        assert error_details.details["limit"] == 5
        assert error_details.details["window"] == "hour"
        assert error_details.details["retry_after_seconds"] == 3600
        assert error_details.request_id == "req-mno"

    def test_create_rate_limit_error_suggestions(self):
        """Test that appropriate suggestions are included."""
        error_details = create_rate_limit_error(limit=10)
        
        assert "Please wait before making another request" in error_details.suggestions


class TestCreateProcessingTimeoutError:
    """Test the create_processing_timeout_error function."""

    def test_create_processing_timeout_error_minimal(self):
        """Test creating processing timeout error with minimal parameters."""
        error_details = create_processing_timeout_error(timeout_seconds=30)
        
        assert error_details.error_type == ErrorType.TIMEOUT_ERROR
        assert error_details.message == "Processing timeout exceeded (30s). Please try again with a simpler image."
        assert error_details.details["timeout_seconds"] == 30

    def test_create_processing_timeout_error_complete(self):
        """Test creating processing timeout error with all parameters."""
        error_details = create_processing_timeout_error(
            timeout_seconds=60,
            request_id="req-pqr"
        )
        
        assert error_details.request_id == "req-pqr"
        assert "60s" in error_details.message

    def test_create_processing_timeout_error_suggestions(self):
        """Test that appropriate suggestions are included."""
        error_details = create_processing_timeout_error(timeout_seconds=30)
        
        suggestions = error_details.suggestions
        assert "Try with a higher quality, less complex image" in suggestions
        assert "Ensure good lighting and clear focus" in suggestions
        assert "Retry the request" in suggestions


class TestCreateServiceError:
    """Test the create_service_error function."""

    def test_create_service_error_ai_service(self):
        """Test creating service error for AI service."""
        error_details = create_service_error("gemini")
        
        assert error_details.error_type == ErrorType.AI_SERVICE_ERROR
        assert error_details.message == "AI vision service is temporarily unavailable"
        assert error_details.details["service"] == "gemini"

    def test_create_service_error_database_service(self):
        """Test creating service error for database service."""
        error_details = create_service_error("tcg")
        
        assert error_details.error_type == ErrorType.DATABASE_ERROR
        assert error_details.message == "Card database service is temporarily unavailable"

    def test_create_service_error_generic_service(self):
        """Test creating service error for generic service."""
        error_details = create_service_error("webhook")
        
        assert error_details.error_type == ErrorType.SERVICE_UNAVAILABLE
        assert error_details.message == "webhook service is temporarily unavailable"

    def test_create_service_error_not_temporary(self):
        """Test creating service error that's not temporary."""
        error_details = create_service_error(
            "test_service",
            is_temporary=False
        )
        
        assert error_details.error_type == ErrorType.INTERNAL_ERROR
        assert error_details.message == "Error in test_service service"
        assert "Please contact support if this issue persists" in error_details.suggestions

    def test_create_service_error_with_original_error(self):
        """Test creating service error with original error details."""
        error_details = create_service_error(
            "api",
            original_error="Connection timeout",
            request_id="req-stu"
        )
        
        assert error_details.details["original_error"] == "Connection timeout"
        assert error_details.request_id == "req-stu"

    def test_create_service_error_case_insensitive(self):
        """Test that service name matching is case insensitive."""
        ai_error = create_service_error("GEMINI")
        db_error = create_service_error("TCG")
        
        assert ai_error.error_type == ErrorType.AI_SERVICE_ERROR
        assert db_error.error_type == ErrorType.DATABASE_ERROR


class TestRaisePokemonScannerError:
    """Test the raise_pokemon_scanner_error function."""

    @patch('src.scanner.services.error_handler.logger')
    def test_raise_pokemon_scanner_error_client_error(self, mock_logger):
        """Test raising a client error."""
        error_details = ErrorDetails(
            error_type=ErrorType.INVALID_INPUT,
            message="Test client error",
            request_id="req-vwx"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            raise_pokemon_scanner_error(error_details)
        
        assert exc_info.value.status_code == 400
        detail = json.loads(exc_info.value.detail)
        assert detail["message"] == "Test client error"
        assert detail["error_type"] == "invalid_input"
        
        mock_logger.info.assert_called_once()

    @patch('src.scanner.services.error_handler.logger')
    def test_raise_pokemon_scanner_error_server_error(self, mock_logger):
        """Test raising a server error."""
        error_details = ErrorDetails(
            error_type=ErrorType.INTERNAL_ERROR,
            message="Test server error"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            raise_pokemon_scanner_error(error_details)
        
        assert exc_info.value.status_code == 500
        mock_logger.error.assert_called_once()

    @patch('src.scanner.services.error_handler.logger')
    def test_raise_pokemon_scanner_error_rate_limit(self, mock_logger):
        """Test raising a rate limit error."""
        error_details = ErrorDetails(
            error_type=ErrorType.RATE_LIMITED,
            message="Rate limit exceeded"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            raise_pokemon_scanner_error(error_details)
        
        assert exc_info.value.status_code == 429
        mock_logger.warning.assert_called_once()

    @patch('src.scanner.services.error_handler.logger')
    def test_raise_pokemon_scanner_error_with_request_id(self, mock_logger):
        """Test raising error with request ID in log."""
        error_details = ErrorDetails(
            error_type=ErrorType.INVALID_INPUT,
            message="Test error",
            request_id="req-123"
        )
        
        with pytest.raises(HTTPException):
            raise_pokemon_scanner_error(error_details)
        
        # Check that request ID is in log message
        log_call = mock_logger.info.call_args[0][0]
        assert "[req-123]" in log_call


class TestHandleUnexpectedError:
    """Test the handle_unexpected_error function."""

    @patch('src.scanner.services.error_handler.logger')
    def test_handle_unexpected_error_minimal(self, mock_logger):
        """Test handling unexpected error with minimal parameters."""
        test_error = ValueError("Test error")
        
        with pytest.raises(HTTPException) as exc_info:
            handle_unexpected_error(test_error)
        
        assert exc_info.value.status_code == 500
        detail = json.loads(exc_info.value.detail)
        assert detail["message"] == "An unexpected error occurred during processing"
        assert detail["error_type"] == "internal_error"
        
        mock_logger.exception.assert_called_once()

    @patch('src.scanner.services.error_handler.logger')
    def test_handle_unexpected_error_complete(self, mock_logger):
        """Test handling unexpected error with all parameters."""
        test_error = RuntimeError("Runtime error")
        
        with pytest.raises(HTTPException) as exc_info:
            handle_unexpected_error(
                test_error,
                context="card_scanning",
                request_id="req-yzz"
            )
        
        detail = json.loads(exc_info.value.detail)
        assert detail["message"] == "An unexpected error occurred during card_scanning"
        assert detail["details"]["context"] == "card_scanning"
        assert detail["request_id"] == "req-yzz"


class TestUtilityFunctions:
    """Test utility functions."""

    def test_is_client_error(self):
        """Test is_client_error function."""
        assert is_client_error(400) is True
        assert is_client_error(404) is True
        assert is_client_error(429) is True
        assert is_client_error(499) is True
        assert is_client_error(399) is False
        assert is_client_error(500) is False
        assert is_client_error(200) is False

    def test_is_server_error(self):
        """Test is_server_error function."""
        assert is_server_error(500) is True
        assert is_server_error(502) is True
        assert is_server_error(503) is True
        assert is_server_error(504) is True
        assert is_server_error(599) is True
        assert is_server_error(499) is False
        assert is_server_error(400) is False
        assert is_server_error(200) is False

    def test_should_retry(self):
        """Test should_retry function."""
        retryable_types = [
            ErrorType.AI_SERVICE_ERROR,
            ErrorType.DATABASE_ERROR,
            ErrorType.SERVICE_UNAVAILABLE,
            ErrorType.TIMEOUT_ERROR,
            ErrorType.INTERNAL_ERROR
        ]
        
        for error_type in retryable_types:
            assert should_retry(error_type) is True
        
        non_retryable_types = [
            ErrorType.INVALID_INPUT,
            ErrorType.CARD_BACK_DETECTED,
            ErrorType.NO_CARD_FOUND,
            ErrorType.RATE_LIMITED
        ]
        
        for error_type in non_retryable_types:
            assert should_retry(error_type) is False

    def test_get_retry_delay(self):
        """Test get_retry_delay function."""
        assert get_retry_delay(ErrorType.RATE_LIMITED) == 60
        assert get_retry_delay(ErrorType.AI_SERVICE_ERROR) == 30
        assert get_retry_delay(ErrorType.DATABASE_ERROR) == 30
        assert get_retry_delay(ErrorType.TIMEOUT_ERROR) == 10
        assert get_retry_delay(ErrorType.INVALID_INPUT) == 5
        assert get_retry_delay(ErrorType.INTERNAL_ERROR) == 5


class TestErrorHandlerIntegration:
    """Test error handler integration scenarios."""

    def test_complete_error_flow(self):
        """Test complete error handling flow."""
        # Create an error
        error_details = create_image_quality_error(
            quality_score=20.0,
            request_id="integration-test"
        )
        
        # Convert to dict
        error_dict = error_details.to_dict()
        
        # Verify structure
        assert error_dict["error_type"] == "image_quality_too_low"
        assert error_dict["quality_score"] == 20.0
        assert error_dict["request_id"] == "integration-test"
        assert "quality_feedback" in error_dict
        
        # Test retryability
        assert should_retry(error_details.error_type) is False
        
        # Test status code classification
        assert is_client_error(error_details.error_type.status_code) is True
        assert is_server_error(error_details.error_type.status_code) is False

    def test_error_serialization(self):
        """Test that error details can be serialized to JSON."""
        error_details = create_non_pokemon_card_error(
            detected_type="Magic card",
            quality_score=85.0,
            request_id="serialization-test"
        )
        
        error_dict = error_details.to_dict()
        
        # Should be JSON serializable
        json_str = json.dumps(error_dict)
        parsed = json.loads(json_str)
        
        assert parsed["error_type"] == "non_pokemon_card"
        assert parsed["quality_score"] == 85.0
        assert "Magic card" in parsed["message"]