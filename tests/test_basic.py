"""Basic tests for Pokemon card scanner."""

import pytest
from unittest.mock import Mock, patch


def test_import_structure():
    """Test that main modules can be imported."""
    # Test basic imports without external dependencies
    from src.scanner.models.schemas import ScanRequest, ScanResponse
    from src.scanner.utils.cost_tracker import CostTracker
    
    # Basic object creation
    request = ScanRequest(image="test_base64_data")
    tracker = CostTracker()
    
    assert request.image == "test_base64_data"
    assert isinstance(tracker.session_costs, list)


def test_cost_tracker():
    """Test cost tracking functionality."""
    from src.scanner.utils.cost_tracker import CostTracker
    
    tracker = CostTracker()
    
    # Test Gemini cost tracking
    cost = tracker.track_gemini_usage(
        prompt_tokens=100,
        response_tokens=200,
        includes_image=True,
        operation="test"
    )
    
    assert cost > 0
    assert len(tracker.session_costs) == 1
    assert tracker.session_costs[0]["service"] == "gemini"
    
    # Test TCG cost tracking
    tcg_cost = tracker.track_tcg_usage("search")
    assert tcg_cost == 0.0
    assert len(tracker.session_costs) == 2
    
    # Test session summary
    summary = tracker.get_session_summary()
    assert summary["total_requests"] == 2
    assert summary["total_cost_usd"] == cost


def test_schemas():
    """Test Pydantic schema validation."""
    from src.scanner.models.schemas import ScanRequest, ScanOptions
    
    # Test valid request
    request = ScanRequest(
        image="base64_data_here",
        filename="test.jpg",
        options=ScanOptions(optimize_for_speed=True)
    )
    
    assert request.image == "base64_data_here"
    assert request.filename == "test.jpg"
    assert request.options.optimize_for_speed is True
    
    # Test default options
    request_minimal = ScanRequest(image="base64_data")
    assert request_minimal.options.optimize_for_speed is True
    assert request_minimal.options.include_cost_tracking is True


@patch('src.scanner.services.image_processor.HEIC_SUPPORTED', True)
def test_image_processor_basic():
    """Test basic image processor functionality."""
    from src.scanner.services.image_processor import ImageProcessor
    
    processor = ImageProcessor()
    
    # Test supported formats
    formats = processor.get_supported_formats()
    assert "JPEG" in formats
    assert "PNG" in formats
    assert formats["JPEG"] is True
    
    # Test validation with invalid data
    is_valid, error = processor.validate_image(b"not_an_image")
    assert not is_valid
    assert "Invalid image file" in error


if __name__ == "__main__":
    pytest.main([__file__])