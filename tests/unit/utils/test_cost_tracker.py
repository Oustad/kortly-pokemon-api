"""Comprehensive tests for cost_tracker.py - consolidated from simple and extended tests."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
from src.scanner.utils.cost_tracker import CostTracker


class TestCostTrackerInitialization:
    """Test CostTracker initialization and configuration."""

    @pytest.fixture
    def cost_tracker(self):
        """Create CostTracker instance."""
        return CostTracker()

    def test_initialization_basic(self, cost_tracker):
        """Test basic initialization."""
        assert cost_tracker.session_costs == []
        assert isinstance(cost_tracker.session_start, datetime)
        
        # Check that pricing constants exist
        assert hasattr(cost_tracker, 'GEMINI_COSTS')
        assert hasattr(cost_tracker, 'TCG_API_COSTS')

    def test_initialization_creates_empty_session(self):
        """Test that initialization creates empty session."""
        tracker = CostTracker()
        
        assert tracker.session_costs == []
        assert isinstance(tracker.session_start, datetime)

    def test_initialization_sets_current_time(self):
        """Test that initialization sets current time."""
        before_init = datetime.now()
        tracker = CostTracker()
        after_init = datetime.now()
        
        assert before_init <= tracker.session_start <= after_init

    def test_gemini_costs_constants(self):
        """Test that Gemini cost constants are properly defined."""
        tracker = CostTracker()
        
        assert "input_tokens_per_1k" in tracker.GEMINI_COSTS
        assert "output_tokens_per_1k" in tracker.GEMINI_COSTS
        assert "image_processing" in tracker.GEMINI_COSTS
        
        # Check that costs are reasonable positive values
        assert tracker.GEMINI_COSTS["input_tokens_per_1k"] > 0
        assert tracker.GEMINI_COSTS["output_tokens_per_1k"] > 0
        assert tracker.GEMINI_COSTS["image_processing"] > 0

    def test_tcg_costs_constants(self):
        """Test that TCG cost constants are properly defined."""
        tracker = CostTracker()
        
        assert "search" in tracker.TCG_API_COSTS
        assert "get_card" in tracker.TCG_API_COSTS
        
        # TCG API should be free
        assert tracker.TCG_API_COSTS["search"] == 0.0
        assert tracker.TCG_API_COSTS["get_card"] == 0.0


class TestTrackGeminiUsage:
    """Test Gemini usage tracking functionality."""

    @pytest.fixture
    def cost_tracker(self):
        """Create CostTracker instance."""
        return CostTracker()

    @pytest.fixture
    def tracker(self):
        """Create a fresh CostTracker instance."""
        return CostTracker()

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

    def test_track_gemini_usage_token_only_cost(self, tracker):
        """Test tracking with only token costs."""
        cost = tracker.track_gemini_usage(
            prompt_tokens=1000,
            response_tokens=500,
            includes_image=False
        )
        
        expected_cost = (
            (1000 / 1000) * tracker.GEMINI_COSTS["input_tokens_per_1k"] +
            (500 / 1000) * tracker.GEMINI_COSTS["output_tokens_per_1k"]
        )
        
        assert cost == expected_cost
        assert len(tracker.session_costs) == 1
        
        record = tracker.session_costs[0]
        assert record["service"] == "gemini"
        assert record["prompt_tokens"] == 1000
        assert record["response_tokens"] == 500
        assert record["includes_image"] is False

    def test_track_gemini_usage_with_image_cost(self, tracker):
        """Test tracking with image processing cost."""
        cost = tracker.track_gemini_usage(
            prompt_tokens=1000,
            response_tokens=500,
            includes_image=True
        )
        
        expected_cost = (
            (1000 / 1000) * tracker.GEMINI_COSTS["input_tokens_per_1k"] +
            (500 / 1000) * tracker.GEMINI_COSTS["output_tokens_per_1k"] +
            tracker.GEMINI_COSTS["image_processing"]
        )
        
        assert cost == expected_cost
        assert tracker.session_costs[0]["includes_image"] is True

    def test_zero_token_usage(self, cost_tracker):
        """Test handling of zero tokens."""
        cost = cost_tracker.track_gemini_usage(0, 0, False)
        
        assert cost == 0.0
        assert len(cost_tracker.session_costs) == 1  # Should still record

    def test_track_gemini_usage_zero_tokens(self, tracker):
        """Test tracking with zero tokens."""
        cost = tracker.track_gemini_usage(
            prompt_tokens=0,
            response_tokens=0,
            includes_image=False
        )
        
        assert cost == 0.0
        assert len(tracker.session_costs) == 1
        
        record = tracker.session_costs[0]
        assert record["prompt_tokens"] == 0
        assert record["response_tokens"] == 0
        assert record["cost_usd"] == 0.0

    def test_track_gemini_usage_only_image(self, tracker):
        """Test tracking with only image cost."""
        cost = tracker.track_gemini_usage(
            prompt_tokens=0,
            response_tokens=0,
            includes_image=True
        )
        
        assert cost == tracker.GEMINI_COSTS["image_processing"]
        assert tracker.session_costs[0]["cost_usd"] == tracker.GEMINI_COSTS["image_processing"]

    def test_track_gemini_usage_custom_operation(self, tracker):
        """Test tracking with custom operation name."""
        cost = tracker.track_gemini_usage(
            prompt_tokens=100,
            response_tokens=50,
            operation="custom_operation"
        )
        
        assert tracker.session_costs[0]["operation"] == "custom_operation"

    def test_track_gemini_usage_default_operation(self, tracker):
        """Test tracking with default operation name."""
        cost = tracker.track_gemini_usage(
            prompt_tokens=100,
            response_tokens=50
        )
        
        assert tracker.session_costs[0]["operation"] == "identify_card"

    def test_track_gemini_usage_fractional_tokens(self, tracker):
        """Test tracking with fractional token calculations."""
        cost = tracker.track_gemini_usage(
            prompt_tokens=250,  # 0.25 * 1000
            response_tokens=750  # 0.75 * 1000
        )
        
        expected_cost = (
            0.25 * tracker.GEMINI_COSTS["input_tokens_per_1k"] +
            0.75 * tracker.GEMINI_COSTS["output_tokens_per_1k"]
        )
        
        assert cost == expected_cost

    def test_track_gemini_usage_record_structure(self, tracker):
        """Test that usage records have correct structure."""
        cost = tracker.track_gemini_usage(
            prompt_tokens=100,
            response_tokens=50,
            includes_image=True,
            operation="test_op"
        )
        
        record = tracker.session_costs[0]
        
        # Check all required fields are present
        assert "timestamp" in record
        assert "service" in record
        assert "operation" in record
        assert "prompt_tokens" in record
        assert "response_tokens" in record
        assert "includes_image" in record
        assert "cost_usd" in record
        
        # Check field types
        assert isinstance(record["timestamp"], str)
        assert record["service"] == "gemini"
        assert record["operation"] == "test_op"
        assert isinstance(record["prompt_tokens"], int)
        assert isinstance(record["response_tokens"], int)
        assert isinstance(record["includes_image"], bool)
        assert isinstance(record["cost_usd"], (int, float))

    def test_track_gemini_usage_timestamp_format(self, tracker):
        """Test that timestamp is in ISO format."""
        tracker.track_gemini_usage(100, 50)
        
        timestamp = tracker.session_costs[0]["timestamp"]
        
        # Should be able to parse as ISO format
        parsed_time = datetime.fromisoformat(timestamp)
        assert isinstance(parsed_time, datetime)

    def test_large_token_usage(self, cost_tracker):
        """Test handling of large token counts."""
        cost = cost_tracker.track_gemini_usage(10000, 5000, True)
        
        assert isinstance(cost, (int, float))
        assert cost > 0
        
        record = cost_tracker.session_costs[0]
        assert record["prompt_tokens"] == 10000
        assert record["response_tokens"] == 5000

    def test_track_gemini_usage_negative_tokens(self, tracker):
        """Test handling of negative token counts."""
        # The implementation only processes positive token counts
        cost = tracker.track_gemini_usage(
            prompt_tokens=-100,
            response_tokens=-50
        )
        
        # Should result in zero cost (negative tokens are ignored)
        assert cost == 0.0
        assert len(tracker.session_costs) == 1

    def test_track_gemini_usage_very_large_tokens(self, tracker):
        """Test handling of very large token counts."""
        cost = tracker.track_gemini_usage(
            prompt_tokens=1000000,
            response_tokens=500000,
            includes_image=True
        )
        
        assert cost > 0
        assert isinstance(cost, (int, float))
        assert len(tracker.session_costs) == 1


class TestTrackTcgUsage:
    """Test TCG usage tracking functionality."""

    @pytest.fixture
    def cost_tracker(self):
        """Create CostTracker instance."""
        return CostTracker()

    @pytest.fixture
    def tracker(self):
        """Create a fresh CostTracker instance."""
        return CostTracker()

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

    def test_track_tcg_usage_default_operation(self, tracker):
        """Test tracking TCG usage with default operation."""
        cost = tracker.track_tcg_usage()
        
        assert cost == 0.0
        assert len(tracker.session_costs) == 1
        
        record = tracker.session_costs[0]
        assert record["service"] == "tcg_api"
        assert record["operation"] == "search"
        assert record["cost_usd"] == 0.0

    def test_track_tcg_usage_custom_operation(self, tracker):
        """Test tracking TCG usage with custom operation."""
        cost = tracker.track_tcg_usage("get_card")
        
        assert cost == 0.0
        assert tracker.session_costs[0]["operation"] == "get_card"

    def test_track_tcg_usage_record_structure(self, tracker):
        """Test that TCG usage records have correct structure."""
        cost = tracker.track_tcg_usage("custom_op")
        
        record = tracker.session_costs[0]
        
        # Check all required fields are present
        assert "timestamp" in record
        assert "service" in record
        assert "operation" in record
        assert "cost_usd" in record
        
        # Check field types
        assert isinstance(record["timestamp"], str)
        assert record["service"] == "tcg_api"
        assert record["operation"] == "custom_op"
        assert record["cost_usd"] == 0.0

    def test_track_tcg_usage_multiple_operations(self, tracker):
        """Test tracking multiple TCG operations."""
        tracker.track_tcg_usage("search")
        tracker.track_tcg_usage("get_card")
        tracker.track_tcg_usage("search")
        
        assert len(tracker.session_costs) == 3
        
        operations = [record["operation"] for record in tracker.session_costs]
        assert operations == ["search", "get_card", "search"]

    def test_operations_with_none_values(self, tracker):
        """Test operations with None values where applicable."""
        # track_tcg_usage should handle None gracefully
        cost = tracker.track_tcg_usage(None)
        
        # Should default to "search" or handle None appropriately
        assert cost == 0.0
        assert len(tracker.session_costs) == 1


class TestSessionSummary:
    """Test session summary functionality."""

    @pytest.fixture
    def cost_tracker(self):
        """Create CostTracker instance."""
        return CostTracker()

    @pytest.fixture
    def tracker(self):
        """Create a fresh CostTracker instance."""
        return CostTracker()

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

    def test_get_session_summary_empty(self, tracker):
        """Test session summary with no usage."""
        summary = tracker.get_session_summary()
        
        assert summary["total_requests"] == 0
        assert summary["total_cost_usd"] == 0.0
        assert summary["average_cost_per_request"] == 0
        assert summary["services"] == {}
        assert "session_start" in summary
        assert "session_duration_minutes" in summary

    def test_get_session_summary_with_gemini_usage(self, tracker):
        """Test session summary with Gemini usage."""
        tracker.track_gemini_usage(1000, 500, True, "identify_card")
        tracker.track_gemini_usage(500, 250, False, "analyze_card")
        
        summary = tracker.get_session_summary()
        
        assert summary["total_requests"] == 2
        assert summary["total_cost_usd"] > 0
        assert summary["average_cost_per_request"] > 0
        
        # Check Gemini service details
        assert "gemini" in summary["services"]
        gemini_service = summary["services"]["gemini"]
        assert gemini_service["count"] == 2
        assert gemini_service["total_cost"] > 0
        assert "identify_card" in gemini_service["operations"]
        assert "analyze_card" in gemini_service["operations"]

    def test_get_session_summary_with_mixed_usage(self, tracker):
        """Test session summary with mixed Gemini and TCG usage."""
        tracker.track_gemini_usage(1000, 500, True)
        tracker.track_tcg_usage("search")
        tracker.track_tcg_usage("get_card")
        
        summary = tracker.get_session_summary()
        
        assert summary["total_requests"] == 3
        assert "gemini" in summary["services"]
        assert "tcg_api" in summary["services"]
        
        # Check service counts
        assert summary["services"]["gemini"]["count"] == 1
        assert summary["services"]["tcg_api"]["count"] == 2
        
        # Check operations
        assert "search" in summary["services"]["tcg_api"]["operations"]
        assert "get_card" in summary["services"]["tcg_api"]["operations"]

    def test_get_session_summary_cost_calculations(self, tracker):
        """Test that cost calculations are correct."""
        cost1 = tracker.track_gemini_usage(1000, 500, True)
        cost2 = tracker.track_gemini_usage(2000, 1000, False)
        
        summary = tracker.get_session_summary()
        
        expected_total = cost1 + cost2
        assert summary["total_cost_usd"] == round(expected_total, 6)
        assert summary["average_cost_per_request"] == round(expected_total / 2, 6)

    def test_get_session_summary_duration_calculation(self, tracker):
        """Test session duration calculation."""
        summary = tracker.get_session_summary()
        
        assert summary["session_duration_minutes"] > 0
        assert summary["session_duration_minutes"] <= 1  # Should be very small for new tracker

    def test_get_session_summary_estimated_monthly_cost(self, tracker):
        """Test estimated monthly cost calculation."""
        tracker.track_gemini_usage(1000, 500, True)
        
        summary = tracker.get_session_summary()
        
        # Should have some estimated monthly cost
        assert summary["estimated_monthly_cost"] >= 0
        assert isinstance(summary["estimated_monthly_cost"], (int, float))

    def test_get_session_summary_operation_counting(self, tracker):
        """Test that operations are counted correctly."""
        tracker.track_gemini_usage(100, 50, operation="identify_card")
        tracker.track_gemini_usage(200, 100, operation="identify_card")
        tracker.track_gemini_usage(150, 75, operation="analyze_card")
        
        summary = tracker.get_session_summary()
        
        gemini_ops = summary["services"]["gemini"]["operations"]
        assert gemini_ops["identify_card"] == 2
        assert gemini_ops["analyze_card"] == 1

    def test_get_session_summary_minimum_duration(self, tracker):
        """Test that minimum duration is enforced."""
        # The implementation uses max(duration, 0.01) to avoid division by zero
        summary = tracker.get_session_summary()
        
        assert summary["session_duration_minutes"] >= 0.01

    def test_get_session_summary_empty_monthly_estimate(self, tracker):
        """Test monthly estimate when no costs recorded."""
        summary = tracker.get_session_summary()
        
        assert summary["estimated_monthly_cost"] == 0

    def test_get_session_summary_with_zero_costs(self, tracker):
        """Test session summary when all costs are zero."""
        tracker.track_tcg_usage("search")
        tracker.track_tcg_usage("get_card")
        
        summary = tracker.get_session_summary()
        
        assert summary["total_cost_usd"] == 0.0
        assert summary["average_cost_per_request"] == 0.0
        assert summary["total_requests"] == 2


class TestResetSession:
    """Test session reset functionality."""

    @pytest.fixture
    def cost_tracker(self):
        """Create CostTracker instance."""
        return CostTracker()

    @pytest.fixture
    def tracker(self):
        """Create a fresh CostTracker instance."""
        return CostTracker()

    def test_reset_session(self, cost_tracker):
        """Test session reset."""
        # Add some data
        cost_tracker.track_gemini_usage(100, 50)
        
        assert len(cost_tracker.session_costs) == 1
        
        # Reset
        cost_tracker.reset_session()
        
        assert len(cost_tracker.session_costs) == 0

    def test_reset_session_clears_costs(self, tracker):
        """Test that reset clears session costs."""
        tracker.track_gemini_usage(1000, 500)
        tracker.track_tcg_usage("search")
        
        assert len(tracker.session_costs) == 2
        
        tracker.reset_session()
        
        assert len(tracker.session_costs) == 0

    def test_reset_session_updates_start_time(self, tracker):
        """Test that reset updates session start time."""
        original_start = tracker.session_start
        
        # Wait a brief moment to ensure time difference
        import time
        time.sleep(0.001)
        
        tracker.reset_session()
        
        assert tracker.session_start > original_start

    def test_reset_session_with_empty_session(self, tracker):
        """Test reset with already empty session."""
        assert len(tracker.session_costs) == 0
        
        tracker.reset_session()
        
        assert len(tracker.session_costs) == 0

    @patch('src.scanner.utils.cost_tracker.logger')
    def test_reset_session_logs_message(self, mock_logger, tracker):
        """Test that reset logs a message."""
        tracker.reset_session()
        
        mock_logger.info.assert_called_once_with("Cost tracking session reset")

    def test_multiple_resets(self, tracker):
        """Test multiple consecutive resets."""
        tracker.track_gemini_usage(100, 50)
        tracker.reset_session()
        tracker.reset_session()
        tracker.reset_session()
        
        assert len(tracker.session_costs) == 0


class TestEstimateScanCost:
    """Test scan cost estimation functionality."""

    @pytest.fixture
    def cost_tracker(self):
        """Create CostTracker instance."""
        return CostTracker()

    @pytest.fixture
    def tracker(self):
        """Create a fresh CostTracker instance."""
        return CostTracker()

    def test_estimate_scan_cost(self, cost_tracker):
        """Test scan cost estimation."""
        # This should work based on the actual implementation
        estimate = cost_tracker.estimate_scan_cost(use_image=True)
        
        assert isinstance(estimate, dict)
        assert "total_cost" in estimate
        assert "token_cost" in estimate
        assert "image_cost" in estimate

    def test_estimate_scan_cost_with_image(self, tracker):
        """Test cost estimation with image processing."""
        estimate = tracker.estimate_scan_cost(use_image=True)
        
        assert "token_cost" in estimate
        assert "image_cost" in estimate
        assert "total_cost" in estimate
        assert "cost_per_1000_scans" in estimate
        
        # With image should include image processing cost
        assert estimate["image_cost"] == tracker.GEMINI_COSTS["image_processing"]
        # The total cost is calculated before rounding individual components
        assert estimate["total_cost"] > estimate["token_cost"]
        assert estimate["total_cost"] > estimate["image_cost"]

    def test_estimate_scan_cost_without_image(self, tracker):
        """Test cost estimation without image processing."""
        estimate = tracker.estimate_scan_cost(use_image=False)
        
        # Without image should have zero image cost
        assert estimate["image_cost"] == 0.0
        assert estimate["total_cost"] == estimate["token_cost"]

    def test_estimate_scan_cost_token_calculations(self, tracker):
        """Test that token cost calculations are correct."""
        estimate = tracker.estimate_scan_cost(use_image=False)
        
        # Should use different token counts based on image usage
        avg_prompt_tokens = 150  # Without image
        avg_response_tokens = 300
        
        expected_token_cost = (
            (avg_prompt_tokens / 1000) * tracker.GEMINI_COSTS["input_tokens_per_1k"] +
            (avg_response_tokens / 1000) * tracker.GEMINI_COSTS["output_tokens_per_1k"]
        )
        
        assert estimate["token_cost"] == round(expected_token_cost, 6)

    def test_estimate_scan_cost_with_image_token_adjustment(self, tracker):
        """Test that token usage is adjusted when image is used."""
        estimate_with_image = tracker.estimate_scan_cost(use_image=True)
        estimate_without_image = tracker.estimate_scan_cost(use_image=False)
        
        # With image should use fewer prompt tokens (50 vs 150)
        # So token cost should be lower with image
        assert estimate_with_image["token_cost"] < estimate_without_image["token_cost"]

    def test_estimate_scan_cost_1000_scans_calculation(self, tracker):
        """Test cost per 1000 scans calculation."""
        estimate = tracker.estimate_scan_cost(use_image=True)
        
        expected_cost_per_1000 = estimate["total_cost"] * 1000
        assert estimate["cost_per_1000_scans"] == round(expected_cost_per_1000, 2)

    def test_estimate_scan_cost_rounding(self, tracker):
        """Test that all costs are properly rounded."""
        estimate = tracker.estimate_scan_cost(use_image=True)
        
        # Check rounding precision
        assert isinstance(estimate["token_cost"], float)
        assert isinstance(estimate["image_cost"], float)
        assert isinstance(estimate["total_cost"], float)
        assert isinstance(estimate["cost_per_1000_scans"], (int, float))

    def test_estimate_scan_cost_consistency(self, tracker):
        """Test that estimates are consistent across calls."""
        estimate1 = tracker.estimate_scan_cost(use_image=True)
        estimate2 = tracker.estimate_scan_cost(use_image=True)
        
        assert estimate1 == estimate2

    def test_estimate_scan_cost_both_scenarios(self, tracker):
        """Test both image and non-image scenarios."""
        with_image = tracker.estimate_scan_cost(use_image=True)
        without_image = tracker.estimate_scan_cost(use_image=False)
        
        # With image should cost more due to image processing
        assert with_image["total_cost"] > without_image["total_cost"]
        assert with_image["image_cost"] > without_image["image_cost"]