"""Simple working tests for CostTracker utility."""

import pytest
from datetime import datetime
from src.scanner.utils.cost_tracker import CostTracker


class TestCostTrackerSimple:
    """Simple test cases for CostTracker that match actual interface."""

    @pytest.fixture
    def cost_tracker(self):
        """Create CostTracker instance."""
        return CostTracker()

    def test_initialization(self, cost_tracker):
        """Test basic initialization."""
        assert cost_tracker.session_costs == []
        assert isinstance(cost_tracker.session_start, datetime)
        
        # Check that pricing constants exist
        assert hasattr(cost_tracker, 'GEMINI_COSTS')
        assert hasattr(cost_tracker, 'TCG_API_COSTS')

    def test_track_gemini_usage_basic(self, cost_tracker):
        """Test basic Gemini usage tracking."""
        cost = cost_tracker.track_gemini_usage(
            prompt_tokens=100,
            response_tokens=50,
            includes_image=False,
            operation="test"
        )
        
        # Should return a numeric cost
        assert isinstance(cost, (int, float))
        assert cost >= 0
        
        # Should record the usage
        assert len(cost_tracker.session_costs) == 1
        record = cost_tracker.session_costs[0]
        assert record["service"] == "gemini"
        assert record["prompt_tokens"] == 100
        assert record["response_tokens"] == 50

    def test_track_gemini_usage_with_image(self, cost_tracker):
        """Test Gemini usage with image."""
        cost = cost_tracker.track_gemini_usage(
            prompt_tokens=100,
            response_tokens=50,
            includes_image=True
        )
        
        # Should be higher cost with image
        cost_without_image = cost_tracker.track_gemini_usage(
            prompt_tokens=100,
            response_tokens=50,
            includes_image=False
        )
        
        assert cost > cost_without_image

    def test_track_tcg_usage_basic(self, cost_tracker):
        """Test basic TCG usage tracking."""
        # Check actual method signature
        cost = cost_tracker.track_tcg_usage("search")
        
        # TCG API is free
        assert cost == 0.0
        
        # Should record the usage
        assert len(cost_tracker.session_costs) == 1
        record = cost_tracker.session_costs[0]
        assert record["service"] == "tcg_api"
        assert record["operation"] == "search"

    def test_get_session_summary_structure(self, cost_tracker):
        """Test session summary returns correct structure."""
        summary = cost_tracker.get_session_summary()
        
        # Check basic structure
        assert isinstance(summary, dict)
        assert "session_start" in summary
        assert "total_requests" in summary
        assert "total_cost_usd" in summary
        
        # Should handle empty session
        assert summary["total_requests"] == 0
        assert summary["total_cost_usd"] == 0

    def test_session_summary_with_data(self, cost_tracker):
        """Test session summary with actual data."""
        # Add some usage
        cost_tracker.track_gemini_usage(100, 50, True)
        cost_tracker.track_tcg_usage("search")
        
        summary = cost_tracker.get_session_summary()
        
        assert summary["total_requests"] == 2
        assert summary["total_cost_usd"] > 0  # Should have some cost from Gemini

    def test_reset_session(self, cost_tracker):
        """Test session reset."""
        # Add some data
        cost_tracker.track_gemini_usage(100, 50)
        
        assert len(cost_tracker.session_costs) == 1
        
        # Reset
        cost_tracker.reset_session()
        
        assert len(cost_tracker.session_costs) == 0

    def test_estimate_scan_cost(self, cost_tracker):
        """Test scan cost estimation."""
        # This should work based on the actual implementation
        estimate = cost_tracker.estimate_scan_cost(use_image=True)
        
        assert isinstance(estimate, dict)
        assert "total_cost" in estimate
        assert "token_cost" in estimate
        assert "image_cost" in estimate

    def test_zero_token_usage(self, cost_tracker):
        """Test handling of zero tokens."""
        cost = cost_tracker.track_gemini_usage(0, 0, False)
        
        assert cost == 0.0
        assert len(cost_tracker.session_costs) == 1  # Should still record

    def test_large_token_usage(self, cost_tracker):
        """Test handling of large token counts."""
        cost = cost_tracker.track_gemini_usage(10000, 5000, True)
        
        assert isinstance(cost, (int, float))
        assert cost > 0
        
        record = cost_tracker.session_costs[0]
        assert record["prompt_tokens"] == 10000
        assert record["response_tokens"] == 5000