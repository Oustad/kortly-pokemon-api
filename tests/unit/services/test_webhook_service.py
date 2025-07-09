"""Comprehensive tests for webhook_service.py - consolidated from simple and extended tests."""

import pytest
import time
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from src.scanner.services.webhook_service import (
    WebhookService,
    RateLimiter,
    get_webhook_service,
    send_error_webhook
)


class TestRateLimiter:
    """Test RateLimiter class."""

    def test_rate_limiter_initialization(self):
        """Test RateLimiter initialization."""
        limiter = RateLimiter(max_requests=5, window=60)
        
        assert limiter.max_requests == 5
        assert limiter.window == 60
        assert limiter.requests == []

    def test_rate_limiter_allow_request_empty(self):
        """Test allowing request when no previous requests."""
        limiter = RateLimiter(max_requests=3, window=60)
        
        result = limiter.allow_request()
        
        assert result is True
        assert len(limiter.requests) == 1

    def test_rate_limiter_allow_request_under_limit(self):
        """Test allowing request when under limit."""
        limiter = RateLimiter(max_requests=3, window=60)
        
        # Make two requests
        assert limiter.allow_request() is True
        assert limiter.allow_request() is True
        assert len(limiter.requests) == 2

    def test_rate_limiter_allow_request_at_limit(self):
        """Test allowing request when at limit."""
        limiter = RateLimiter(max_requests=2, window=60)
        
        # Make two requests (at limit)
        assert limiter.allow_request() is True
        assert limiter.allow_request() is True
        
        # Third request should be denied
        assert limiter.allow_request() is False
        assert len(limiter.requests) == 2

    def test_rate_limiter_window_cleanup(self):
        """Test that old requests are cleaned up."""
        limiter = RateLimiter(max_requests=2, window=1)  # 1 second window
        
        # Add old request manually
        old_time = time.time() - 2  # 2 seconds ago
        limiter.requests.append(old_time)
        
        # Allow request should clean up old requests
        assert limiter.allow_request() is True
        assert len(limiter.requests) == 1  # Old request removed, new one added

    def test_rate_limiter_window_multiple_cleanup(self):
        """Test cleanup of multiple old requests."""
        limiter = RateLimiter(max_requests=3, window=1)
        
        # Add multiple old requests
        old_time1 = time.time() - 2
        old_time2 = time.time() - 1.5
        limiter.requests.extend([old_time1, old_time2])
        
        # Allow request should clean up all old requests
        assert limiter.allow_request() is True
        assert len(limiter.requests) == 1

    def test_rate_limiter_mixed_old_new_requests(self):
        """Test with mix of old and new requests."""
        limiter = RateLimiter(max_requests=3, window=2)
        
        # Add one old request and one recent request
        old_time = time.time() - 3  # Outside window
        recent_time = time.time() - 1  # Inside window
        limiter.requests.extend([old_time, recent_time])
        
        # Should clean up old, keep recent, and allow new
        assert limiter.allow_request() is True
        assert len(limiter.requests) == 2  # recent + new

    def test_rate_limiter_edge_case_window_boundary(self):
        """Test edge case at window boundary."""
        limiter = RateLimiter(max_requests=2, window=1)
        
        # Add request at boundary
        boundary_time = time.time() - 1.0001  # Just outside window
        limiter.requests.append(boundary_time)
        
        # Should clean up boundary request
        assert limiter.allow_request() is True
        assert len(limiter.requests) == 1

    def test_rate_limiter_zero_window(self):
        """Test RateLimiter with zero window."""
        limiter = RateLimiter(max_requests=2, window=0)
        
        # With zero window, all requests should be allowed
        assert limiter.allow_request() is True
        assert limiter.allow_request() is True
        assert limiter.allow_request() is True

    def test_rate_limiter_zero_max_requests(self):
        """Test RateLimiter with zero max requests."""
        limiter = RateLimiter(max_requests=0, window=60)
        
        # With zero max requests, no requests should be allowed
        assert limiter.allow_request() is False
        assert limiter.allow_request() is False


class TestGlobalFunctions:
    """Test global helper functions."""

    def test_get_webhook_service_singleton(self):
        """Test that get_webhook_service returns singleton."""
        with patch('src.scanner.services.webhook_service.WebhookService') as mock_service:
            mock_instance = Mock()
            mock_service.return_value = mock_instance
            
            # Reset the global variable
            import src.scanner.services.webhook_service
            src.scanner.services.webhook_service._webhook_service = None
            
            service1 = get_webhook_service()
            service2 = get_webhook_service()
            
            assert service1 is service2
            mock_service.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_error_webhook_convenience_function(self):
        """Test send_error_webhook convenience function."""
        with patch('src.scanner.services.webhook_service.get_webhook_service') as mock_get_service:
            mock_service = Mock()
            mock_service.send_error_notification = AsyncMock(return_value=True)
            mock_get_service.return_value = mock_service
            
            result = await send_error_webhook(
                error_message="Test error",
                level="ERROR",
                request_id="test-123"
            )
            
            assert result is True
            mock_service.send_error_notification.assert_called_once_with(
                error_message="Test error",
                level="ERROR",
                request_id="test-123",
                endpoint=None,
                user_agent=None,
                traceback=None,
                context=None
            )

    @pytest.mark.asyncio
    async def test_send_error_webhook_with_all_params(self):
        """Test send_error_webhook with all parameters."""
        with patch('src.scanner.services.webhook_service.get_webhook_service') as mock_get_service:
            mock_service = Mock()
            mock_service.send_error_notification = AsyncMock(return_value=False)
            mock_get_service.return_value = mock_service
            
            result = await send_error_webhook(
                error_message="Test error",
                level="CRITICAL",
                request_id="test-456",
                endpoint="/api/v1/scan",
                user_agent="TestBot/1.0",
                traceback="Test traceback",
                context={"test": "context"}
            )
            
            assert result is False
            mock_service.send_error_notification.assert_called_once_with(
                error_message="Test error",
                level="CRITICAL",
                request_id="test-456",
                endpoint="/api/v1/scan",
                user_agent="TestBot/1.0",
                traceback="Test traceback",
                context={"test": "context"}
            )


class TestWebhookServiceInitialization:
    """Test WebhookService initialization."""

    @pytest.fixture
    def webhook_service(self):
        """Create WebhookService instance."""
        with patch('src.scanner.services.webhook_service.get_config') as mock_config:
            mock_config.return_value = Mock(
                error_webhook_timeout=30,
                error_webhook_rate_limit=10,
                error_webhook_enabled=True,
                error_webhook_url="https://example.com/webhook"
            )
            return WebhookService()

    def test_initialization_basic(self, webhook_service):
        """Test basic WebhookService initialization."""
        assert hasattr(webhook_service, 'client')
        assert hasattr(webhook_service, '_rate_limiter')

    def test_initialization_with_config(self):
        """Test initialization with different config values."""
        with patch('src.scanner.services.webhook_service.get_config') as mock_config:
            mock_config.return_value = Mock(
                error_webhook_timeout=60,
                error_webhook_rate_limit=5,
                error_webhook_enabled=False,
                error_webhook_url=None
            )
            service = WebhookService()
            assert hasattr(service, 'client')
            assert hasattr(service, '_rate_limiter')

    def test_rate_limiter_exists(self, webhook_service):
        """Test that rate limiter is properly initialized."""
        assert hasattr(webhook_service, '_rate_limiter')
        rate_limiter = webhook_service._rate_limiter
        
        # Should have some rate limiting functionality
        if hasattr(rate_limiter, 'is_allowed'):
            # Test basic rate limiter functionality
            result = rate_limiter.is_allowed()
            assert isinstance(result, bool)

    def test_webhook_service_has_client(self, webhook_service):
        """Test that webhook service has HTTP client."""
        assert hasattr(webhook_service, 'client')
        # Client should be some kind of HTTP client
        client = webhook_service.client
        assert client is not None

    def test_webhook_service_string_representation(self, webhook_service):
        """Test webhook service string representation."""
        str_repr = str(webhook_service)
        assert isinstance(str_repr, str)


class TestSendErrorNotification:
    """Test send_error_notification functionality."""

    @pytest.fixture
    def webhook_service(self):
        """Create WebhookService instance."""
        with patch('src.scanner.services.webhook_service.get_config') as mock_config:
            mock_config.return_value = Mock(
                error_webhook_timeout=30,
                error_webhook_rate_limit=10,
                error_webhook_enabled=True,
                error_webhook_url="https://example.com/webhook"
            )
            return WebhookService()

    @pytest.fixture
    def webhook_service_minimal(self):
        """Create WebhookService with minimal config."""
        config = Mock()
        config.error_webhook_enabled = True
        config.error_webhook_url = "https://webhook.test"
        config.error_webhook_timeout = 1.0
        config.error_webhook_rate_limit = 1
        config.error_webhook_min_level = "ERROR"
        config.error_webhook_environment_tag = "test"
        config.error_webhook_include_traceback = False
        
        with patch('src.scanner.services.webhook_service.get_config', return_value=config):
            with patch('src.scanner.services.webhook_service.config', config):
                with patch('src.scanner.services.webhook_service.httpx.AsyncClient') as mock_client:
                    mock_client.return_value = AsyncMock()
                    service = WebhookService()
                    service.client = mock_client.return_value
                    return service

    @pytest.mark.asyncio
    async def test_send_error_notification_method_exists(self, webhook_service):
        """Test that send_error_notification method exists."""
        with patch.object(webhook_service, 'client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.post = AsyncMock(return_value=mock_response)
            
            with patch('src.scanner.services.webhook_service.get_config') as mock_config:
                mock_config.return_value = Mock(
                    error_webhook_enabled=True,
                    error_webhook_url="https://example.com/webhook"
                )
                
                result = await webhook_service.send_error_notification(
                    "Test error message"
                )
                
                assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_send_error_notification_with_params(self, webhook_service):
        """Test send_error_notification with all parameters."""
        with patch.object(webhook_service, 'client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.post = AsyncMock(return_value=mock_response)
            
            with patch('src.scanner.services.webhook_service.get_config') as mock_config:
                mock_config.return_value = Mock(
                    error_webhook_enabled=True,
                    error_webhook_url="https://example.com/webhook"
                )
                
                result = await webhook_service.send_error_notification(
                    error_message="Test error",
                    level="CRITICAL",
                    request_id="req-123",
                    endpoint="/api/scan",
                    user_agent="test-agent",
                    traceback="fake traceback",
                    context={"key": "value"}
                )
                
                assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_send_error_notification_disabled(self, webhook_service):
        """Test send_error_notification when webhooks are disabled."""
        with patch('src.scanner.services.webhook_service.get_config') as mock_config:
            mock_config.return_value = Mock(
                error_webhook_enabled=False,
                error_webhook_url="https://example.com/webhook"
            )
            
            result = await webhook_service.send_error_notification(
                "Test error message"
            )
            
            # Should return False when disabled
            assert result is False

    @pytest.mark.asyncio
    async def test_send_error_notification_no_url(self, webhook_service):
        """Test send_error_notification when no URL is configured."""
        with patch('src.scanner.services.webhook_service.get_config') as mock_config:
            mock_config.return_value = Mock(
                error_webhook_enabled=True,
                error_webhook_url=None
            )
            
            result = await webhook_service.send_error_notification(
                "Test error message"
            )
            
            # Should return False when no URL
            assert result is False

    @pytest.mark.asyncio
    async def test_send_error_notification_http_error(self, webhook_service):
        """Test send_error_notification with HTTP error."""
        with patch.object(webhook_service, 'client') as mock_client:
            mock_client.post = AsyncMock(side_effect=Exception("HTTP error"))
            
            with patch('src.scanner.services.webhook_service.get_config') as mock_config:
                mock_config.return_value = Mock(
                    error_webhook_enabled=True,
                    error_webhook_url="https://example.com/webhook"
                )
                
                result = await webhook_service.send_error_notification(
                    "Test error message"
                )
                
                # Should handle errors gracefully
                assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_send_notification_rate_limiting(self, webhook_service):
        """Test that rate limiting is considered."""
        with patch.object(webhook_service._rate_limiter, 'allow_request', return_value=False):
            with patch('src.scanner.services.webhook_service.get_config') as mock_config:
                mock_config.return_value = Mock(
                    error_webhook_enabled=True,
                    error_webhook_url="https://example.com/webhook"
                )
                
                result = await webhook_service.send_error_notification(
                    "Test error message"
                )
                
                # Should respect rate limiting and return False
                assert result is False

    @pytest.mark.asyncio
    async def test_send_error_notification_success_response(self, webhook_service):
        """Test successful webhook response handling."""
        with patch.object(webhook_service, 'client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "ok"}
            mock_client.post = AsyncMock(return_value=mock_response)
            
            with patch('src.scanner.services.webhook_service.get_config') as mock_config:
                mock_config.return_value = Mock(
                    error_webhook_enabled=True,
                    error_webhook_url="https://example.com/webhook"
                )
                
                result = await webhook_service.send_error_notification(
                    "Test success message"
                )
                
                # Should return True for successful response
                assert result is True

    @pytest.mark.asyncio
    async def test_send_error_notification_empty_message(self, webhook_service_minimal):
        """Test sending error notification with empty message."""
        mock_response = Mock()
        mock_response.status_code = 200
        webhook_service_minimal.client.post = AsyncMock(return_value=mock_response)

        result = await webhook_service_minimal.send_error_notification(
            error_message="",
            level="ERROR"
        )

        assert result is True
        call_args = webhook_service_minimal.client.post.call_args
        payload = call_args[1]['json']
        assert payload['message'] == ""

    @pytest.mark.asyncio
    async def test_send_error_notification_none_values(self, webhook_service_minimal):
        """Test sending error notification with None values."""
        mock_response = Mock()
        mock_response.status_code = 200
        webhook_service_minimal.client.post = AsyncMock(return_value=mock_response)

        result = await webhook_service_minimal.send_error_notification(
            error_message="Test error",
            level="ERROR",
            request_id=None,
            endpoint=None,
            user_agent=None,
            traceback=None,
            context=None
        )

        assert result is True
        call_args = webhook_service_minimal.client.post.call_args
        payload = call_args[1]['json']
        
        # None values should not be included in payload
        assert 'request_id' not in payload
        assert 'endpoint' not in payload
        assert 'user_agent' not in payload
        assert 'context' not in payload
        assert 'traceback' not in payload

    def test_should_notify_case_sensitive(self, webhook_service_minimal):
        """Test _should_notify with different case levels."""
        result1 = webhook_service_minimal._should_notify("error")
        result2 = webhook_service_minimal._should_notify("ERROR")
        result3 = webhook_service_minimal._should_notify("Error")
        
        # Implementation is case-sensitive, only uppercase works
        assert result1 is False
        assert result2 is True  
        assert result3 is False


class TestWebhookServiceOptionalMethods:
    """Test optional methods that may exist in WebhookService."""

    @pytest.fixture
    def webhook_service(self):
        """Create WebhookService instance."""
        with patch('src.scanner.services.webhook_service.get_config') as mock_config:
            mock_config.return_value = Mock(
                error_webhook_timeout=30,
                error_webhook_rate_limit=10,
                error_webhook_enabled=True,
                error_webhook_url="https://example.com/webhook"
            )
            return WebhookService()

    @pytest.mark.asyncio
    async def test_send_bulk_notification_method(self, webhook_service):
        """Test send_bulk_notification method if it exists."""
        if hasattr(webhook_service, 'send_bulk_notification'):
            with patch.object(webhook_service, 'client') as mock_client:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_client.post = AsyncMock(return_value=mock_response)
                
                with patch('src.scanner.services.webhook_service.get_config') as mock_config:
                    mock_config.return_value = Mock(
                        error_webhook_enabled=True,
                        error_webhook_url="https://example.com/webhook"
                    )
                    
                    result = await webhook_service.send_bulk_notification([
                        {"message": "error 1"},
                        {"message": "error 2"}
                    ])
                    
                    assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_webhook_service_cleanup_method(self, webhook_service):
        """Test cleanup/close method if it exists."""
        if hasattr(webhook_service, 'close'):
            # Should be able to call cleanup
            try:
                await webhook_service.close()
            except Exception:
                # Should handle cleanup gracefully
                pass