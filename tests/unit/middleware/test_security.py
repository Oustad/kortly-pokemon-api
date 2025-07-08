"""Unit tests for security middleware."""

import pytest
import time
from unittest.mock import Mock, patch, AsyncMock
from fastapi import Request, Response, HTTPException
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse

from src.scanner.middleware.security import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    cleanup_rate_limit_data
)


class TestRateLimitMiddleware:
    """Test cases for RateLimitMiddleware."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for rate limiting."""
        with patch('src.scanner.middleware.security.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.rate_limit_enabled = True
            mock_config.rate_limit_per_minute = 5
            mock_config.rate_limit_burst = 2
            mock_get_config.return_value = mock_config
            yield mock_config

    @pytest.fixture
    def rate_limit_middleware(self, mock_config):
        """Create RateLimitMiddleware instance."""
        app = Mock()
        return RateLimitMiddleware(app)

    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "192.168.1.1"
        request.headers = {}
        return request

    def test_middleware_initialization(self, rate_limit_middleware):
        """Test middleware initialization."""
        assert rate_limit_middleware is not None
        assert rate_limit_middleware.requests == {}
        assert rate_limit_middleware.window == 60

    def test_get_client_ip_direct(self, rate_limit_middleware, mock_request):
        """Test getting client IP from direct connection."""
        mock_request.client.host = "203.0.113.1"
        
        ip = rate_limit_middleware._get_client_ip(mock_request)
        
        assert ip == "203.0.113.1"

    def test_get_client_ip_forwarded_for(self, rate_limit_middleware, mock_request):
        """Test getting client IP from X-Forwarded-For header."""
        mock_request.headers = {"X-Forwarded-For": "203.0.113.1, 192.168.1.1, 10.0.0.1"}
        
        ip = rate_limit_middleware._get_client_ip(mock_request)
        
        assert ip == "203.0.113.1"

    def test_get_client_ip_real_ip(self, rate_limit_middleware, mock_request):
        """Test getting client IP from X-Real-IP header."""
        mock_request.headers = {"X-Real-IP": "203.0.113.1"}
        
        ip = rate_limit_middleware._get_client_ip(mock_request)
        
        assert ip == "203.0.113.1"

    def test_get_client_ip_no_client(self, rate_limit_middleware):
        """Test getting client IP when request.client is None."""
        request = Mock(spec=Request)
        request.client = None
        request.headers = {}
        
        ip = rate_limit_middleware._get_client_ip(request)
        
        assert ip == "unknown"

    @pytest.mark.asyncio
    async def test_dispatch_rate_limiting_disabled(self, mock_request):
        """Test dispatch when rate limiting is disabled."""
        with patch('src.scanner.middleware.security.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.rate_limit_enabled = False
            mock_get_config.return_value = mock_config
            
            app = Mock()
            middleware = RateLimitMiddleware(app)
            
            call_next = AsyncMock()
            expected_response = Mock()
            call_next.return_value = expected_response
            
            result = await middleware.dispatch(mock_request, call_next)
            
            assert result == expected_response
            call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_dispatch_under_rate_limit(self, rate_limit_middleware, mock_request, mock_config):
        """Test dispatch when under rate limit."""
        call_next = AsyncMock()
        mock_response = Mock()
        mock_response.headers = {}
        call_next.return_value = mock_response
        
        # Mock time.time to return consistent value
        with patch('time.time', return_value=1000.0):
            result = await rate_limit_middleware.dispatch(mock_request, call_next)
        
        assert result == mock_response
        call_next.assert_called_once_with(mock_request)
        
        # Check rate limit headers were added
        assert "X-RateLimit-Limit" in mock_response.headers
        assert "X-RateLimit-Remaining" in mock_response.headers
        assert "X-RateLimit-Reset" in mock_response.headers
        assert mock_response.headers["X-RateLimit-Limit"] == "5"

    @pytest.mark.asyncio
    async def test_dispatch_exceed_rate_limit(self, rate_limit_middleware, mock_request, mock_config):
        """Test dispatch when rate limit is exceeded."""
        client_ip = "192.168.1.1"
        
        # Mock the error handler functions
        with patch('src.scanner.services.error_handler.create_rate_limit_error') as mock_create_error:
            mock_error_details = Mock()
            mock_error_details.to_dict.return_value = {"error": "rate_limited"}
            mock_create_error.return_value = mock_error_details
            
            # Simulate requests exceeding the limit + burst (5 + 2 = 7 max, so 8th request should fail)
            current_time = 1000.0
            with patch('time.time', return_value=current_time):
                # Add 7 requests to reach the burst limit
                for i in range(7):
                    rate_limit_middleware.requests[client_ip].append(current_time)
            
            call_next = AsyncMock()
            
            # 8th request should raise HTTPException for rate limit exceeded
            with patch('time.time', return_value=current_time):
                with pytest.raises(HTTPException) as exc_info:
                    await rate_limit_middleware.dispatch(mock_request, call_next)
            
            assert exc_info.value.status_code == 429
            assert "Retry-After" in exc_info.value.headers
            assert exc_info.value.headers["Retry-After"] == "60"
            call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_burst_allowance(self, rate_limit_middleware, mock_request, mock_config):
        """Test dispatch within burst allowance."""
        client_ip = "192.168.1.1"
        
        current_time = 1000.0
        with patch('time.time', return_value=current_time):
            # Add requests up to burst limit (5 + 2 = 7)
            for i in range(6):  # 6 requests (within burst)
                rate_limit_middleware.requests[client_ip].append(current_time)
        
        call_next = AsyncMock()
        mock_response = Mock()
        mock_response.headers = {}
        call_next.return_value = mock_response
        
        # Should still process the request within burst
        with patch('time.time', return_value=current_time):
            result = await rate_limit_middleware.dispatch(mock_request, call_next)
        
        assert result == mock_response
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_rate_limit_window_cleanup(self, rate_limit_middleware, mock_request, mock_config):
        """Test that old requests outside the window are cleaned up."""
        client_ip = "192.168.1.1"
        
        # Add old requests (outside 60-second window)
        old_time = 1000.0
        for i in range(10):
            rate_limit_middleware.requests[client_ip].append(old_time)
        
        # Make new request (current time is 70 seconds later)
        current_time = 1070.0
        call_next = AsyncMock()
        mock_response = Mock()
        mock_response.headers = {}
        call_next.return_value = mock_response
        
        with patch('time.time', return_value=current_time):
            result = await rate_limit_middleware.dispatch(mock_request, call_next)
        
        # Old requests should be cleaned up, new request should go through
        assert result == mock_response
        call_next.assert_called_once_with(mock_request)
        
        # Only the current request should remain
        assert len(rate_limit_middleware.requests[client_ip]) == 1

    @pytest.mark.asyncio
    async def test_different_ips_separate_limits(self, rate_limit_middleware, mock_config):
        """Test that different IPs have separate rate limits."""
        call_next = AsyncMock()
        mock_response = Mock()
        mock_response.headers = {}
        call_next.return_value = mock_response
        
        # Create requests from different IPs
        request1 = Mock(spec=Request)
        request1.client = Mock()
        request1.client.host = "192.168.1.1"
        request1.headers = {}
        
        request2 = Mock(spec=Request)
        request2.client = Mock()
        request2.client.host = "192.168.1.2"
        request2.headers = {}
        
        current_time = 1000.0
        with patch('time.time', return_value=current_time):
            # Each IP should be able to make requests up to their limit
            for _ in range(5):  # Up to the limit
                await rate_limit_middleware.dispatch(request1, call_next)
                await rate_limit_middleware.dispatch(request2, call_next)
        
        # Both IPs should have processed all requests
        assert call_next.call_count == 10
        assert len(rate_limit_middleware.requests["192.168.1.1"]) == 5
        assert len(rate_limit_middleware.requests["192.168.1.2"]) == 5


class TestSecurityHeadersMiddleware:
    """Test cases for SecurityHeadersMiddleware."""

    @pytest.fixture
    def mock_config_production(self):
        """Mock configuration for production environment."""
        with patch('src.scanner.middleware.security.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.is_production = True
            mock_get_config.return_value = mock_config
            yield mock_config

    @pytest.fixture
    def mock_config_development(self):
        """Mock configuration for development environment."""
        with patch('src.scanner.middleware.security.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.is_production = False
            mock_get_config.return_value = mock_config
            yield mock_config

    @pytest.fixture
    def security_middleware(self):
        """Create SecurityHeadersMiddleware instance."""
        app = Mock()
        return SecurityHeadersMiddleware(app)

    @pytest.mark.asyncio
    async def test_security_headers_basic(self, security_middleware, mock_config_development):
        """Test basic security headers are added."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.scheme = "http"
        
        call_next = AsyncMock()
        mock_response = Mock()
        mock_response.headers = {}
        call_next.return_value = mock_response
        
        result = await security_middleware.dispatch(request, call_next)
        
        assert result == mock_response
        call_next.assert_called_once_with(request)
        
        # Check basic security headers
        expected_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options", 
            "X-XSS-Protection",
            "Referrer-Policy",
            "Permissions-Policy",
            "Content-Security-Policy"
        ]
        
        for header in expected_headers:
            assert header in mock_response.headers
        
        assert mock_response.headers["X-Content-Type-Options"] == "nosniff"
        assert mock_response.headers["X-Frame-Options"] == "DENY"
        assert mock_response.headers["X-XSS-Protection"] == "1; mode=block"

    @pytest.mark.asyncio
    async def test_csp_development(self, security_middleware, mock_config_development):
        """Test CSP header in development environment."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.scheme = "http"
        
        call_next = AsyncMock()
        mock_response = Mock()
        mock_response.headers = {}
        call_next.return_value = mock_response
        
        await security_middleware.dispatch(request, call_next)
        
        csp = mock_response.headers["Content-Security-Policy"]
        
        # Development CSP should be more permissive
        assert "'unsafe-inline'" in csp
        assert "'unsafe-eval'" in csp
        assert "connect-src 'self' *" in csp

    @pytest.mark.asyncio
    async def test_csp_production(self, security_middleware, mock_config_production):
        """Test CSP header in production environment."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.scheme = "http"
        
        call_next = AsyncMock()
        mock_response = Mock()
        mock_response.headers = {}
        call_next.return_value = mock_response
        
        await security_middleware.dispatch(request, call_next)
        
        csp = mock_response.headers["Content-Security-Policy"]
        
        # Production CSP should be stricter
        assert "default-src 'self'" in csp
        assert "object-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "connect-src 'self'" in csp  # Not wildcard

    @pytest.mark.asyncio
    async def test_hsts_header_https_production(self, security_middleware, mock_config_production):
        """Test HSTS header is added for HTTPS in production."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.scheme = "https"
        
        call_next = AsyncMock()
        mock_response = Mock()
        mock_response.headers = {}
        call_next.return_value = mock_response
        
        await security_middleware.dispatch(request, call_next)
        
        assert "Strict-Transport-Security" in mock_response.headers
        hsts = mock_response.headers["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts

    @pytest.mark.asyncio
    async def test_no_hsts_header_http_production(self, security_middleware, mock_config_production):
        """Test HSTS header is not added for HTTP in production."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.scheme = "http"
        
        call_next = AsyncMock()
        mock_response = Mock()
        mock_response.headers = {}
        call_next.return_value = mock_response
        
        await security_middleware.dispatch(request, call_next)
        
        assert "Strict-Transport-Security" not in mock_response.headers

    @pytest.mark.asyncio
    async def test_no_hsts_header_development(self, security_middleware, mock_config_development):
        """Test HSTS header is not added in development."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.scheme = "https"
        
        call_next = AsyncMock()
        mock_response = Mock()
        mock_response.headers = {}
        call_next.return_value = mock_response
        
        await security_middleware.dispatch(request, call_next)
        
        assert "Strict-Transport-Security" not in mock_response.headers

    @pytest.mark.asyncio
    async def test_permissions_policy(self, security_middleware, mock_config_development):
        """Test Permissions-Policy header."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.scheme = "http"
        
        call_next = AsyncMock()
        mock_response = Mock()
        mock_response.headers = {}
        call_next.return_value = mock_response
        
        await security_middleware.dispatch(request, call_next)
        
        permissions_policy = mock_response.headers["Permissions-Policy"]
        assert "camera=()" in permissions_policy
        assert "microphone=()" in permissions_policy
        assert "geolocation=()" in permissions_policy

    @pytest.mark.asyncio
    async def test_referrer_policy(self, security_middleware, mock_config_development):
        """Test Referrer-Policy header."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.scheme = "http"
        
        call_next = AsyncMock()
        mock_response = Mock()
        mock_response.headers = {}
        call_next.return_value = mock_response
        
        await security_middleware.dispatch(request, call_next)
        
        referrer_policy = mock_response.headers["Referrer-Policy"]
        assert referrer_policy == "strict-origin-when-cross-origin"


class TestSecurityMiddlewareIntegration:
    """Integration tests for security middleware."""

    @pytest.mark.asyncio
    async def test_rate_limit_middleware_with_real_request(self):
        """Test rate limit middleware with more realistic request setup."""
        # Create a simple ASGI app for testing
        async def app(scope, receive, send):
            response = JSONResponse({"message": "success"})
            await response(scope, receive, send)
        
        with patch('src.scanner.middleware.security.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.rate_limit_enabled = True
            mock_config.rate_limit_per_minute = 2
            mock_config.rate_limit_burst = 1
            mock_get_config.return_value = mock_config
            
            middleware = RateLimitMiddleware(app)
            
            # Create mock request with proper structure
            request = Mock(spec=Request)
            request.client = Mock()
            request.client.host = "192.168.1.1"
            request.headers = {}
            
            # Mock call_next function
            async def call_next(req):
                response = Mock()
                response.headers = {}
                return response
            
            # First request should succeed
            with patch('time.time', return_value=1000.0):
                response1 = await middleware.dispatch(request, call_next)
                assert response1 is not None
            
            # Second request should succeed  
            with patch('time.time', return_value=1001.0):
                response2 = await middleware.dispatch(request, call_next)
                assert response2 is not None
            
            # Third request should succeed (within burst)
            with patch('time.time', return_value=1002.0):
                response3 = await middleware.dispatch(request, call_next)
                assert response3 is not None
            
            # Fourth request should fail (exceeds burst)
            with patch('time.time', return_value=1003.0):
                with pytest.raises(HTTPException) as exc_info:
                    await middleware.dispatch(request, call_next)
                assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_security_headers_middleware_with_real_response(self):
        """Test security headers middleware with realistic response."""
        # Create a simple ASGI app for testing
        async def app(scope, receive, send):
            response = JSONResponse({"message": "success"})
            await response(scope, receive, send)
        
        with patch('src.scanner.middleware.security.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.is_production = False
            mock_get_config.return_value = mock_config
            
            middleware = SecurityHeadersMiddleware(app)
            
            request = Mock(spec=Request)
            request.url = Mock()
            request.url.scheme = "http"
            
            # Mock call_next to return response with headers dict
            async def call_next(req):
                response = Mock()
                response.headers = {}
                return response
            
            result = await middleware.dispatch(request, call_next)
            
            # Verify security headers were added
            assert "X-Content-Type-Options" in result.headers
            assert "X-Frame-Options" in result.headers
            assert "Content-Security-Policy" in result.headers
            assert result.headers["X-Frame-Options"] == "DENY"


class TestCleanupFunction:
    """Test cases for cleanup functions."""

    def test_cleanup_rate_limit_data(self):
        """Test rate limit data cleanup function."""
        # Currently a placeholder function
        result = cleanup_rate_limit_data()
        assert result is None


class TestErrorHandling:
    """Test error handling in security middleware."""

    @pytest.mark.asyncio
    async def test_rate_limit_error_structure(self):
        """Test that rate limit errors have proper structure."""
        with patch('src.scanner.middleware.security.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.rate_limit_enabled = True
            mock_config.rate_limit_per_minute = 1
            mock_config.rate_limit_burst = 0
            mock_get_config.return_value = mock_config
            
            # Mock the error handler
            with patch('src.scanner.services.error_handler.create_rate_limit_error') as mock_create_error:
                mock_error_details = Mock()
                mock_error_details.to_dict.return_value = {"error": "rate_limited", "message": "Rate limit exceeded"}
                mock_create_error.return_value = mock_error_details
                
                app = Mock()
                middleware = RateLimitMiddleware(app)
                
                request = Mock(spec=Request)
                request.client = Mock()
                request.client.host = "192.168.1.1"
                request.headers = {}
                
                current_time = 1000.0
                
                # Add requests to exceed limit (1 + 0 burst = 1 max, so 2nd request should fail)
                middleware.requests["192.168.1.1"] = [current_time]
                
                call_next = AsyncMock()
                
                with patch('time.time', return_value=current_time):
                    with pytest.raises(HTTPException) as exc_info:
                        await middleware.dispatch(request, call_next)
                
                # Verify error structure
                exception = exc_info.value
                assert exception.status_code == 429
                assert isinstance(exception.detail, dict)
                
                # Check headers
                assert "Retry-After" in exception.headers
                assert "X-RateLimit-Limit" in exception.headers
                assert "X-RateLimit-Remaining" in exception.headers
                assert "X-RateLimit-Reset" in exception.headers
                
                assert exception.headers["X-RateLimit-Remaining"] == "0"

    @pytest.mark.asyncio
    async def test_middleware_exception_handling(self):
        """Test middleware behavior when call_next raises exception."""
        with patch('src.scanner.middleware.security.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.rate_limit_enabled = True
            mock_config.rate_limit_per_minute = 10
            mock_config.rate_limit_burst = 2
            mock_get_config.return_value = mock_config
            
            app = Mock()
            middleware = RateLimitMiddleware(app)
            
            request = Mock(spec=Request)
            request.client = Mock()
            request.client.host = "192.168.1.1"
            request.headers = {}
            
            # Mock call_next to raise an exception
            async def call_next_with_error(req):
                raise Exception("Downstream error")
            
            with patch('time.time', return_value=1000.0):
                with pytest.raises(Exception, match="Downstream error"):
                    await middleware.dispatch(request, call_next_with_error)
            
            # Rate limit should still track the attempt
            assert len(middleware.requests["192.168.1.1"]) == 1