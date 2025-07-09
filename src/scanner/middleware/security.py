"""Security middleware for rate limiting and security headers."""

import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import get_config


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware to prevent abuse."""
    
    def __init__(self, app):
        super().__init__(app)
        self.requests = defaultdict(list)  # IP -> list of request timestamps
        self.window = 60  # 1 minute window
    
    async def dispatch(self, request: Request, call_next: Callable):
        config = get_config()
        if not config.rate_limit_enabled:
            return await call_next(request)
        
        client_ip = self._get_client_ip(request)
        current_time = time.time()
        
        # Clean old requests outside the window
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if current_time - req_time < self.window
        ]
        
        # Check if client exceeds rate limit
        if len(self.requests[client_ip]) >= config.rate_limit_per_minute:
            # Allow burst for established clients
            if len(self.requests[client_ip]) < config.rate_limit_per_minute + config.rate_limit_burst:
                # Add to requests but continue
                self.requests[client_ip].append(current_time)
            else:
                from ..services.error_handler import create_rate_limit_error
                error_details = create_rate_limit_error(
                    limit=config.rate_limit_per_minute,
                    window="minute",
                    retry_after=60
                )
                
                # We still need to raise HTTPException here for middleware, but with structured detail
                raise HTTPException(
                    status_code=429,
                    detail=error_details.to_dict(),
                    headers={
                        "Retry-After": "60",
                        "X-RateLimit-Limit": str(config.rate_limit_per_minute),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(current_time + self.window)),
                    }
                )
        
        # Add current request
        self.requests[client_ip].append(current_time)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        remaining = max(0, config.rate_limit_per_minute - len(self.requests[client_ip]))
        response.headers["X-RateLimit-Limit"] = str(config.rate_limit_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(current_time + self.window))
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        # Check for forwarded headers (for reverse proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to responses."""
    
    async def dispatch(self, request: Request, call_next: Callable):
        config = get_config()
        response = await call_next(request)
        
        # Security headers
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        }
        
        # Add Content Security Policy
        if config.is_production:
            # Strict CSP for production
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob:; "
                "connect-src 'self'; "
                "font-src 'self'; "
                "object-src 'none'; "
                "media-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
        else:
            # More permissive CSP for development
            csp = (
                "default-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "img-src 'self' data: blob: *; "
                "connect-src 'self' *; "
                "frame-ancestors 'none'"
            )
        
        security_headers["Content-Security-Policy"] = csp
        
        # Add HSTS header for HTTPS in production
        if config.is_production and request.url.scheme == "https":
            security_headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Add headers to response
        for header, value in security_headers.items():
            response.headers[header] = value
        
        return response