"""Webhook notification service for error reporting."""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from ..config import get_config

logger = logging.getLogger(__name__)
config = get_config()


class WebhookService:
    """Service for sending webhook notifications on errors."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=config.error_webhook_timeout)
        self._rate_limiter = RateLimiter(config.error_webhook_rate_limit, window=60)
    
    async def send_error_notification(
        self,
        error_message: str,
        level: str = "ERROR",
        request_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        user_agent: Optional[str] = None,
        traceback: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Send error notification to configured webhook.
        
        Args:
            error_message: The error message
            level: Log level (ERROR, CRITICAL, etc.)
            request_id: Unique request identifier
            endpoint: API endpoint where error occurred
            user_agent: User agent string
            traceback: Exception traceback
            context: Additional context information
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        if not config.error_webhook_enabled or not config.error_webhook_url:
            return False
        
        # Validate webhook URL format
        if not self._is_valid_url(config.error_webhook_url):
            logger.error(f"Invalid webhook URL format: {config.error_webhook_url[:50]}...")
            return False
            
        # Check if level meets minimum threshold
        if not self._should_notify(level):
            return False
            
        # Check rate limiting
        if not self._rate_limiter.allow_request():
            logger.warning(f"Webhook notification rate limited for error: {error_message[:100]}...")
            return False
        
        try:
            payload = self._build_payload(
                error_message=error_message,
                level=level,
                request_id=request_id,
                endpoint=endpoint,
                user_agent=user_agent,
                traceback=traceback,
                context=context,
            )
            
            # Send webhook notification
            response = await self.client.post(
                config.error_webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            
            if response.status_code == 200:
                logger.debug(f"Webhook notification sent successfully for error: {error_message[:100]}...")
                return True
            else:
                logger.warning(
                    f"Webhook notification failed with status {response.status_code}: {response.text}"
                )
                return False
                
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {str(e)}")
            return False
    
    def _should_notify(self, level: str) -> bool:
        """Check if the error level meets the minimum threshold."""
        level_priority = {
            "DEBUG": 10,
            "INFO": 20,
            "WARNING": 30,
            "ERROR": 40,
            "CRITICAL": 50,
        }
        
        min_level = config.error_webhook_min_level
        return level_priority.get(level, 0) >= level_priority.get(min_level, 40)
    
    def _build_payload(
        self,
        error_message: str,
        level: str,
        request_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        user_agent: Optional[str] = None,
        traceback: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build webhook payload."""
        payload = {
            "environment": config.error_webhook_environment_tag,
            "service": "pokemon-card-scanner",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": level,
            "message": error_message,
        }
        
        if request_id:
            payload["request_id"] = request_id
        if endpoint:
            payload["endpoint"] = endpoint
        if user_agent:
            payload["user_agent"] = user_agent
        if context:
            payload["context"] = context
        if traceback and config.error_webhook_include_traceback:
            payload["traceback"] = traceback
            
        return payload
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        if not url:
            return False
        
        # Basic URL validation - must start with http:// or https://
        if not (url.startswith("http://") or url.startswith("https://")):
            return False
        
        # Must have a domain after the protocol
        if url in ["http://", "https://"]:
            return False
        
        # Check for basic URL structure
        try:
            # Simple validation - split by protocol and check domain exists
            parts = url.split("://", 1)
            if len(parts) != 2:
                return False
            
            domain_part = parts[1]
            # Must have at least a domain
            if not domain_part or domain_part.startswith("/"):
                return False
            
            return True
        except Exception:
            return False
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, max_requests: int, window: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed in the window
            window: Time window in seconds
        """
        self.max_requests = max_requests
        self.window = window
        self.requests = []
    
    def allow_request(self) -> bool:
        """Check if a request is allowed within the rate limit."""
        now = time.time()
        
        # Remove old requests outside the window
        self.requests = [req_time for req_time in self.requests if now - req_time < self.window]
        
        # Check if we're under the limit
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        
        return False


# Global webhook service instance
_webhook_service: Optional[WebhookService] = None


def get_webhook_service() -> WebhookService:
    """Get global webhook service instance."""
    global _webhook_service
    if _webhook_service is None:
        _webhook_service = WebhookService()
    return _webhook_service


async def send_error_webhook(
    error_message: str,
    level: str = "ERROR",
    request_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    user_agent: Optional[str] = None,
    traceback: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Convenience function to send error webhook notification.
    
    Args:
        error_message: The error message
        level: Log level (ERROR, CRITICAL, etc.)
        request_id: Unique request identifier
        endpoint: API endpoint where error occurred
        user_agent: User agent string
        traceback: Exception traceback
        context: Additional context information
        
    Returns:
        True if notification was sent successfully, False otherwise
    """
    webhook_service = get_webhook_service()
    return await webhook_service.send_error_notification(
        error_message=error_message,
        level=level,
        request_id=request_id,
        endpoint=endpoint,
        user_agent=user_agent,
        traceback=traceback,
        context=context,
    )