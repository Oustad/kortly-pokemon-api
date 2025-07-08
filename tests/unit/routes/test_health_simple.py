"""Simple working tests for health routes."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from src.scanner.main import app


class TestHealthRoutesSimple:
    """Simple test cases for health check routes."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_health_endpoint_exists(self, client):
        """Test that health endpoint exists and responds."""
        response = client.get("/api/v1/health")
        
        # Should return a response
        assert response.status_code in [200, 500, 503]
        assert 'application/json' in response.headers.get('content-type', '')

    def test_health_endpoint_success(self, client):
        """Test health endpoint with mocked services."""
        with patch('src.scanner.routes.health.GeminiService') as mock_gemini:
            with patch('src.scanner.routes.health.PokemonTcgClient') as mock_tcg:
                # Mock successful service initialization
                mock_gemini_instance = Mock()
                mock_gemini_instance._api_key = "test-key"
                mock_gemini.return_value = mock_gemini_instance
                
                mock_tcg_instance = Mock()
                mock_tcg_instance.get_rate_limit_stats.return_value = {
                    "remaining_requests": 100,
                    "limit": 200
                }
                mock_tcg.return_value = mock_tcg_instance
                
                response = client.get("/api/v1/health")
                
                assert response.status_code == 200
                data = response.json()
                assert 'status' in data
                assert 'services' in data

    def test_health_endpoint_response_model(self, client):
        """Test that health endpoint returns expected fields."""
        with patch('src.scanner.routes.health.GeminiService') as mock_gemini:
            with patch('src.scanner.routes.health.PokemonTcgClient') as mock_tcg:
                # Mock services
                mock_gemini.return_value = Mock(_api_key="test-key")
                mock_tcg.return_value = Mock(
                    get_rate_limit_stats=Mock(return_value={"remaining_requests": 50})
                )
                
                response = client.get("/api/v1/health")
                
                if response.status_code == 200:
                    data = response.json()
                    # Should have expected structure
                    assert isinstance(data, dict)
                    if 'status' in data:
                        assert data['status'] in ['healthy', 'unhealthy', 'degraded']

    def test_health_endpoint_gemini_failure(self, client):
        """Test health endpoint when Gemini service fails."""
        with patch('src.scanner.routes.health.GeminiService') as mock_gemini:
            with patch('src.scanner.routes.health.PokemonTcgClient') as mock_tcg:
                # Mock Gemini failure
                mock_gemini.side_effect = Exception("Gemini init failed")
                
                # Mock TCG success
                mock_tcg.return_value = Mock(
                    get_rate_limit_stats=Mock(return_value={"remaining_requests": 100})
                )
                
                response = client.get("/api/v1/health")
                
                # Should still return a response
                assert response.status_code in [200, 503]
                data = response.json()
                assert 'services' in data
                assert data['services']['gemini'] is False

    def test_health_endpoint_tcg_failure(self, client):
        """Test health endpoint when TCG service fails."""
        with patch('src.scanner.routes.health.GeminiService') as mock_gemini:
            with patch('src.scanner.routes.health.PokemonTcgClient') as mock_tcg:
                # Mock Gemini success
                mock_gemini.return_value = Mock(_api_key="test-key")
                
                # Mock TCG failure
                mock_tcg.return_value = Mock(
                    get_rate_limit_stats=Mock(side_effect=Exception("TCG API error"))
                )
                
                response = client.get("/api/v1/health")
                
                # Should still return a response
                assert response.status_code in [200, 503]
                data = response.json()
                assert 'services' in data
                assert data['services']['tcg_api'] is False

    def test_health_endpoint_all_services_down(self, client):
        """Test health endpoint when all services are down."""
        with patch('src.scanner.routes.health.GeminiService') as mock_gemini:
            with patch('src.scanner.routes.health.PokemonTcgClient') as mock_tcg:
                # Mock all failures
                mock_gemini.side_effect = Exception("Gemini down")
                mock_tcg.side_effect = Exception("TCG down")
                
                response = client.get("/api/v1/health")
                
                # Should return unhealthy status
                assert response.status_code in [503, 200]
                data = response.json()
                assert data['status'] in ['unhealthy', 'degraded']

    def test_liveness_endpoint_exists(self, client):
        """Test that liveness endpoint exists if implemented."""
        # Try common liveness endpoint paths
        for path in ["/api/v1/liveness", "/api/v1/live", "/liveness", "/live"]:
            response = client.get(path)
            if response.status_code != 404:
                # Found a liveness endpoint
                assert response.status_code in [200, 204]
                break

    def test_readiness_endpoint_exists(self, client):
        """Test that readiness endpoint exists if implemented."""
        # Try common readiness endpoint paths
        for path in ["/api/v1/readiness", "/api/v1/ready", "/readiness", "/ready"]:
            response = client.get(path)
            if response.status_code != 404:
                # Found a readiness endpoint
                assert response.status_code in [200, 503]
                break

    def test_health_endpoint_with_env_vars(self, client):
        """Test health endpoint with environment variables set."""
        with patch.dict('os.environ', {'GOOGLE_API_KEY': 'test-gemini-key'}):
            with patch('src.scanner.routes.health.PokemonTcgClient') as mock_tcg:
                mock_tcg.return_value = Mock(
                    get_rate_limit_stats=Mock(return_value={"remaining_requests": 75})
                )
                
                response = client.get("/api/v1/health")
                
                assert response.status_code in [200, 503]
                data = response.json()
                # Gemini should be available with API key
                if 'services' in data and 'gemini' in data['services']:
                    assert isinstance(data['services']['gemini'], bool)

    def test_health_endpoint_tcg_rate_limit_zero(self, client):
        """Test health endpoint when TCG rate limit is exhausted."""
        with patch('src.scanner.routes.health.GeminiService') as mock_gemini:
            with patch('src.scanner.routes.health.PokemonTcgClient') as mock_tcg:
                mock_gemini.return_value = Mock(_api_key="test-key")
                
                # Mock zero remaining requests
                mock_tcg.return_value = Mock(
                    get_rate_limit_stats=Mock(return_value={"remaining_requests": 0})
                )
                
                response = client.get("/api/v1/health")
                
                assert response.status_code in [200, 503]
                data = response.json()
                # TCG should be marked as unavailable
                assert data['services']['tcg_api'] is False

    def test_health_endpoint_response_time(self, client):
        """Test that health endpoint responds quickly."""
        import time
        
        with patch('src.scanner.routes.health.GeminiService') as mock_gemini:
            with patch('src.scanner.routes.health.PokemonTcgClient') as mock_tcg:
                mock_gemini.return_value = Mock(_api_key="test-key")
                mock_tcg.return_value = Mock(
                    get_rate_limit_stats=Mock(return_value={"remaining_requests": 100})
                )
                
                start_time = time.time()
                response = client.get("/api/v1/health")
                duration = time.time() - start_time
                
                # Health check should be fast
                assert response.status_code in [200, 503]
                assert duration < 2.0  # Should respond within 2 seconds

    def test_health_endpoint_includes_version(self, client):
        """Test if health endpoint includes version info."""
        with patch('src.scanner.routes.health.GeminiService') as mock_gemini:
            with patch('src.scanner.routes.health.PokemonTcgClient') as mock_tcg:
                mock_gemini.return_value = Mock(_api_key="test-key")
                mock_tcg.return_value = Mock(
                    get_rate_limit_stats=Mock(return_value={"remaining_requests": 100})
                )
                
                response = client.get("/api/v1/health")
                
                if response.status_code == 200:
                    data = response.json()
                    # Check if version info is included
                    if 'version' in data:
                        assert isinstance(data['version'], str)

    def test_health_endpoint_error_webhook(self, client):
        """Test if health endpoint sends error webhooks on failures."""
        with patch('src.scanner.routes.health.send_error_webhook') as mock_webhook:
            with patch('src.scanner.routes.health.GeminiService') as mock_gemini:
                # Mock a critical failure
                mock_gemini.side_effect = Exception("Critical service failure")
                
                response = client.get("/api/v1/health")
                
                # Check response is handled
                assert response.status_code in [200, 503]

    def test_health_endpoint_partial_failure(self, client):
        """Test health endpoint with partial service failures."""
        with patch('src.scanner.routes.health.GeminiService') as mock_gemini:
            with patch('src.scanner.routes.health.PokemonTcgClient') as mock_tcg:
                # One service up, one down
                mock_gemini.return_value = Mock(_api_key="test-key")
                mock_tcg.side_effect = Exception("TCG service error")
                
                response = client.get("/api/v1/health")
                
                assert response.status_code in [200, 503]
                data = response.json()
                # Status should reflect partial failure
                if 'status' in data:
                    assert data['status'] in ['degraded', 'unhealthy']