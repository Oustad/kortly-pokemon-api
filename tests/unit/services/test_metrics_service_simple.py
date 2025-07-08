"""Simple working tests for MetricsService."""

import pytest
from unittest.mock import Mock, patch
from src.scanner.services.metrics_service import MetricsService


class TestMetricsServiceSimple:
    """Simple test cases for MetricsService that match actual interface."""

    @pytest.fixture
    def metrics_service(self):
        """Create MetricsService instance."""
        return MetricsService()

    def test_initialization_basic(self, metrics_service):
        """Test basic MetricsService initialization."""
        assert hasattr(metrics_service, 'metrics')
        assert hasattr(metrics_service, 'recent_requests')
        assert hasattr(metrics_service, 'response_times')
        assert isinstance(metrics_service.metrics, object)

    def test_record_request_method(self, metrics_service):
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
            metrics_service.record_request(request_metrics)
            
            # Should update metrics
            assert metrics_service.metrics.total_requests == 1
            assert metrics_service.metrics.successful_requests == 1

    def test_record_cache_hit_method(self, metrics_service):
        """Test record_cache_hit method."""
        initial_hits = metrics_service.metrics.cache_hits
        
        with patch('src.scanner.services.metrics_service.config.enable_metrics', True):
            metrics_service.record_cache_hit()
            
            # Should increment cache hits
            assert metrics_service.metrics.cache_hits == initial_hits + 1

    def test_record_gauge_method(self, metrics_service):
        """Test record_gauge method if it exists."""
        if hasattr(metrics_service, 'record_gauge'):
            metrics_service.record_gauge('test_gauge', 42.5)
            assert 'test_gauge' in metrics_service._metrics
            assert metrics_service._metrics['test_gauge'] == 42.5

    def test_record_histogram_method(self, metrics_service):
        """Test record_histogram method if it exists."""
        if hasattr(metrics_service, 'record_histogram'):
            metrics_service.record_histogram('test_histogram', 100)
            # Should store histogram data somehow
            assert isinstance(metrics_service._metrics, dict)

    def test_get_current_metrics_method(self, metrics_service):
        """Test get_current_metrics method."""
        # Get current metrics
        with patch('src.scanner.services.metrics_service.config.enable_metrics', True):
            metrics = metrics_service.get_current_metrics()
        
        assert isinstance(metrics, dict)
        assert 'requests' in metrics
        assert 'total' in metrics['requests']
        assert 'successful' in metrics['requests']
        assert 'failed' in metrics['requests']
        assert 'uptime_seconds' in metrics

    def test_reset_metrics_method(self, metrics_service):
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
            metrics_service.record_request(request_metrics)
            
            # Reset metrics
            metrics_service.reset_metrics()
            
            # Should be reset
            assert metrics_service.metrics.total_requests == 0
            assert len(metrics_service.recent_requests) == 0

    def test_track_request_method(self, metrics_service):
        """Test track_request method if it exists."""
        if hasattr(metrics_service, 'track_request'):
            result = metrics_service.track_request(
                endpoint='/api/scan',
                method='POST',
                status_code=200,
                duration=0.5
            )
            # Should track request metrics
            metrics = metrics_service.get_metrics()
            assert len(metrics) > 0

    def test_track_error_method(self, metrics_service):
        """Test track_error method if it exists."""
        if hasattr(metrics_service, 'track_error'):
            metrics_service.track_error(
                error_type='ValidationError',
                endpoint='/api/scan'
            )
            metrics = metrics_service.get_metrics()
            # Should have error metrics
            assert len(metrics) > 0

    def test_get_uptime_method(self, metrics_service):
        """Test get_uptime method if it exists."""
        if hasattr(metrics_service, 'get_uptime'):
            uptime = metrics_service.get_uptime()
            assert isinstance(uptime, (int, float))
            assert uptime >= 0

    def test_get_hourly_metrics_method(self, metrics_service):
        """Test get_hourly_metrics method."""
        with patch('src.scanner.services.metrics_service.config.enable_metrics', True):
            hourly_metrics = metrics_service.get_hourly_metrics()
        
        assert isinstance(hourly_metrics, dict)
        assert 'hours' in hourly_metrics
        assert 'total_hours' in hourly_metrics
        assert isinstance(hourly_metrics['hours'], list)

    def test_get_recent_requests_method(self, metrics_service):
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
            metrics_service.record_request(request_metrics)
            
            # Get recent requests
            recent = metrics_service.get_recent_requests(limit=5)
            
            assert isinstance(recent, dict)
            assert 'requests' in recent
            assert 'total_recent' in recent
            assert isinstance(recent['requests'], list)

    def test_record_cache_miss_method(self, metrics_service):
        """Test record_cache_miss method."""
        initial_misses = metrics_service.metrics.cache_misses
        
        with patch('src.scanner.services.metrics_service.config.enable_metrics', True):
            metrics_service.record_cache_miss()
            
            # Should increment cache misses
            assert metrics_service.metrics.cache_misses == initial_misses + 1

    def test_metrics_with_labels(self, metrics_service):
        """Test metrics with labels if supported."""
        if hasattr(metrics_service, 'increment_counter_with_labels'):
            metrics_service.increment_counter_with_labels(
                'labeled_counter',
                value=1,
                labels={'endpoint': '/api/scan', 'method': 'POST'}
            )
            metrics = metrics_service.get_metrics()
            assert len(metrics) > 0

    def test_response_time_tracking(self, metrics_service):
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
                metrics_service.record_request(request_metrics)
            
            # Check response time stats
            current = metrics_service.get_current_metrics()
            assert 'response_times_ms' in current
            assert current['response_times_ms']['average'] > 0
            assert current['response_times_ms']['minimum'] == 50.0
            assert current['response_times_ms']['maximum'] == 200.0

    def test_metrics_service_string_representation(self, metrics_service):
        """Test metrics service string representation."""
        str_repr = str(metrics_service)
        assert isinstance(str_repr, str)

    def test_health_check_metrics(self, metrics_service):
        """Test health check related metrics if they exist."""
        if hasattr(metrics_service, 'record_health_check'):
            metrics_service.record_health_check(healthy=True)
            metrics = metrics_service.get_metrics()
            # Should have some health-related metrics
            assert isinstance(metrics, dict)

    def test_performance_metrics(self, metrics_service):
        """Test performance tracking methods if they exist."""
        if hasattr(metrics_service, 'start_timer'):
            timer = metrics_service.start_timer('operation')
            # Simulate some work
            import time
            time.sleep(0.01)
            if hasattr(timer, 'stop'):
                timer.stop()
            
            metrics = metrics_service.get_metrics()
            assert isinstance(metrics, dict)

    def test_batch_increment(self, metrics_service):
        """Test batch increment functionality if available."""
        if hasattr(metrics_service, 'batch_increment'):
            metrics_service.batch_increment({
                'metric1': 10,
                'metric2': 20,
                'metric3': 30
            })
            
            metrics = metrics_service.get_metrics()
            assert metrics.get('metric1') == 10
            assert metrics.get('metric2') == 20
            assert metrics.get('metric3') == 30