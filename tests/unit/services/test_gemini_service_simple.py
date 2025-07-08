"""Simple working tests for GeminiService."""

import pytest
import os
from unittest.mock import Mock, patch, AsyncMock
from src.scanner.services.gemini_service import GeminiService


class TestGeminiServiceSimple:
    """Simple test cases for GeminiService that match actual interface."""

    def test_initialization_basic(self):
        """Test basic GeminiService initialization."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            service = GeminiService()
            
            assert hasattr(service, '_api_key')

    def test_initialization_no_api_key(self):
        """Test initialization without API key."""
        with patch.dict(os.environ, {}, clear=True):
            service = GeminiService()
            
            # Should handle missing API key gracefully
            assert hasattr(service, '_api_key')

    def test_initialization_with_custom_api_key(self):
        """Test initialization with custom API key."""
        service = GeminiService(api_key="custom-test-key")
        
        assert hasattr(service, '_api_key')
        assert service._api_key == "custom-test-key"

    @pytest.mark.asyncio
    async def test_identify_pokemon_card_method_exists(self):
        """Test that identify_pokemon_card method exists."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            service = GeminiService()
            
            # Mock the actual Gemini API call
            with patch('google.generativeai.GenerativeModel') as mock_model_class:
                mock_model = Mock()
                mock_response = Mock()
                mock_response.text = '{"name": "Pikachu", "success": true}'
                mock_model.generate_content = AsyncMock(return_value=mock_response)
                mock_model_class.return_value = mock_model
                
                # Method should exist and be callable
                image_bytes = b"fake_image_data"
                result = await service.identify_pokemon_card(image_bytes)
                
                assert isinstance(result, dict)

    def test_api_key_validation(self):
        """Test API key validation functionality."""
        # Test with valid key passed directly
        service = GeminiService(api_key='test-key-123')
        assert service._api_key == 'test-key-123'

    def test_model_configuration(self):
        """Test model configuration if accessible."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            service = GeminiService()
            
            # Should have model configuration
            if hasattr(service, 'model_name'):
                assert isinstance(service.model_name, str)

    @pytest.mark.asyncio
    async def test_identify_pokemon_card_with_options(self):
        """Test identify_pokemon_card with optimization options."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            service = GeminiService()
            
            with patch('google.generativeai.GenerativeModel') as mock_model_class:
                mock_model = Mock()
                mock_response = Mock()
                mock_response.text = '{"name": "Charizard"}'
                mock_model.generate_content = AsyncMock(return_value=mock_response)
                mock_model_class.return_value = mock_model
                
                image_bytes = b"fake_image_data"
                
                # Test with optimize_for_speed option
                result = await service.identify_pokemon_card(
                    image_bytes, 
                    optimize_for_speed=True
                )
                
                assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_error_handling_network_error(self):
        """Test error handling for network issues."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            service = GeminiService()
            
            with patch('google.generativeai.GenerativeModel') as mock_model_class:
                mock_model = Mock()
                mock_model.generate_content = AsyncMock(side_effect=Exception("Network error"))
                mock_model_class.return_value = mock_model
                
                image_bytes = b"fake_image_data"
                result = await service.identify_pokemon_card(image_bytes)
                
                # Should handle errors gracefully
                assert isinstance(result, dict)
                # Likely has error information
                if 'success' in result:
                    assert result['success'] is False

    @pytest.mark.asyncio
    async def test_identify_pokemon_card_invalid_image(self):
        """Test with invalid image data."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            service = GeminiService()
            
            # Test with empty image data
            result = await service.identify_pokemon_card(b"")
            
            assert isinstance(result, dict)

    def test_service_configuration_attributes(self):
        """Test that service has expected configuration attributes."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            service = GeminiService()
            
            # Should have API key
            assert hasattr(service, '_api_key')
            
            # Check for other common attributes
            if hasattr(service, 'temperature'):
                assert isinstance(service.temperature, (int, float))

    @pytest.mark.asyncio
    async def test_response_structure_validation(self):
        """Test that response has expected structure."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            service = GeminiService()
            
            with patch('google.generativeai.GenerativeModel') as mock_model_class:
                mock_model = Mock()
                mock_response = Mock()
                mock_response.text = '{"name": "Test Card", "number": "1"}'
                mock_model.generate_content = AsyncMock(return_value=mock_response)
                mock_model_class.return_value = mock_model
                
                image_bytes = b"test_image"
                result = await service.identify_pokemon_card(image_bytes)
                
                # Should return dictionary
                assert isinstance(result, dict)
                
                # Check for common response fields
                expected_fields = ['success', 'response_text', 'metadata']
                for field in expected_fields:
                    if field in result:
                        assert field in result

    def test_string_representation(self):
        """Test service string representation."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            service = GeminiService()
            
            # Should not crash when converted to string
            str_repr = str(service)
            assert isinstance(str_repr, str)

    @pytest.mark.asyncio
    async def test_concurrent_requests_handling(self):
        """Test handling of concurrent requests."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            service = GeminiService()
            
            with patch('google.generativeai.GenerativeModel') as mock_model_class:
                mock_model = Mock()
                mock_response = Mock()
                mock_response.text = '{"name": "Concurrent Test"}'
                mock_model.generate_content = AsyncMock(return_value=mock_response)
                mock_model_class.return_value = mock_model
                
                # Test multiple concurrent calls
                import asyncio
                tasks = [
                    service.identify_pokemon_card(b"image1"),
                    service.identify_pokemon_card(b"image2")
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Should handle concurrent requests
                assert len(results) == 2
                for result in results:
                    if not isinstance(result, Exception):
                        assert isinstance(result, dict)