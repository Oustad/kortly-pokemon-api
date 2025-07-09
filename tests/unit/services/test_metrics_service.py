"""Comprehensive tests for metrics_service.py - consolidated from simple and extended tests."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, Mock

from src.scanner.services.metrics_service import (
    MetricsService,
    RequestMetrics,
    ServiceMetrics,
    get_metrics_service
)


class TestRequestMetrics:
    """Test the RequestMetrics dataclass."""

    def test_request_metrics_initialization_minimal(self):
        """Test RequestMetrics initialization with minimal parameters."""
        timestamp = datetime.now()
        metrics = RequestMetrics(
            timestamp=timestamp,
            endpoint="/api/v1/scan",
            method="POST",
            status_code=200,
            processing_time_ms=150.5
        )
        
        assert metrics.timestamp == timestamp
        assert metrics.endpoint == "/api/v1/scan"
        assert metrics.method == "POST"
        assert metrics.status_code == 200
        assert metrics.processing_time_ms == 150.5
        assert metrics.image_size_bytes is None
        assert metrics.gemini_cost is None
        assert metrics.tcg_matches is None
        assert metrics.error_type is None

    def test_request_metrics_initialization_complete(self):
        """Test RequestMetrics initialization with all parameters."""
        timestamp = datetime.now()
        metrics = RequestMetrics(
            timestamp=timestamp,
            endpoint="/api/v1/scan",
            method="POST",
            status_code=200,
            processing_time_ms=150.5,
            image_size_bytes=1024000,
            gemini_cost=0.0025,
            tcg_matches=5,
            error_type=None
        )
        
        assert metrics.image_size_bytes == 1024000
        assert metrics.gemini_cost == 0.0025
        assert metrics.tcg_matches == 5
        assert metrics.error_type is None

    def test_request_metrics_with_error(self):
        """Test RequestMetrics with error type."""
        timestamp = datetime.now()
        metrics = RequestMetrics(
            timestamp=timestamp,
            endpoint="/api/v1/scan",
            method="POST",
            status_code=400,
            processing_time_ms=50.0,
            error_type="invalid_input"
        )
        
        assert metrics.status_code == 400
        assert metrics.error_type == "invalid_input"


class TestServiceMetrics:
    """Test the ServiceMetrics dataclass."""

    def test_service_metrics_initialization(self):
        """Test ServiceMetrics initialization with default values."""
        metrics = ServiceMetrics()
        
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.avg_response_time_ms == 0.0
        assert metrics.min_response_time_ms == float('inf')
        assert metrics.max_response_time_ms == 0.0
        assert metrics.gemini_api_calls == 0
        assert metrics.tcg_api_calls == 0
        assert metrics.total_cost_usd == 0.0
        assert metrics.images_processed == 0
        assert metrics.total_image_size_mb == 0.0
        assert metrics.heic_images == 0
        assert metrics.cache_hits == 0
        assert metrics.cache_misses == 0
        assert metrics.errors_by_type == {}
        assert isinstance(metrics.start_time, datetime)
        assert metrics.last_request_time is None

    def test_service_metrics_with_custom_values(self):
        """Test ServiceMetrics with custom initialization values."""
        start_time = datetime.now()
        last_request_time = datetime.now()
        
        metrics = ServiceMetrics(
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            avg_response_time_ms=250.0,
            min_response_time_ms=50.0,
            max_response_time_ms=1000.0,
            start_time=start_time,
            last_request_time=last_request_time
        )
        
        assert metrics.total_requests == 100
        assert metrics.successful_requests == 95
        assert metrics.failed_requests == 5
        assert metrics.avg_response_time_ms == 250.0
        assert metrics.min_response_time_ms == 50.0
        assert metrics.max_response_time_ms == 1000.0
        assert metrics.start_time == start_time
        assert metrics.last_request_time == last_request_time


class TestMetricsServiceInitialization:
    """Test MetricsService initialization."""

    def test_metrics_service_initialization(self):
        """Test that MetricsService initializes correctly."""
        service = MetricsService()
        
        assert isinstance(service.metrics, ServiceMetrics)
        assert service.recent_requests == []
        assert service.response_times == []
        assert service._hourly_metrics is not None
        assert len(service._hourly_metrics) == 0

    def test_initialization_basic(self):
        """Test basic MetricsService initialization."""
        metrics_service = MetricsService()
        assert hasattr(metrics_service, 'metrics')
        assert hasattr(metrics_service, 'recent_requests')
        assert hasattr(metrics_service, 'response_times')
        assert isinstance(metrics_service.metrics, object)

    def test_metrics_service_singleton_pattern(self):
        """Test that get_metrics_service returns the same instance."""
        service1 = get_metrics_service()
        service2 = get_metrics_service()
        
        assert service1 is service2
        assert isinstance(service1, MetricsService)


class TestRecordRequest:
    """Test the record_request method."""

    @pytest.fixture
    def service(self):
        """Create a fresh MetricsService instance."""
        return MetricsService()

    def test_record_request_method_basic(self, service):
        """Test record_request method."""
        from datetime import datetime
        from src.scanner.services.metrics_service import RequestMetrics
        
        # Create test request metrics
        request_metrics = RequestMetrics(
            timestamp=datetime.now(),
            endpoint="/api/scan",
            method="POST",
            status_code=200,
            processing_time_ms=100.0
        )
        
        # Record the request
        with patch('src.scanner.services.metrics_service.config.enable_metrics', True):
            service.record_request(request_metrics)
            
            # Should update metrics
            assert service.metrics.total_requests == 1
            assert service.metrics.successful_requests == 1

    @patch('src.scanner.services.metrics_service.config')
    def test_record_request_successful(self, mock_config, service):
        """Test recording a successful request."""
        mock_config.enable_metrics = True
        
        request_metrics = RequestMetrics(
            timestamp=datetime.now(),
            endpoint="/api/v1/scan",
            method="POST",
            status_code=200,
            processing_time_ms=150.5,
            image_size_bytes=1024000,
            gemini_cost=0.0025,
            tcg_matches=3
        )
        
        service.record_request(request_metrics)
        
        assert service.metrics.total_requests == 1
        assert service.metrics.successful_requests == 1
        assert service.metrics.failed_requests == 0
        assert service.metrics.gemini_api_calls == 1
        assert service.metrics.tcg_api_calls == 1
        assert service.metrics.total_cost_usd == 0.0025
        assert service.metrics.images_processed == 1
        assert abs(service.metrics.total_image_size_mb - 1.0) < 0.1  # Allow for floating point precision
        assert len(service.recent_requests) == 1
        assert service.metrics.last_request_time == request_metrics.timestamp

    @patch('src.scanner.services.metrics_service.config')
    def test_record_request_failed(self, mock_config, service):
        """Test recording a failed request."""
        mock_config.enable_metrics = True
        
        request_metrics = RequestMetrics(
            timestamp=datetime.now(),
            endpoint="/api/v1/scan",
            method="POST",
            status_code=400,
            processing_time_ms=50.0,
            error_type="invalid_input"
        )
        
        service.record_request(request_metrics)
        
        assert service.metrics.total_requests == 1
        assert service.metrics.successful_requests == 0
        assert service.metrics.failed_requests == 1
        assert service.metrics.errors_by_type["invalid_input"] == 1

    @patch('src.scanner.services.metrics_service.config')
    def test_record_request_metrics_disabled(self, mock_config, service):
        """Test recording when metrics are disabled."""
        mock_config.enable_metrics = False
        
        request_metrics = RequestMetrics(
            timestamp=datetime.now(),
            endpoint="/api/v1/scan",
            method="POST",
            status_code=200,
            processing_time_ms=150.5
        )
        
        service.record_request(request_metrics)
        
        # Should not record anything
        assert service.metrics.total_requests == 0
        assert service.metrics.successful_requests == 0

    @patch('src.scanner.services.metrics_service.config')
    def test_record_request_response_time_updates(self, mock_config, service):
        """Test that response time metrics are updated correctly."""
        mock_config.enable_metrics = True
        
        # Record first request
        request1 = RequestMetrics(
            timestamp=datetime.now(),
            endpoint="/api/v1/scan",
            method="POST",
            status_code=200,
            processing_time_ms=100.0
        )
        service.record_request(request1)
        
        # Record second request
        request2 = RequestMetrics(
            timestamp=datetime.now(),
            endpoint="/api/v1/scan",
            method="POST",
            status_code=200,
            processing_time_ms=200.0
        )
        service.record_request(request2)
        
        assert service.metrics.min_response_time_ms == 100.0
        assert service.metrics.max_response_time_ms == 200.0
        assert service.metrics.avg_response_time_ms == 150.0

    @patch('src.scanner.services.metrics_service.config')
    def test_record_request_recent_requests_limit(self, mock_config, service):
        """Test that recent requests are limited to 100."""
        mock_config.enable_metrics = True
        
        # Record 105 requests
        for i in range(105):
            request_metrics = RequestMetrics(
                timestamp=datetime.now(),
                endpoint="/api/v1/scan",
                method="POST",
                status_code=200,
                processing_time_ms=100.0
            )
            service.record_request(request_metrics)
        
        # Should only keep the last 100
        assert len(service.recent_requests) == 100
        assert service.metrics.total_requests == 105

    @patch('src.scanner.services.metrics_service.config')
    def test_record_request_hourly_metrics(self, mock_config, service):
        """Test hourly metrics tracking."""
        mock_config.enable_metrics = True
        
        now = datetime.now()
        request_metrics = RequestMetrics(
            timestamp=now,
            endpoint="/api/v1/scan",
            method="POST",
            status_code=200,
            processing_time_ms=100.0
        )
        
        service.record_request(request_metrics)
        
        # Check that hourly metrics were created
        hour_key = now.replace(minute=0, second=0, microsecond=0)
        assert hour_key in service._hourly_metrics
        assert service._hourly_metrics[hour_key].total_requests == 1
        assert service._hourly_metrics[hour_key].successful_requests == 1

    @patch('src.scanner.services.metrics_service.config')
    def test_record_request_hourly_metrics_cleanup(self, mock_config, service):
        """Test that old hourly metrics are cleaned up."""
        mock_config.enable_metrics = True
        
        # Create old metrics (25 hours ago)
        old_time = datetime.now() - timedelta(hours=25)
        service._hourly_metrics[old_time] = ServiceMetrics(total_requests=1)
        
        # Record new request
        request_metrics = RequestMetrics(
            timestamp=datetime.now(),
            endpoint="/api/v1/scan",
            method="POST",
            status_code=200,
            processing_time_ms=100.0
        )
        service.record_request(request_metrics)
        
        # Old metrics should be cleaned up
        assert old_time not in service._hourly_metrics

    @patch('src.scanner.services.metrics_service.config')
    def test_record_request_non_scan_endpoint(self, mock_config, service):
        """Test recording request for non-scan endpoint."""
        mock_config.enable_metrics = True
        
        request_metrics = RequestMetrics(
            timestamp=datetime.now(),
            endpoint="/health",
            method="GET",
            status_code=200,
            processing_time_ms=10.0
        )
        
        service.record_request(request_metrics)
        
        # Should not increment API calls for non-scan endpoints
        assert service.metrics.gemini_api_calls == 0
        assert service.metrics.tcg_api_calls == 0
        assert service.metrics.total_requests == 1

    @patch('src.scanner.services.metrics_service.config')
    def test_record_request_error_counting(self, mock_config, service):
        """Test that errors are counted by type."""
        mock_config.enable_metrics = True
        
        # Record multiple errors of different types
        error_types = ["invalid_input", "image_quality_too_low", "invalid_input"]
        
        for error_type in error_types:
            request_metrics = RequestMetrics(
                timestamp=datetime.now(),
                endpoint="/api/v1/scan",
                method="POST",
                status_code=400,
                processing_time_ms=50.0,
                error_type=error_type
            )
            service.record_request(request_metrics)
        
        assert service.metrics.errors_by_type["invalid_input"] == 2
        assert service.metrics.errors_by_type["image_quality_too_low"] == 1

    @patch('src.scanner.services.metrics_service.config')
    def test_record_request_with_zero_cost(self, mock_config, service):
        """Test recording request with zero cost."""
        mock_config.enable_metrics = True
        
        request_metrics = RequestMetrics(
            timestamp=datetime.now(),
            endpoint="/api/v1/scan",
            method="POST",
            status_code=200,
            processing_time_ms=100.0,
            gemini_cost=0.0
        )
        
        service.record_request(request_metrics)
        
        assert service.metrics.total_cost_usd == 0.0

    @patch('src.scanner.services.metrics_service.config')
    def test_record_request_with_none_values(self, mock_config, service):
        """Test recording request with None values."""
        mock_config.enable_metrics = True
        
        request_metrics = RequestMetrics(
            timestamp=datetime.now(),
            endpoint="/api/v1/scan",
            method="POST",
            status_code=200,
            processing_time_ms=100.0,
            image_size_bytes=None,
            gemini_cost=None,
            tcg_matches=None
        )
        
        service.record_request(request_metrics)
        
        # Should handle None values gracefully
        assert service.metrics.total_requests == 1
        assert service.metrics.images_processed == 0
        assert service.metrics.total_cost_usd == 0.0


class TestCacheMetrics:
    """Test cache-related metrics methods."""

    @pytest.fixture
    def service(self):
        """Create a fresh MetricsService instance."""
        return MetricsService()

    def test_record_cache_hit_method(self, service):
        """Test record_cache_hit method."""
        initial_hits = service.metrics.cache_hits
        
        with patch('src.scanner.services.metrics_service.config.enable_metrics', True):
            service.record_cache_hit()
            
            # Should increment cache hits
            assert service.metrics.cache_hits == initial_hits + 1

    @patch('src.scanner.services.metrics_service.config')
    def test_record_cache_hit(self, mock_config, service):
        """Test recording cache hits."""
        mock_config.enable_metrics = True
        
        service.record_cache_hit()
        service.record_cache_hit()
        
        assert service.metrics.cache_hits == 2
        assert service.metrics.cache_misses == 0

    def test_record_cache_miss_method(self, service):
        """Test record_cache_miss method."""
        initial_misses = service.metrics.cache_misses
        
        with patch('src.scanner.services.metrics_service.config.enable_metrics', True):
            service.record_cache_miss()
            
            # Should increment cache misses
            assert service.metrics.cache_misses == initial_misses + 1

    @patch('src.scanner.services.metrics_service.config')
    def test_record_cache_miss(self, mock_config, service):
        """Test recording cache misses."""
        mock_config.enable_metrics = True
        
        service.record_cache_miss()
        service.record_cache_miss()
        service.record_cache_miss()
        
        assert service.metrics.cache_misses == 3
        assert service.metrics.cache_hits == 0

    @patch('src.scanner.services.metrics_service.config')
    def test_record_cache_disabled(self, mock_config, service):
        """Test cache recording when metrics are disabled."""
        mock_config.enable_metrics = False
        
        service.record_cache_hit()
        service.record_cache_miss()
        
        assert service.metrics.cache_hits == 0
        assert service.metrics.cache_misses == 0


class TestGetCurrentMetrics:
    """Test the get_current_metrics method."""

    @pytest.fixture
    def service(self):
        """Create a fresh MetricsService instance."""
        return MetricsService()

    def test_get_current_metrics_method(self, service):
        """Test get_current_metrics method."""
        # Get current metrics
        with patch('src.scanner.services.metrics_service.config.enable_metrics', True):
            metrics = service.get_current_metrics()
        
        assert isinstance(metrics, dict)
        assert 'requests' in metrics
        assert 'total' in metrics['requests']
        assert 'successful' in metrics['requests']
        assert 'failed' in metrics['requests']
        assert 'uptime_seconds' in metrics

    @patch('src.scanner.services.metrics_service.config')
    def test_get_current_metrics_disabled(self, mock_config, service):
        """Test getting metrics when disabled."""
        mock_config.enable_metrics = False
        
        metrics = service.get_current_metrics()
        
        assert metrics == {"metrics_disabled": True}

    @patch('src.scanner.services.metrics_service.config')
    def test_get_current_metrics_empty(self, mock_config, service):
        """Test getting metrics with no recorded requests."""
        mock_config.enable_metrics = True
        
        metrics = service.get_current_metrics()
        
        assert "uptime_seconds" in metrics
        assert "uptime_human" in metrics
        assert metrics["requests"]["total"] == 0
        assert metrics["requests"]["successful"] == 0
        assert metrics["requests"]["failed"] == 0
        assert metrics["requests"]["rate_per_second"] == 0
        assert metrics["requests"]["error_rate_percent"] == 0

    @patch('src.scanner.services.metrics_service.config')
    def test_get_current_metrics_with_data(self, mock_config, service):
        """Test getting metrics with recorded data."""
        mock_config.enable_metrics = True
        
        # Record some requests
        for i in range(5):
            request_metrics = RequestMetrics(
                timestamp=datetime.now(),
                endpoint="/api/v1/scan",
                method="POST",
                status_code=200,
                processing_time_ms=100.0 + i * 10,
                image_size_bytes=1024000,
                gemini_cost=0.0025
            )
            service.record_request(request_metrics)
        
        # Record one failed request
        failed_request = RequestMetrics(
            timestamp=datetime.now(),
            endpoint="/api/v1/scan",
            method="POST",
            status_code=400,
            processing_time_ms=50.0,
            error_type="invalid_input"
        )
        service.record_request(failed_request)
        
        # Record cache metrics
        service.record_cache_hit()
        service.record_cache_hit()
        service.record_cache_miss()
        
        metrics = service.get_current_metrics()
        
        assert metrics["requests"]["total"] == 6
        assert metrics["requests"]["successful"] == 5
        assert metrics["requests"]["failed"] == 1
        assert metrics["requests"]["error_rate_percent"] == round(1/6 * 100, 2)
        
        assert metrics["api_usage"]["gemini_calls"] == 6
        assert metrics["api_usage"]["total_cost_usd"] == round(5 * 0.0025, 6)
        
        assert metrics["image_processing"]["images_processed"] == 5
        assert abs(metrics["image_processing"]["total_size_mb"] - 5.0) < 0.2  # Allow for floating point precision
        
        assert metrics["cache"]["hits"] == 2
        assert metrics["cache"]["misses"] == 1
        assert metrics["cache"]["hit_rate_percent"] == round(2/3 * 100, 2)
        
        assert metrics["errors"]["invalid_input"] == 1

    @patch('src.scanner.services.metrics_service.config')
    def test_get_current_metrics_response_time_percentiles(self, mock_config, service):
        """Test response time percentiles calculation."""
        mock_config.enable_metrics = True
        
        # Record requests with various response times
        response_times = [50, 100, 150, 200, 250, 300, 350, 400, 450, 500]
        
        for time_ms in response_times:
            request_metrics = RequestMetrics(
                timestamp=datetime.now(),
                endpoint="/api/v1/scan",
                method="POST",
                status_code=200,
                processing_time_ms=time_ms
            )
            service.record_request(request_metrics)
        
        metrics = service.get_current_metrics()
        
        response_times_metrics = metrics["response_times_ms"]
        assert response_times_metrics["minimum"] == 50.0
        assert response_times_metrics["maximum"] == 500.0
        assert response_times_metrics["average"] == 275.0
        assert "p50" in response_times_metrics
        assert "p90" in response_times_metrics
        assert "p95" in response_times_metrics
        assert "p99" in response_times_metrics

    @patch('src.scanner.services.metrics_service.config')
    def test_get_current_metrics_infinite_minimum(self, mock_config, service):
        """Test handling of infinite minimum response time."""
        mock_config.enable_metrics = True
        
        metrics = service.get_current_metrics()
        
        # When no requests recorded, minimum should be None
        assert metrics["response_times_ms"]["minimum"] is None

    @patch('src.scanner.services.metrics_service.config')
    def test_get_current_metrics_division_by_zero_protection(self, mock_config, service):
        """Test division by zero protection in metrics calculation."""
        mock_config.enable_metrics = True
        
        metrics = service.get_current_metrics()
        
        # Should not crash with division by zero
        assert metrics["requests"]["error_rate_percent"] == 0
        assert metrics["cache"]["hit_rate_percent"] == 0
        assert metrics["api_usage"]["avg_cost_per_request"] == 0
        assert metrics["image_processing"]["avg_size_mb"] == 0

    @patch('src.scanner.services.metrics_service.config')
    def test_get_current_metrics_with_zero_duration(self, mock_config, service):
        """Test getting metrics with very short duration."""
        mock_config.enable_metrics = True
        
        # Force start time to be very recent
        service.metrics.start_time = datetime.now()
        
        metrics = service.get_current_metrics()
        
        # Should not crash with division by zero
        assert "uptime_seconds" in metrics
        assert metrics["uptime_seconds"] >= 0


class TestGetHourlyMetrics:
    """Test the get_hourly_metrics method."""

    @pytest.fixture
    def service(self):
        """Create a fresh MetricsService instance."""
        return MetricsService()

    def test_get_hourly_metrics_method(self, service):
        """Test get_hourly_metrics method."""
        with patch('src.scanner.services.metrics_service.config.enable_metrics', True):
            hourly_metrics = service.get_hourly_metrics()
        
        assert isinstance(hourly_metrics, dict)
        assert 'hours' in hourly_metrics
        assert 'total_hours' in hourly_metrics
        assert isinstance(hourly_metrics['hours'], list)

    @patch('src.scanner.services.metrics_service.config')
    def test_get_hourly_metrics_disabled(self, mock_config, service):
        """Test getting hourly metrics when disabled."""
        mock_config.enable_metrics = False
        
        metrics = service.get_hourly_metrics()
        
        assert metrics == {"metrics_disabled": True}

    @patch('src.scanner.services.metrics_service.config')
    def test_get_hourly_metrics_empty(self, mock_config, service):
        """Test getting hourly metrics with no data."""
        mock_config.enable_metrics = True
        
        metrics = service.get_hourly_metrics()
        
        assert metrics["hours"] == []
        assert metrics["total_hours"] == 0

    @patch('src.scanner.services.metrics_service.config')
    def test_get_hourly_metrics_with_data(self, mock_config, service):
        """Test getting hourly metrics with recorded data."""
        mock_config.enable_metrics = True
        
        # Record requests in different hours
        base_time = datetime.now().replace(minute=0, second=0, microsecond=0)
        
        for hour_offset in [0, 1, 2]:
            hour_time = base_time + timedelta(hours=hour_offset)
            
            # Record successful request
            request_metrics = RequestMetrics(
                timestamp=hour_time,
                endpoint="/api/v1/scan",
                method="POST",
                status_code=200,
                processing_time_ms=100.0
            )
            service.record_request(request_metrics)
            
            # Record failed request
            failed_request = RequestMetrics(
                timestamp=hour_time,
                endpoint="/api/v1/scan",
                method="POST",
                status_code=400,
                processing_time_ms=50.0
            )
            service.record_request(failed_request)
        
        metrics = service.get_hourly_metrics()
        
        assert len(metrics["hours"]) == 3
        assert metrics["total_hours"] == 3
        
        # Check first hour data
        first_hour = metrics["hours"][0]
        assert first_hour["total_requests"] == 2
        assert first_hour["successful_requests"] == 1
        assert first_hour["failed_requests"] == 1
        assert first_hour["error_rate_percent"] == 50.0


class TestGetRecentRequests:
    """Test the get_recent_requests method."""

    @pytest.fixture
    def service(self):
        """Create a fresh MetricsService instance."""
        return MetricsService()

    def test_get_recent_requests_method(self, service):
        """Test get_recent_requests method."""
        from datetime import datetime
        from src.scanner.services.metrics_service import RequestMetrics
        
        # Add a recent request
        request_metrics = RequestMetrics(
            timestamp=datetime.now(),
            endpoint="/api/scan",
            method="POST",
            status_code=200,
            processing_time_ms=50.0
        )
        
        with patch('src.scanner.services.metrics_service.config.enable_metrics', True):
            service.record_request(request_metrics)
            
            # Get recent requests
            recent = service.get_recent_requests(limit=5)
            
            assert isinstance(recent, dict)
            assert 'requests' in recent
            assert 'total_recent' in recent
            assert isinstance(recent['requests'], list)

    @patch('src.scanner.services.metrics_service.config')
    def test_get_recent_requests_disabled(self, mock_config, service):
        """Test getting recent requests when disabled."""
        mock_config.enable_metrics = False
        
        requests = service.get_recent_requests()
        
        assert requests == {"metrics_disabled": True}

    @patch('src.scanner.services.metrics_service.config')
    def test_get_recent_requests_empty(self, mock_config, service):
        """Test getting recent requests with no data."""
        mock_config.enable_metrics = True
        
        requests = service.get_recent_requests()
        
        assert requests["requests"] == []
        assert requests["total_recent"] == 0

    @patch('src.scanner.services.metrics_service.config')
    def test_get_recent_requests_with_data(self, mock_config, service):
        """Test getting recent requests with recorded data."""
        mock_config.enable_metrics = True
        
        # Record several requests
        for i in range(5):
            request_metrics = RequestMetrics(
                timestamp=datetime.now(),
                endpoint="/api/v1/scan",
                method="POST",
                status_code=200,
                processing_time_ms=100.0 + i * 10,
                image_size_bytes=1024000,
                gemini_cost=0.0025,
                tcg_matches=3
            )
            service.record_request(request_metrics)
        
        requests = service.get_recent_requests(limit=3)
        
        assert len(requests["requests"]) == 3
        assert requests["total_recent"] == 5
        
        # Check request structure
        first_request = requests["requests"][0]
        assert "timestamp" in first_request
        assert first_request["endpoint"] == "/api/v1/scan"
        assert first_request["method"] == "POST"
        assert first_request["status_code"] == 200
        assert "processing_time_ms" in first_request
        assert "image_size_kb" in first_request
        assert first_request["cost_usd"] == 0.0025
        assert first_request["tcg_matches"] == 3
        assert first_request["error_type"] is None

    @patch('src.scanner.services.metrics_service.config')
    def test_get_recent_requests_no_limit(self, mock_config, service):
        """Test getting recent requests with no limit."""
        mock_config.enable_metrics = True
        
        # Record several requests
        for i in range(5):
            request_metrics = RequestMetrics(
                timestamp=datetime.now(),
                endpoint="/api/v1/scan",
                method="POST",
                status_code=200,
                processing_time_ms=100.0
            )
            service.record_request(request_metrics)
        
        requests = service.get_recent_requests(limit=0)
        
        assert len(requests["requests"]) == 5
        assert requests["total_recent"] == 5


class TestResetMetrics:
    """Test the reset_metrics method."""

    @pytest.fixture
    def service(self):
        """Create a fresh MetricsService instance."""
        return MetricsService()

    def test_reset_metrics_method(self, service):
        """Test reset_metrics method."""
        from datetime import datetime
        from src.scanner.services.metrics_service import RequestMetrics
        
        # Add some metrics first
        request_metrics = RequestMetrics(
            timestamp=datetime.now(),
            endpoint="/api/scan",
            method="POST",
            status_code=200,
            processing_time_ms=100.0
        )
        
        with patch('src.scanner.services.metrics_service.config.enable_metrics', True):
            service.record_request(request_metrics)
            
            # Reset metrics
            service.reset_metrics()
            
            # Should be reset
            assert service.metrics.total_requests == 0
            assert len(service.recent_requests) == 0

    @patch('src.scanner.services.metrics_service.config')
    def test_reset_metrics(self, mock_config, service):
        """Test resetting metrics."""
        mock_config.enable_metrics = True
        
        # Record some data
        request_metrics = RequestMetrics(
            timestamp=datetime.now(),
            endpoint="/api/v1/scan",
            method="POST",
            status_code=200,
            processing_time_ms=100.0
        )
        service.record_request(request_metrics)
        service.record_cache_hit()
        
        # Verify data exists
        assert service.metrics.total_requests == 1
        assert len(service.recent_requests) == 1
        assert len(service.response_times) == 1
        assert len(service._hourly_metrics) == 1
        
        # Reset metrics
        service.reset_metrics()
        
        # Verify everything is reset
        assert service.metrics.total_requests == 0
        assert len(service.recent_requests) == 0
        assert len(service.response_times) == 0
        assert len(service._hourly_metrics) == 0
        assert service.metrics.cache_hits == 0


class TestCalculatePercentiles:
    """Test the _calculate_percentiles method."""

    @pytest.fixture
    def service(self):
        """Create a fresh MetricsService instance."""
        return MetricsService()

    def test_calculate_percentiles_empty(self, service):
        """Test percentiles calculation with empty data."""
        percentiles = service._calculate_percentiles()
        
        assert percentiles == {}

    def test_calculate_percentiles_single_value(self, service):
        """Test percentiles calculation with single value."""
        service.response_times = [100.0]
        
        percentiles = service._calculate_percentiles()
        
        assert percentiles["p50"] == 100.0
        assert percentiles["p90"] == 100.0
        assert percentiles["p95"] == 100.0
        assert percentiles["p99"] == 100.0

    def test_calculate_percentiles_multiple_values(self, service):
        """Test percentiles calculation with multiple values."""
        service.response_times = list(range(1, 101))  # 1 to 100
        
        percentiles = service._calculate_percentiles()
        
        # Percentiles are calculated based on index positions
        assert percentiles["p50"] == 51.0  # 50% of 100 items = index 50
        assert percentiles["p90"] == 91.0  # 90% of 100 items = index 90
        assert percentiles["p95"] == 96.0  # 95% of 100 items = index 95
        assert percentiles["p99"] == 100.0  # 99% of 100 items = index 99

    def test_calculate_percentiles_edge_case(self, service):
        """Test percentiles calculation with edge case values."""
        service.response_times = [10.0, 20.0]
        
        percentiles = service._calculate_percentiles()
        
        # With only 2 values, percentiles should be distributed
        # For 2 values, 50% index = 1, so we get the second value
        assert percentiles["p50"] == 20.0
        assert percentiles["p90"] == 20.0
        assert percentiles["p95"] == 20.0
        assert percentiles["p99"] == 20.0


class TestUpdateResponseTimes:
    """Test the _update_response_times method."""

    @pytest.fixture
    def service(self):
        """Create a fresh MetricsService instance."""
        return MetricsService()

    def test_update_response_times_first_value(self, service):
        """Test updating response times with first value."""
        service._update_response_times(100.0)
        
        assert service.metrics.min_response_time_ms == 100.0
        assert service.metrics.max_response_time_ms == 100.0
        assert service.metrics.avg_response_time_ms == 100.0
        assert len(service.response_times) == 1

    def test_update_response_times_multiple_values(self, service):
        """Test updating response times with multiple values."""
        service._update_response_times(100.0)
        service._update_response_times(200.0)
        service._update_response_times(50.0)
        
        assert service.metrics.min_response_time_ms == 50.0
        assert service.metrics.max_response_time_ms == 200.0
        assert abs(service.metrics.avg_response_time_ms - 116.67) < 0.01  # Allow for floating point precision

    def test_update_response_times_limit(self, service):
        """Test that response times are limited to 1000 entries."""
        # Add 1005 response times
        for i in range(1005):
            service._update_response_times(float(i))
        
        # Should only keep last 1000
        assert len(service.response_times) == 1000
        assert service.response_times[0] == 5.0  # First 5 should be removed


class TestResponseTimeTracking:
    """Test response time tracking functionality."""

    @pytest.fixture
    def service(self):
        """Create a fresh MetricsService instance."""
        return MetricsService()

    def test_response_time_tracking(self, service):
        """Test response time tracking."""
        from datetime import datetime
        from src.scanner.services.metrics_service import RequestMetrics
        
        # Record multiple requests with different response times
        times = [50.0, 100.0, 150.0, 200.0]
        
        with patch('src.scanner.services.metrics_service.config.enable_metrics', True):
            for time_ms in times:
                request_metrics = RequestMetrics(
                    timestamp=datetime.now(),
                    endpoint="/api/scan",
                    method="POST",
                    status_code=200,
                    processing_time_ms=time_ms
                )
                service.record_request(request_metrics)
            
            # Check response time stats
            current = service.get_current_metrics()
            assert 'response_times_ms' in current
            assert current['response_times_ms']['average'] > 0
            assert current['response_times_ms']['minimum'] == 50.0
            assert current['response_times_ms']['maximum'] == 200.0


class TestMetricsServiceOptionalMethods:
    """Test optional methods that may exist in MetricsService."""

    @pytest.fixture
    def service(self):
        """Create a fresh MetricsService instance."""
        return MetricsService()

    def test_record_gauge_method(self, service):
        """Test record_gauge method if it exists."""
        if hasattr(service, 'record_gauge'):
            service.record_gauge('test_gauge', 42.5)
            assert 'test_gauge' in service._metrics
            assert service._metrics['test_gauge'] == 42.5

    def test_record_histogram_method(self, service):
        """Test record_histogram method if it exists."""
        if hasattr(service, 'record_histogram'):
            service.record_histogram('test_histogram', 100)
            # Should store histogram data somehow
            assert isinstance(service._metrics, dict)

    def test_track_request_method(self, service):
        """Test track_request method if it exists."""
        if hasattr(service, 'track_request'):
            result = service.track_request(
                endpoint='/api/scan',
                method='POST',
                status_code=200,
                duration=0.5
            )
            # Should track request metrics
            metrics = service.get_metrics()
            assert len(metrics) > 0

    def test_track_error_method(self, service):
        """Test track_error method if it exists."""
        if hasattr(service, 'track_error'):
            service.track_error(
                error_type='ValidationError',
                endpoint='/api/scan'
            )
            metrics = service.get_metrics()
            # Should have error metrics
            assert len(metrics) > 0

    def test_get_uptime_method(self, service):
        """Test get_uptime method if it exists."""
        if hasattr(service, 'get_uptime'):
            uptime = service.get_uptime()
            assert isinstance(uptime, (int, float))
            assert uptime >= 0

    def test_metrics_with_labels(self, service):
        """Test metrics with labels if supported."""
        if hasattr(service, 'increment_counter_with_labels'):
            service.increment_counter_with_labels(
                'labeled_counter',
                value=1,
                labels={'endpoint': '/api/scan', 'method': 'POST'}
            )
            metrics = service.get_metrics()
            assert len(metrics) > 0

    def test_health_check_metrics(self, service):
        """Test health check related metrics if they exist."""
        if hasattr(service, 'record_health_check'):
            service.record_health_check(healthy=True)
            metrics = service.get_metrics()
            # Should have some health-related metrics
            assert isinstance(metrics, dict)

    def test_performance_metrics(self, service):
        """Test performance tracking methods if they exist."""
        if hasattr(service, 'start_timer'):
            timer = service.start_timer('operation')
            # Simulate some work
            import time
            time.sleep(0.01)
            if hasattr(timer, 'stop'):
                timer.stop()
            
            metrics = service.get_metrics()
            assert isinstance(metrics, dict)

    def test_batch_increment(self, service):
        """Test batch increment functionality if available."""
        if hasattr(service, 'batch_increment'):
            service.batch_increment({
                'metric1': 10,
                'metric2': 20,
                'metric3': 30
            })
            
            metrics = service.get_metrics()
            assert metrics.get('metric1') == 10
            assert metrics.get('metric2') == 20
            assert metrics.get('metric3') == 30

    def test_metrics_service_string_representation(self, service):
        """Test metrics service string representation."""
        str_repr = str(service)
        assert isinstance(str_repr, str)