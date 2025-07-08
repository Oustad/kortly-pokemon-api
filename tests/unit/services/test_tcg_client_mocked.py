"""Properly mocked tests for tcg_client.py to achieve higher coverage."""

import pytest
import asyncio
import hashlib
import json
import time
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

# Mock external dependencies before importing
mock_httpx = Mock()
mock_httpx.AsyncClient = Mock()
mock_httpx.HTTPError = type('HTTPError', (Exception,), {})
mock_httpx.HTTPStatusError = type('HTTPStatusError', (Exception,), {})
mock_httpx.Timeout = Mock()

# Mock tenacity decorators
def mock_retry(**kwargs):
    def decorator(func):
        return func
    return decorator

mock_tenacity = Mock()
mock_tenacity.retry = mock_retry
mock_tenacity.retry_if_exception_type = Mock()
mock_tenacity.stop_after_attempt = Mock()
mock_tenacity.wait_exponential = Mock()

# Apply mocks before importing
with patch.dict('sys.modules', {
    'httpx': mock_httpx,
    'tenacity': mock_tenacity,
}):
    from src.scanner.services.tcg_client import (
        PokemonTcgClient,
        RateLimitError,
        PokemonTcgApiError
    )


class TestPokemonTcgClientMocked:
    """Test PokemonTcgClient with proper mocking."""

    def test_initialization_with_api_key(self):
        """Test client initialization with API key."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient(
            api_key="test-key",
            base_url="https://api.test.com",
            rate_limit=50,
            cache_ttl=1800
        )
        
        assert client.api_key == "test-key"
        assert client.base_url == "https://api.test.com"
        assert client.rate_limit == 50
        assert client.cache_ttl == 1800
        assert client.cache == {}
        assert client.request_timestamps == []

    def test_initialization_without_api_key(self):
        """Test client initialization without API key."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        assert client.api_key is None
        assert client.base_url == "https://api.pokemontcg.io/v2"
        assert client.rate_limit == 100
        assert client.cache_ttl == 3600

    def test_initialization_headers_with_api_key(self):
        """Test HTTP client headers with API key."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient(api_key="test-key")
        
        # Check that AsyncClient was called with correct headers
        call_args = mock_httpx.AsyncClient.call_args
        headers = call_args[1]['headers']
        assert headers['X-Api-Key'] == "test-key"
        assert headers['Accept'] == "application/json"

    def test_initialization_headers_without_api_key(self):
        """Test HTTP client headers without API key."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        # Check that AsyncClient was called with correct headers
        call_args = mock_httpx.AsyncClient.call_args
        headers = call_args[1]['headers']
        assert 'X-Api-Key' not in headers
        assert headers['Accept'] == "application/json"

    @pytest.mark.asyncio
    async def test_async_context_manager_enter(self):
        """Test async context manager entry."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        result = await client.__aenter__()
        
        assert result is client

    @pytest.mark.asyncio
    async def test_async_context_manager_exit(self):
        """Test async context manager exit."""
        mock_client = Mock()
        mock_client.aclose = AsyncMock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        await client.__aexit__(None, None, None)
        
        mock_client.aclose.assert_called_once()

    def test_is_rate_limited_empty_timestamps(self):
        """Test rate limiting with no previous requests."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient(rate_limit=10)
        
        result = client._is_rate_limited()
        
        assert result is False

    def test_is_rate_limited_under_limit(self):
        """Test rate limiting when under limit."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient(rate_limit=10)
        
        # Add some recent timestamps
        now = time.time()
        client.request_timestamps = [now - 1800, now - 1200, now - 600]  # 3 requests in last hour
        
        result = client._is_rate_limited()
        
        assert result is False

    def test_is_rate_limited_at_limit(self):
        """Test rate limiting when at limit."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient(rate_limit=3)
        
        # Add timestamps at limit
        now = time.time()
        client.request_timestamps = [now - 1800, now - 1200, now - 600]  # 3 requests in last hour
        
        result = client._is_rate_limited()
        
        assert result is True

    def test_is_rate_limited_cleanup_old_timestamps(self):
        """Test that old timestamps are cleaned up."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient(rate_limit=10)
        
        # Add old and recent timestamps
        now = time.time()
        client.request_timestamps = [
            now - 7200,  # 2 hours ago (should be removed)
            now - 1800,  # 30 minutes ago (should be kept)
            now - 600,   # 10 minutes ago (should be kept)
        ]
        
        result = client._is_rate_limited()
        
        assert result is False
        assert len(client.request_timestamps) == 2  # Old timestamp removed

    def test_get_cache_key_basic(self):
        """Test cache key generation with basic parameters."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        result = client._get_cache_key("/cards", {"q": "name:Pikachu"})
        
        # Should be a valid MD5 hash
        assert len(result) == 32
        assert isinstance(result, str)

    def test_get_cache_key_no_params(self):
        """Test cache key generation without parameters."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        result = client._get_cache_key("/cards")
        
        # Should be a valid MD5 hash
        assert len(result) == 32
        assert isinstance(result, str)

    def test_get_cache_key_consistent(self):
        """Test that cache key generation is consistent."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        key1 = client._get_cache_key("/cards", {"q": "name:Pikachu"})
        key2 = client._get_cache_key("/cards", {"q": "name:Pikachu"})
        
        assert key1 == key2

    def test_get_from_cache_miss(self):
        """Test cache retrieval with cache miss."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        result = client._get_from_cache("nonexistent_key")
        
        assert result is None

    def test_get_from_cache_hit_valid(self):
        """Test cache retrieval with valid cache hit."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        # Add valid cache entry
        cache_key = "test_key"
        test_data = {"name": "Pikachu"}
        client.cache[cache_key] = {
            "data": test_data,
            "expires_at": time.time() + 3600  # Expires in 1 hour
        }
        
        result = client._get_from_cache(cache_key)
        
        assert result == test_data

    def test_get_from_cache_hit_expired(self):
        """Test cache retrieval with expired cache entry."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        # Add expired cache entry
        cache_key = "test_key"
        test_data = {"name": "Pikachu"}
        client.cache[cache_key] = {
            "data": test_data,
            "expires_at": time.time() - 3600  # Expired 1 hour ago
        }
        
        result = client._get_from_cache(cache_key)
        
        assert result is None
        assert cache_key not in client.cache  # Should be cleaned up

    def test_add_to_cache(self):
        """Test adding data to cache."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient(cache_ttl=1800)
        
        cache_key = "test_key"
        test_data = {"name": "Charizard"}
        
        client._add_to_cache(cache_key, test_data)
        
        assert cache_key in client.cache
        assert client.cache[cache_key]["data"] == test_data
        assert client.cache[cache_key]["expires_at"] > time.time()

    @pytest.mark.asyncio
    async def test_make_request_successful(self):
        """Test successful HTTP request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"name": "Pikachu"}]}
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        result = await client._make_request("GET", "/cards", params={"q": "name:Pikachu"})
        
        assert result == {"data": [{"name": "Pikachu"}]}
        mock_client.request.assert_called_once_with(
            "GET", "/cards", params={"q": "name:Pikachu"}
        )

    @pytest.mark.asyncio
    async def test_make_request_rate_limited(self):
        """Test HTTP request when rate limited."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient(rate_limit=1)
        
        # Fill up rate limit
        now = time.time()
        client.request_timestamps = [now - 1800]  # 1 request in last hour
        
        with pytest.raises(RateLimitError):
            await client._make_request("GET", "/cards")

    @pytest.mark.asyncio
    async def test_make_request_http_status_error_429(self):
        """Test HTTP request with 429 status error."""
        mock_response = Mock()
        mock_response.status_code = 429
        
        mock_error = mock_httpx.HTTPStatusError("Rate limit exceeded")
        mock_error.response = mock_response
        
        mock_client = Mock()
        mock_client.request = AsyncMock(side_effect=mock_error)
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        with pytest.raises(RateLimitError):
            await client._make_request("GET", "/cards")

    @pytest.mark.asyncio
    async def test_make_request_http_status_error_400(self):
        """Test HTTP request with 400+ status error."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "Bad request"}
        mock_response.content = b'{"error": "Bad request"}'
        
        mock_error = mock_httpx.HTTPStatusError("Bad request")
        mock_error.response = mock_response
        
        mock_client = Mock()
        mock_client.request = AsyncMock(side_effect=mock_error)
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        with pytest.raises(PokemonTcgApiError):
            await client._make_request("GET", "/cards")

    @pytest.mark.asyncio
    async def test_make_request_http_error(self):
        """Test HTTP request with generic HTTP error."""
        mock_error = mock_httpx.HTTPError("Connection error")
        
        mock_client = Mock()
        mock_client.request = AsyncMock(side_effect=mock_error)
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        with pytest.raises(mock_httpx.HTTPError):
            await client._make_request("GET", "/cards")

    @pytest.mark.asyncio
    async def test_search_cards_basic(self):
        """Test basic card search."""
        mock_response_data = {
            "data": [{"name": "Pikachu", "set": {"name": "Base Set"}}],
            "page": 1,
            "pageSize": 20,
            "count": 1,
            "totalCount": 1
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        result = await client.search_cards(name="Pikachu")
        
        assert result == mock_response_data

    @pytest.mark.asyncio
    async def test_search_cards_with_all_params(self):
        """Test card search with all parameters."""
        mock_response_data = {"data": [{"name": "Charizard"}]}
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        result = await client.search_cards(
            name="Charizard",
            set_name="Base Set",
            number="4",
            supertype="Pokemon",
            types=["Fire"],
            hp="120",
            page=2,
            page_size=50,
            order_by="name",
            fuzzy=False
        )
        
        assert result == mock_response_data
        
        # Check that request was made with correct parameters
        call_args = mock_client.request.call_args
        params = call_args[1]['params']
        assert params['page'] == 2
        assert params['pageSize'] == 50
        assert 'q' in params

    @pytest.mark.asyncio
    async def test_search_cards_cache_hit(self):
        """Test card search with cache hit."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        # Add cached data
        cache_key = client._get_cache_key("/cards", {"page": 1, "pageSize": 20, "q": 'name:"Pikachu*"'})
        cached_data = {"data": [{"name": "Pikachu"}]}
        client._add_to_cache(cache_key, cached_data)
        
        result = await client.search_cards(name="Pikachu")
        
        assert result == cached_data
        # Should not make HTTP request
        mock_client.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_card_by_id_basic(self):
        """Test getting card by ID."""
        mock_response_data = {
            "data": {"id": "base1-25", "name": "Pikachu"}
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        result = await client.get_card_by_id("base1-25")
        
        assert result == mock_response_data

    @pytest.mark.asyncio
    async def test_get_card_by_id_cache_hit(self):
        """Test getting card by ID with cache hit."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        # Add cached data
        cache_key = client._get_cache_key("/cards/base1-25")
        cached_data = {"data": {"id": "base1-25", "name": "Pikachu"}}
        client._add_to_cache(cache_key, cached_data)
        
        result = await client.get_card_by_id("base1-25")
        
        assert result == cached_data
        # Should not make HTTP request
        mock_client.request.assert_not_called()

    def test_clear_cache(self):
        """Test clearing cache."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        # Add some cache entries
        client.cache["key1"] = {"data": "value1", "expires_at": time.time() + 3600}
        client.cache["key2"] = {"data": "value2", "expires_at": time.time() + 3600}
        
        client.clear_cache()
        
        assert len(client.cache) == 0

    def test_get_cache_stats(self):
        """Test getting cache statistics."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient(cache_ttl=3600)
        
        # Add cache entries (active and expired)
        now = time.time()
        client.cache["active1"] = {"data": "value1", "expires_at": now + 1800}
        client.cache["active2"] = {"data": "value2", "expires_at": now + 3600}
        client.cache["expired1"] = {"data": "value3", "expires_at": now - 1800}
        
        stats = client.get_cache_stats()
        
        assert stats["total_entries"] == 3
        assert stats["active_entries"] == 2
        assert stats["expired_entries"] == 1
        assert stats["cache_ttl_seconds"] == 3600

    def test_get_rate_limit_stats(self):
        """Test getting rate limit statistics."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient(rate_limit=100)
        
        # Add some request timestamps
        now = time.time()
        client.request_timestamps = [
            now - 1800,  # 30 minutes ago
            now - 600,   # 10 minutes ago
            now - 300,   # 5 minutes ago
        ]
        
        stats = client.get_rate_limit_stats()
        
        assert stats["requests_last_hour"] == 3
        assert stats["rate_limit"] == 100
        assert stats["remaining_requests"] == 97

    def test_map_set_name_direct_mapping(self):
        """Test set name mapping with direct match."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        result = client._map_set_name("Base Set")
        
        assert result == "Base"

    def test_map_set_name_case_insensitive(self):
        """Test set name mapping with case insensitive match."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        result = client._map_set_name("base set")
        
        assert result == "Base"

    def test_map_set_name_no_mapping(self):
        """Test set name mapping with no match."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        result = client._map_set_name("Unknown Set")
        
        assert result == "Unknown Set"

    def test_map_set_name_none_input(self):
        """Test set name mapping with None input."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        result = client._map_set_name(None)
        
        assert result is None

    def test_normalize_pokemon_name_basic(self):
        """Test basic Pokemon name normalization."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        result = client._normalize_pokemon_name("Pikachu")
        
        assert result == "Pikachu"

    def test_normalize_pokemon_name_translation(self):
        """Test Pokemon name normalization with translation."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        result = client._normalize_pokemon_name("Goupix")
        
        assert result == "Vulpix"

    def test_normalize_pokemon_name_apostrophe_fix(self):
        """Test Pokemon name normalization with apostrophe fix."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        result = client._normalize_pokemon_name("Farfetchd")
        
        assert result == "Farfetch'd"

    def test_normalize_pokemon_name_gx_fix(self):
        """Test Pokemon name normalization with GX fix."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        result = client._normalize_pokemon_name("Espeon GX")
        
        assert result == "Espeon-GX"

    def test_normalize_pokemon_name_none_input(self):
        """Test Pokemon name normalization with None input."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        result = client._normalize_pokemon_name(None)
        
        assert result is None

    def test_normalize_card_number_basic(self):
        """Test basic card number normalization."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        result = client._normalize_card_number("025")
        
        assert result == "25"

    def test_normalize_card_number_with_variant(self):
        """Test card number normalization with variant suffix."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        result = client._normalize_card_number("177a")
        
        assert result == "177a"

    def test_normalize_card_number_with_slash(self):
        """Test card number normalization with slash format."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        result = client._normalize_card_number("177a/168")
        
        assert result == "177a"

    def test_normalize_card_number_none_input(self):
        """Test card number normalization with None input."""
        mock_client = Mock()
        mock_httpx.AsyncClient.return_value = mock_client
        
        client = PokemonTcgClient()
        
        result = client._normalize_card_number(None)
        
        assert result is None


class TestHelperFunctions:
    """Test helper functions."""

    def test_normalize_energy_symbols_basic(self):
        """Test basic energy symbol normalization."""
        from src.scanner.services.tcg_client import _normalize_energy_symbols
        
        result = _normalize_energy_symbols("Basic ⚡ Energy")
        
        assert result == "Basic Lightning Energy"

    def test_normalize_energy_symbols_multiple(self):
        """Test energy symbol normalization with multiple symbols."""
        from src.scanner.services.tcg_client import _normalize_energy_symbols
        
        result = _normalize_energy_symbols("⚡ Energy and 🔥 Energy")
        
        assert result == "Lightning Energy and Fire Energy"

    def test_normalize_energy_symbols_none_input(self):
        """Test energy symbol normalization with None input."""
        from src.scanner.services.tcg_client import _normalize_energy_symbols
        
        result = _normalize_energy_symbols(None)
        
        assert result is None

    def test_normalize_energy_symbols_no_symbols(self):
        """Test energy symbol normalization with no symbols."""
        from src.scanner.services.tcg_client import _normalize_energy_symbols
        
        result = _normalize_energy_symbols("Regular card text")
        
        assert result == "Regular card text"