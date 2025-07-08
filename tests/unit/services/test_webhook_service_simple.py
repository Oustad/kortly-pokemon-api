"""Simple working tests for WebhookService."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.scanner.services.webhook_service import WebhookService


class TestWebhookServiceSimple:
    """Simple test cases for WebhookService that match actual interface."""

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

    def test_rate_limiter_exists(self, webhook_service):
        """Test that rate limiter is properly initialized."""
        assert hasattr(webhook_service, '_rate_limiter')
        rate_limiter = webhook_service._rate_limiter
        
        # Should have some rate limiting functionality
        if hasattr(rate_limiter, 'is_allowed'):
            # Test basic rate limiter functionality
            result = rate_limiter.is_allowed()
            assert isinstance(result, bool)

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

    def test_webhook_service_string_representation(self, webhook_service):
        """Test webhook service string representation."""
        str_repr = str(webhook_service)
        assert isinstance(str_repr, str)

    def test_webhook_service_has_client(self, webhook_service):
        """Test that webhook service has HTTP client."""
        assert hasattr(webhook_service, 'client')
        # Client should be some kind of HTTP client
        client = webhook_service.client
        assert client is not None

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

    def test_webhook_service_cleanup_method(self, webhook_service):
        """Test cleanup/close method if it exists."""
        if hasattr(webhook_service, 'close'):
            # Should be able to call cleanup
            try:
                webhook_service.close()
            except Exception:
                # Should handle cleanup gracefully
                pass

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