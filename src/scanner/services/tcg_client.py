"""
Pokemon TCG API Client with rate limiting and caching.
Simplified version focusing on card search functionality.
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Raised when API rate limit is exceeded."""
    pass


class PokemonTcgApiError(Exception):
    """Raised when Pokemon TCG API returns an error."""
    pass


class PokemonTcgClient:
    """
    Client for interacting with the Pokemon TCG API.
    
    Features:
    - Asynchronous HTTP requests
    - Rate limiting (100 requests per hour by default)
    - Simple in-memory caching
    - Automatic retry with exponential backoff
    - Comprehensive error handling
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.pokemontcg.io/v2",
        rate_limit: int = 100,
        cache_ttl: int = 3600,
    ):
        """
        Initialize the Pokemon TCG API client.
        
        Args:
            api_key: API key for authentication (optional for higher rate limits)
            base_url: Base URL for the API
            rate_limit: Maximum requests per hour
            cache_ttl: Cache time-to-live in seconds
        """
        self.api_key = api_key
        self.base_url = base_url
        self.rate_limit = rate_limit
        self.cache_ttl = cache_ttl
        
        # Simple in-memory cache
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.request_timestamps: List[float] = []
        
        # Configure HTTP client
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
            
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(30.0),
        )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - close HTTP client."""
        await self.client.aclose()

    def _is_rate_limited(self) -> bool:
        """Check if we've exceeded rate limits."""
        now = time.time()
        hour_ago = now - 3600
        
        # Remove timestamps older than 1 hour
        self.request_timestamps = [
            ts for ts in self.request_timestamps if ts > hour_ago
        ]
        
        # Check if we've exceeded the limit
        return len(self.request_timestamps) >= self.rate_limit

    def _get_cache_key(self, endpoint: str, params: Optional[Dict] = None) -> str:
        """Generate cache key from endpoint and parameters."""
        key_parts = {"endpoint": endpoint, "params": params or {}}
        key_string = json.dumps(key_parts, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Retrieve data from cache if available and not expired."""
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            if entry["expires_at"] > time.time():
                return entry["data"]
            else:
                # Expired, remove from cache
                del self.cache[cache_key]
        return None

    def _add_to_cache(self, cache_key: str, data: Any) -> None:
        """Add response data to cache with timestamp."""
        self.cache[cache_key] = {
            "data": data,
            "expires_at": time.time() + self.cache_ttl,
        }

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Dict[str, Any]:
        """Make an HTTP request with rate limiting and error handling."""
        # Check rate limit
        if self._is_rate_limited():
            logger.warning(f"🚫 Rate limit exceeded: {self.rate_limit} requests per hour")
            raise RateLimitError(
                f"Rate limit exceeded: {self.rate_limit} requests per hour"
            )
        
        # Record request timestamp
        self.request_timestamps.append(time.time())
        
        # Log request
        url = f"{self.base_url}{endpoint}"
        logger.info(f"🌐 Pokemon TCG API Request: {method} {url}")
        if kwargs.get("params"):
            logger.info(f"   Parameters: {kwargs['params']}")
        
        try:
            start_time = time.time()
            response = await self.client.request(method, endpoint, **kwargs)
            response.raise_for_status()
            request_time = time.time() - start_time
            
            # Log response
            logger.info(f"   ✓ Response: {response.status_code} in {request_time:.2f}s")
            
            # Parse JSON response
            data = response.json()
            
            # Log data summary
            if isinstance(data, dict) and "data" in data:
                if isinstance(data["data"], list):
                    logger.info(f"   ← Received {len(data['data'])} items")
                else:
                    logger.info(f"   ← Received single item")
            
            return data
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitError("API rate limit exceeded") from e
            elif e.response.status_code >= 400:
                error_data = e.response.json() if e.response.content else {}
                logger.error(f"   ✗ API error {e.response.status_code}: {error_data}")
                raise PokemonTcgApiError(
                    f"API error {e.response.status_code}: {error_data}"
                ) from e
            raise

    async def search_cards(
        self,
        name: Optional[str] = None,
        set_name: Optional[str] = None,
        number: Optional[str] = None,
        supertype: Optional[str] = None,
        types: Optional[List[str]] = None,
        hp: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        order_by: Optional[str] = None,
        fuzzy: bool = True,
    ) -> Dict[str, Any]:
        """
        Search for Pokemon cards with various filters.
        
        Args:
            name: Card name to search for
            set_name: Set name to filter by
            number: Card number in set
            supertype: Card supertype (Pokemon, Trainer, Energy)
            types: List of Pokemon types to filter by
            hp: HP value to filter by
            page: Page number for pagination
            page_size: Number of results per page
            order_by: Field to order results by
            fuzzy: Enable fuzzy matching for names
            
        Returns:
            API response with matching cards
        """
        # Build query parameters
        params = {
            "page": page,
            "pageSize": min(page_size, 250),  # API max is 250
        }
        
        # Build query string
        query_parts = []
        if name:
            if fuzzy:
                query_parts.append(f'name:"{name}*"')
            else:
                query_parts.append(f'name:"{name}"')
        if set_name:
            query_parts.append(f'set.name:"{set_name}"')
        if number:
            query_parts.append(f'number:{number}')
        if supertype:
            query_parts.append(f'supertype:{supertype}')
        if types:
            for ptype in types:
                query_parts.append(f'types:{ptype}')
        if hp:
            query_parts.append(f'hp:{hp}')
            
        if query_parts:
            params["q"] = " ".join(query_parts)
            
        if order_by:
            params["orderBy"] = order_by
            
        # Create cache key
        cache_key = self._get_cache_key("/cards", params)
        
        # Check cache
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            logger.info("📦 Cache hit for card search")
            return cached_data
            
        # Make request
        data = await self._make_request("GET", "/cards", params=params)
        
        # Cache response
        self._add_to_cache(cache_key, data)
        
        return data

    async def get_card_by_id(self, card_id: str) -> Dict[str, Any]:
        """
        Get a specific Pokemon card by ID.
        
        Args:
            card_id: Unique card ID (e.g., "base1-25")
            
        Returns:
            Card data
        """
        # Check cache
        cache_key = self._get_cache_key(f"/cards/{card_id}")
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            logger.info(f"📦 Cache hit for card: {card_id}")
            return cached_data
            
        logger.info(f"🔍 Fetching card from API: {card_id}")
        # Make request
        data = await self._make_request("GET", f"/cards/{card_id}")
        
        # Cache response
        self._add_to_cache(cache_key, data)
        logger.info(f"   💾 Cached card: {card_id}")
        
        return data

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self.cache.clear()
        logger.info("🗑️ Cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        current_time = time.time()
        active_entries = sum(
            1 for entry in self.cache.values() 
            if entry["expires_at"] > current_time
        )
        
        return {
            "total_entries": len(self.cache),
            "active_entries": active_entries,
            "expired_entries": len(self.cache) - active_entries,
            "cache_ttl_seconds": self.cache_ttl,
        }
    
    def get_rate_limit_stats(self) -> Dict[str, Any]:
        """Get rate limiting statistics."""
        now = time.time()
        hour_ago = now - 3600
        
        # Count requests in the last hour
        recent_requests = [
            ts for ts in self.request_timestamps if ts > hour_ago
        ]
        
        return {
            "requests_last_hour": len(recent_requests),
            "rate_limit": self.rate_limit,
            "remaining_requests": max(0, self.rate_limit - len(recent_requests)),
        }