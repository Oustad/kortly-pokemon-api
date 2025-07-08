"""Properly mocked tests for gemini_service.py to achieve higher coverage."""

import pytest
import io
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any


class TestGeminiServiceProperlyMocked:
    """Test GeminiService with complete mocking of external dependencies."""

    def test_initialization_with_api_key(self):
        """Test service initialization with API key."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            from src.scanner.services.gemini_service import GeminiService
            
            service = GeminiService(api_key="test-key")
            assert service._api_key == "test-key"
            assert service._model is None

    def test_initialization_without_api_key(self):
        """Test service initialization without API key."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            from src.scanner.services.gemini_service import GeminiService
            
            service = GeminiService()
            assert service._api_key is None
            assert service._model is None

    def test_initialization_with_whitespace_api_key(self):
        """Test service initialization with whitespace in API key."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            from src.scanner.services.gemini_service import GeminiService
            
            service = GeminiService(api_key="  test-key  ")
            assert service._api_key == "test-key"

    def test_initialization_with_empty_api_key(self):
        """Test service initialization with empty API key."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            from src.scanner.services.gemini_service import GeminiService
            
            service = GeminiService(api_key="")
            assert service._api_key == ""

    def test_model_property_with_api_key(self):
        """Test model property lazy loading with API key."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            with patch('src.scanner.services.gemini_service.genai') as mock_genai:
                with patch('src.scanner.services.gemini_service.os.environ', {}):
                    from src.scanner.services.gemini_service import GeminiService
                    
                    service = GeminiService(api_key="test-key")
                    
                    # Mock the model
                    mock_model = Mock()
                    mock_genai.GenerativeModel.return_value = mock_model
                    
                    # Access model property
                    model = service.model
                    
                    # Verify configuration and model creation
                    mock_genai.configure.assert_called_once_with(api_key="test-key")
                    mock_genai.GenerativeModel.assert_called_once_with("gemini-pro-vision")
                    assert model == mock_model
                    assert service._model == mock_model

    def test_model_property_without_api_key(self):
        """Test model property lazy loading without API key."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            with patch('src.scanner.services.gemini_service.genai') as mock_genai:
                from src.scanner.services.gemini_service import GeminiService
                
                service = GeminiService()
                
                # Mock the model
                mock_model = Mock()
                mock_genai.GenerativeModel.return_value = mock_model
                
                # Access model property
                model = service.model
                
                # Should not configure but still create model
                mock_genai.configure.assert_not_called()
                mock_genai.GenerativeModel.assert_called_once_with("gemini-pro-vision")
                assert model == mock_model

    def test_model_property_configuration_error(self):
        """Test model property when configuration fails."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            with patch('src.scanner.services.gemini_service.genai') as mock_genai:
                with patch('src.scanner.services.gemini_service.os.environ', {}):
                    from src.scanner.services.gemini_service import GeminiService
                    
                    service = GeminiService(api_key="invalid-key")
                    
                    # Mock configuration to fail
                    mock_genai.configure.side_effect = Exception("Configuration failed")
                    
                    with pytest.raises(Exception) as exc_info:
                        service.model
                    
                    assert "Configuration failed" in str(exc_info.value)

    def test_model_property_caching(self):
        """Test that model property is cached."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            with patch('src.scanner.services.gemini_service.genai') as mock_genai:
                from src.scanner.services.gemini_service import GeminiService
                
                service = GeminiService(api_key="test-key")
                
                mock_model = Mock()
                mock_genai.GenerativeModel.return_value = mock_model
                
                # Access model multiple times
                model1 = service.model
                model2 = service.model
                
                # Should only create once
                mock_genai.GenerativeModel.assert_called_once()
                assert model1 == model2
                assert model1 == mock_model

    @pytest.mark.asyncio
    async def test_identify_pokemon_card_success(self):
        """Test successful Pokemon card identification."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            with patch('src.scanner.services.gemini_service.genai') as mock_genai:
                with patch('src.scanner.services.gemini_service.Image') as mock_image_class:
                    with patch('src.scanner.services.gemini_service.BytesIO') as mock_bytesio:
                        from src.scanner.services.gemini_service import GeminiService
                        
                        service = GeminiService(api_key="test-key")
                        
                        # Mock PIL Image
                        mock_image = Mock()
                        mock_image.size = (100, 100)
                        mock_image_class.open.return_value = mock_image
                        
                        # Mock successful response
                        mock_candidate = Mock()
                        mock_candidate.finish_reason = Mock()
                        mock_candidate.finish_reason.name = "STOP"
                        mock_candidate.content = Mock()
                        mock_candidate.content.parts = [Mock()]
                        mock_candidate.content.parts[0].text = '{"name": "Pikachu", "set": "Base Set"}'
                        mock_candidate.safety_ratings = []
                        
                        mock_response = Mock()
                        mock_response.candidates = [mock_candidate]
                        mock_response.usage_metadata = Mock()
                        mock_response.usage_metadata.prompt_token_count = 100
                        mock_response.usage_metadata.candidates_token_count = 50
                        
                        mock_model = Mock()
                        mock_model.generate_content = AsyncMock(return_value=mock_response)
                        mock_genai.GenerativeModel.return_value = mock_model
                        
                        # Mock _correct_orientation
                        service._correct_orientation = Mock(return_value=(mock_image, False))
                        
                        result = await service.identify_pokemon_card(b"test_image_data")
                        
                        assert result["success"] is True
                        assert result["response"] == '{"name": "Pikachu", "set": "Base Set"}'
                        assert result["prompt_tokens"] == 100
                        assert result["response_tokens"] == 50
                        assert result["finish_reason"] == "STOP"
                        assert result["truncated"] is False

    @pytest.mark.asyncio
    async def test_identify_pokemon_card_safety_blocked(self):
        """Test response blocked by safety filters."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            with patch('src.scanner.services.gemini_service.genai') as mock_genai:
                with patch('src.scanner.services.gemini_service.Image') as mock_image_class:
                    with patch('src.scanner.services.gemini_service.BytesIO') as mock_bytesio:
                        from src.scanner.services.gemini_service import GeminiService
                        
                        service = GeminiService(api_key="test-key")
                        
                        # Mock PIL Image
                        mock_image = Mock()
                        mock_image.size = (100, 100)
                        mock_image_class.open.return_value = mock_image
                        
                        mock_safety_rating = Mock()
                        mock_safety_rating.category = Mock()
                        mock_safety_rating.category.name = "HARM_CATEGORY_HARASSMENT"
                        mock_safety_rating.probability = Mock()
                        mock_safety_rating.probability.name = "HIGH"
                        
                        mock_candidate = Mock()
                        mock_candidate.finish_reason = Mock()
                        mock_candidate.finish_reason.name = "SAFETY"
                        mock_candidate.safety_ratings = [mock_safety_rating]
                        
                        mock_response = Mock()
                        mock_response.candidates = [mock_candidate]
                        
                        mock_model = Mock()
                        mock_model.generate_content = AsyncMock(return_value=mock_response)
                        mock_genai.GenerativeModel.return_value = mock_model
                        
                        # Mock _correct_orientation
                        service._correct_orientation = Mock(return_value=(mock_image, False))
                        
                        result = await service.identify_pokemon_card(b"test_image_data")
                        
                        assert result["success"] is False
                        assert "safety filters" in result["error"]
                        assert result["finish_reason"] == "SAFETY"

    @pytest.mark.asyncio
    async def test_identify_pokemon_card_no_candidates(self):
        """Test response with no candidates."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            with patch('src.scanner.services.gemini_service.genai') as mock_genai:
                with patch('src.scanner.services.gemini_service.Image') as mock_image_class:
                    with patch('src.scanner.services.gemini_service.BytesIO') as mock_bytesio:
                        from src.scanner.services.gemini_service import GeminiService
                        
                        service = GeminiService(api_key="test-key")
                        
                        # Mock PIL Image
                        mock_image = Mock()
                        mock_image.size = (100, 100)
                        mock_image_class.open.return_value = mock_image
                        
                        mock_response = Mock()
                        mock_response.candidates = []
                        
                        mock_model = Mock()
                        mock_model.generate_content = AsyncMock(return_value=mock_response)
                        mock_genai.GenerativeModel.return_value = mock_model
                        
                        # Mock _correct_orientation
                        service._correct_orientation = Mock(return_value=(mock_image, False))
                        
                        result = await service.identify_pokemon_card(b"test_image_data")
                        
                        assert result["success"] is False
                        assert "No candidates returned" in result["error"]

    @pytest.mark.asyncio
    async def test_identify_pokemon_card_google_api_error(self):
        """Test handling of Google API errors."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            with patch('src.scanner.services.gemini_service.genai') as mock_genai:
                with patch('src.scanner.services.gemini_service.Image') as mock_image_class:
                    with patch('src.scanner.services.gemini_service.BytesIO') as mock_bytesio:
                        with patch('src.scanner.services.gemini_service.GoogleAPIError') as mock_google_error:
                            from src.scanner.services.gemini_service import GeminiService
                            
                            service = GeminiService(api_key="test-key")
                            
                            # Mock PIL Image
                            mock_image = Mock()
                            mock_image.size = (100, 100)
                            mock_image_class.open.return_value = mock_image
                            
                            mock_model = Mock()
                            mock_model.generate_content = AsyncMock(side_effect=mock_google_error("API quota exceeded"))
                            mock_genai.GenerativeModel.return_value = mock_model
                            
                            # Mock _correct_orientation
                            service._correct_orientation = Mock(return_value=(mock_image, False))
                            
                            result = await service.identify_pokemon_card(b"test_image_data")
                            
                            assert result["success"] is False
                            assert "Gemini API error" in result["error"]

    @pytest.mark.asyncio
    async def test_identify_pokemon_card_unexpected_error(self):
        """Test handling of unexpected errors."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            with patch('src.scanner.services.gemini_service.genai') as mock_genai:
                with patch('src.scanner.services.gemini_service.Image') as mock_image_class:
                    with patch('src.scanner.services.gemini_service.BytesIO') as mock_bytesio:
                        from src.scanner.services.gemini_service import GeminiService
                        
                        service = GeminiService(api_key="test-key")
                        
                        # Mock PIL Image
                        mock_image = Mock()
                        mock_image.size = (100, 100)
                        mock_image_class.open.return_value = mock_image
                        
                        mock_model = Mock()
                        mock_model.generate_content = AsyncMock(side_effect=ValueError("Unexpected error"))
                        mock_genai.GenerativeModel.return_value = mock_model
                        
                        # Mock _correct_orientation
                        service._correct_orientation = Mock(return_value=(mock_image, False))
                        
                        result = await service.identify_pokemon_card(b"test_image_data")
                        
                        assert result["success"] is False
                        assert "Unexpected error" in result["error"]

    @pytest.mark.asyncio
    async def test_identify_pokemon_card_with_optimization(self):
        """Test Pokemon card identification with speed optimization."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            with patch('src.scanner.services.gemini_service.genai') as mock_genai:
                with patch('src.scanner.services.gemini_service.Image') as mock_image_class:
                    with patch('src.scanner.services.gemini_service.BytesIO') as mock_bytesio:
                        from src.scanner.services.gemini_service import GeminiService
                        
                        service = GeminiService(api_key="test-key")
                        
                        # Mock PIL Image - large image that should be resized
                        mock_image = Mock()
                        mock_image.size = (1200, 1200)
                        mock_resized_image = Mock()
                        mock_resized_image.size = (800, 800)
                        mock_image.resize.return_value = mock_resized_image
                        mock_image_class.open.return_value = mock_image
                        
                        mock_candidate = Mock()
                        mock_candidate.finish_reason = Mock()
                        mock_candidate.finish_reason.name = "STOP"
                        mock_candidate.content = Mock()
                        mock_candidate.content.parts = [Mock()]
                        mock_candidate.content.parts[0].text = '{"name": "Charizard"}'
                        
                        mock_response = Mock()
                        mock_response.candidates = [mock_candidate]
                        mock_response.usage_metadata = Mock()
                        mock_response.usage_metadata.prompt_token_count = 80
                        mock_response.usage_metadata.candidates_token_count = 30
                        
                        mock_model = Mock()
                        mock_model.generate_content = AsyncMock(return_value=mock_response)
                        mock_genai.GenerativeModel.return_value = mock_model
                        
                        # Mock _correct_orientation
                        service._correct_orientation = Mock(return_value=(mock_image, False))
                        
                        result = await service.identify_pokemon_card(
                            b"test_image_data", 
                            optimize_for_speed=True
                        )
                        
                        assert result["success"] is True
                        assert result["response"] == '{"name": "Charizard"}'
                        # Verify image was resized for speed optimization
                        mock_image.resize.assert_called_once()

    @pytest.mark.asyncio
    async def test_identify_pokemon_card_max_tokens_retry(self):
        """Test MAX_TOKENS handling with retry."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            with patch('src.scanner.services.gemini_service.genai') as mock_genai:
                with patch('src.scanner.services.gemini_service.Image') as mock_image_class:
                    with patch('src.scanner.services.gemini_service.BytesIO') as mock_bytesio:
                        from src.scanner.services.gemini_service import GeminiService
                        
                        service = GeminiService(api_key="test-key")
                        
                        # Mock PIL Image
                        mock_image = Mock()
                        mock_image.size = (100, 100)
                        mock_image_class.open.return_value = mock_image
                        
                        # First response with MAX_TOKENS
                        mock_candidate_first = Mock()
                        mock_candidate_first.finish_reason = Mock()
                        mock_candidate_first.finish_reason.name = "MAX_TOKENS"
                        mock_candidate_first.content = Mock()
                        mock_candidate_first.content.parts = [Mock()]
                        mock_candidate_first.content.parts[0].text = '{"name": "Blastoise"}'
                        
                        mock_response_first = Mock()
                        mock_response_first.candidates = [mock_candidate_first]
                        mock_response_first.usage_metadata = Mock()
                        mock_response_first.usage_metadata.prompt_token_count = 100
                        mock_response_first.usage_metadata.candidates_token_count = 50
                        
                        # Second response successful
                        mock_candidate_second = Mock()
                        mock_candidate_second.finish_reason = Mock()
                        mock_candidate_second.finish_reason.name = "STOP"
                        mock_candidate_second.content = Mock()
                        mock_candidate_second.content.parts = [Mock()]
                        mock_candidate_second.content.parts[0].text = '{"name": "Blastoise", "complete": true}'
                        
                        mock_response_second = Mock()
                        mock_response_second.candidates = [mock_candidate_second]
                        mock_response_second.usage_metadata = Mock()
                        mock_response_second.usage_metadata.prompt_token_count = 120
                        mock_response_second.usage_metadata.candidates_token_count = 80
                        
                        mock_model = Mock()
                        mock_model.generate_content = AsyncMock(side_effect=[mock_response_first, mock_response_second])
                        mock_genai.GenerativeModel.return_value = mock_model
                        
                        # Mock _correct_orientation
                        service._correct_orientation = Mock(return_value=(mock_image, False))
                        
                        result = await service.identify_pokemon_card(b"test_image_data")
                        
                        assert result["success"] is True
                        assert result["response"] == '{"name": "Blastoise", "complete": true}'
                        assert result["finish_reason"] == "STOP"

    @pytest.mark.asyncio
    async def test_identify_pokemon_card_no_usage_metadata(self):
        """Test response without usage metadata."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            with patch('src.scanner.services.gemini_service.genai') as mock_genai:
                with patch('src.scanner.services.gemini_service.Image') as mock_image_class:
                    with patch('src.scanner.services.gemini_service.BytesIO') as mock_bytesio:
                        from src.scanner.services.gemini_service import GeminiService
                        
                        service = GeminiService(api_key="test-key")
                        
                        # Mock PIL Image
                        mock_image = Mock()
                        mock_image.size = (100, 100)
                        mock_image_class.open.return_value = mock_image
                        
                        mock_candidate = Mock()
                        mock_candidate.finish_reason = Mock()
                        mock_candidate.finish_reason.name = "STOP"
                        mock_candidate.content = Mock()
                        mock_candidate.content.parts = [Mock()]
                        mock_candidate.content.parts[0].text = '{"name": "NoMeta"}'
                        
                        mock_response = Mock()
                        mock_response.candidates = [mock_candidate]
                        # No usage_metadata
                        
                        mock_model = Mock()
                        mock_model.generate_content = AsyncMock(return_value=mock_response)
                        mock_genai.GenerativeModel.return_value = mock_model
                        
                        # Mock _correct_orientation
                        service._correct_orientation = Mock(return_value=(mock_image, False))
                        
                        result = await service.identify_pokemon_card(b"test_image_data")
                        
                        assert result["success"] is True
                        assert result["response"] == '{"name": "NoMeta"}'
                        assert result["prompt_tokens"] is None
                        assert result["response_tokens"] is None

    def test_count_tokens_success(self):
        """Test count_tokens method with successful response."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            with patch('src.scanner.services.gemini_service.genai') as mock_genai:
                from src.scanner.services.gemini_service import GeminiService
                
                service = GeminiService(api_key="test-key")
                
                mock_token_count = Mock()
                mock_token_count.total_tokens = 42
                
                mock_model = Mock()
                mock_model.count_tokens.return_value = mock_token_count
                mock_genai.GenerativeModel.return_value = mock_model
                
                result = service.count_tokens("This is a test prompt")
                
                assert result == 42
                mock_model.count_tokens.assert_called_once_with("This is a test prompt")

    def test_count_tokens_error(self):
        """Test count_tokens method with error."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            with patch('src.scanner.services.gemini_service.genai') as mock_genai:
                from src.scanner.services.gemini_service import GeminiService
                
                service = GeminiService(api_key="test-key")
                
                mock_model = Mock()
                mock_model.count_tokens.side_effect = Exception("Token counting failed")
                mock_genai.GenerativeModel.return_value = mock_model
                
                result = service.count_tokens("This is a test prompt")
                
                assert result == 0

    def test_get_optimized_prompt(self):
        """Test _get_optimized_prompt method."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            from src.scanner.services.gemini_service import GeminiService
            
            service = GeminiService(api_key="test-key")
            
            prompt = service._get_optimized_prompt()
            
            assert isinstance(prompt, str)
            assert len(prompt) > 0
            assert "TCG_SEARCH_START" in prompt
            assert "TCG_SEARCH_END" in prompt

    def test_get_generation_config_standard(self):
        """Test _get_generation_config method with standard settings."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            with patch('src.scanner.services.gemini_service.genai') as mock_genai:
                from src.scanner.services.gemini_service import GeminiService
                
                service = GeminiService(api_key="test-key")
                
                # Mock GenerationConfig
                mock_config_obj = Mock()
                mock_genai.types.GenerationConfig.return_value = mock_config_obj
                
                config = service._get_generation_config(retry_unlimited=False)
                
                assert config == mock_config_obj
                mock_genai.types.GenerationConfig.assert_called_once()

    def test_get_generation_config_unlimited(self):
        """Test _get_generation_config method with unlimited tokens."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            with patch('src.scanner.services.gemini_service.genai') as mock_genai:
                from src.scanner.services.gemini_service import GeminiService
                
                service = GeminiService(api_key="test-key")
                
                # Mock GenerationConfig
                mock_config_obj = Mock()
                mock_genai.types.GenerationConfig.return_value = mock_config_obj
                
                config = service._get_generation_config(retry_unlimited=True)
                
                assert config == mock_config_obj
                mock_genai.types.GenerationConfig.assert_called_once()

    @pytest.mark.asyncio
    async def test_identify_pokemon_card_multiple_parts(self):
        """Test response with multiple content parts."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            with patch('src.scanner.services.gemini_service.genai') as mock_genai:
                with patch('src.scanner.services.gemini_service.Image') as mock_image_class:
                    with patch('src.scanner.services.gemini_service.BytesIO') as mock_bytesio:
                        from src.scanner.services.gemini_service import GeminiService
                        
                        service = GeminiService(api_key="test-key")
                        
                        # Mock PIL Image
                        mock_image = Mock()
                        mock_image.size = (100, 100)
                        mock_image_class.open.return_value = mock_image
                        
                        mock_part1 = Mock()
                        mock_part1.text = '{"name": "Multi"'
                        mock_part2 = Mock()
                        mock_part2.text = ', "set": "Base"}'
                        
                        mock_candidate = Mock()
                        mock_candidate.finish_reason = Mock()
                        mock_candidate.finish_reason.name = "STOP"
                        mock_candidate.content = Mock()
                        mock_candidate.content.parts = [mock_part1, mock_part2]
                        
                        mock_response = Mock()
                        mock_response.candidates = [mock_candidate]
                        mock_response.usage_metadata = Mock()
                        mock_response.usage_metadata.prompt_token_count = 40
                        mock_response.usage_metadata.candidates_token_count = 20
                        
                        mock_model = Mock()
                        mock_model.generate_content = AsyncMock(return_value=mock_response)
                        mock_genai.GenerativeModel.return_value = mock_model
                        
                        # Mock _correct_orientation
                        service._correct_orientation = Mock(return_value=(mock_image, False))
                        
                        result = await service.identify_pokemon_card(b"test_image_data")
                        
                        assert result["success"] is True
                        assert result["response"] == '{"name": "Multi", "set": "Base"}'

    @pytest.mark.asyncio
    async def test_identify_pokemon_card_no_valid_content(self):
        """Test response with no valid content."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            with patch('src.scanner.services.gemini_service.genai') as mock_genai:
                with patch('src.scanner.services.gemini_service.Image') as mock_image_class:
                    with patch('src.scanner.services.gemini_service.BytesIO') as mock_bytesio:
                        from src.scanner.services.gemini_service import GeminiService
                        
                        service = GeminiService(api_key="test-key")
                        
                        # Mock PIL Image
                        mock_image = Mock()
                        mock_image.size = (100, 100)
                        mock_image_class.open.return_value = mock_image
                        
                        mock_candidate = Mock()
                        mock_candidate.finish_reason = Mock()
                        mock_candidate.finish_reason.name = "OTHER"
                        mock_candidate.content = None
                        
                        mock_response = Mock()
                        mock_response.candidates = [mock_candidate]
                        
                        mock_model = Mock()
                        mock_model.generate_content = AsyncMock(return_value=mock_response)
                        mock_genai.GenerativeModel.return_value = mock_model
                        
                        # Mock _correct_orientation
                        service._correct_orientation = Mock(return_value=(mock_image, False))
                        
                        result = await service.identify_pokemon_card(b"test_image_data")
                        
                        assert result["success"] is False
                        assert "No valid content returned" in result["error"]
                        assert result["finish_reason"] == "OTHER"

    @pytest.mark.asyncio
    async def test_identify_pokemon_card_with_retry_unlimited(self):
        """Test MAX_TOKENS with unlimited retry."""
        with patch('src.scanner.services.gemini_service.config') as mock_config:
            mock_config.gemini_model = "gemini-pro-vision"
            mock_config.gemini_temperature = 0.1
            mock_config.gemini_max_tokens = 150
            mock_config.image_max_dimension = 1024
            
            with patch('src.scanner.services.gemini_service.genai') as mock_genai:
                with patch('src.scanner.services.gemini_service.Image') as mock_image_class:
                    with patch('src.scanner.services.gemini_service.BytesIO') as mock_bytesio:
                        from src.scanner.services.gemini_service import GeminiService
                        
                        service = GeminiService(api_key="test-key")
                        
                        # Mock PIL Image
                        mock_image = Mock()
                        mock_image.size = (100, 100)
                        mock_image_class.open.return_value = mock_image
                        
                        mock_candidate = Mock()
                        mock_candidate.finish_reason = Mock()
                        mock_candidate.finish_reason.name = "MAX_TOKENS"
                        mock_candidate.content = Mock()
                        mock_candidate.content.parts = [Mock()]
                        mock_candidate.content.parts[0].text = '{"name": "Venusaur"}'
                        
                        mock_response = Mock()
                        mock_response.candidates = [mock_candidate]
                        mock_response.usage_metadata = Mock()
                        mock_response.usage_metadata.prompt_token_count = 150
                        mock_response.usage_metadata.candidates_token_count = 100
                        
                        mock_model = Mock()
                        mock_model.generate_content = AsyncMock(return_value=mock_response)
                        mock_genai.GenerativeModel.return_value = mock_model
                        
                        # Mock _correct_orientation
                        service._correct_orientation = Mock(return_value=(mock_image, False))
                        
                        result = await service.identify_pokemon_card(
                            b"test_image_data", 
                            retry_unlimited=True
                        )
                        
                        assert result["success"] is True
                        assert result["response"] == '{"name": "Venusaur"}\n\n[Response truncated due to length limit]'
                        assert result["truncated"] is True