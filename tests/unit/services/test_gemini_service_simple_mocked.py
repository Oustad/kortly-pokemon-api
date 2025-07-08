"""Simple mocked tests for gemini_service.py focusing on testable functions."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any


class TestGeminiServiceSimpleMocked:
    """Test GeminiService with simple mocking approach."""

    def test_initialization_with_api_key(self):
        """Test service initialization with API key."""
        # Mock all the external dependencies at the module level
        with patch.dict('sys.modules', {
            'google.generativeai': Mock(),
            'google.api_core.exceptions': Mock(),
        }):
            from src.scanner.services.gemini_service import GeminiService
            
            service = GeminiService(api_key="test-key")
            assert service._api_key == "test-key"
            assert service._model is None

    def test_initialization_without_api_key(self):
        """Test service initialization without API key."""
        with patch.dict('sys.modules', {
            'google.generativeai': Mock(),
            'google.api_core.exceptions': Mock(),
        }):
            from src.scanner.services.gemini_service import GeminiService
            
            service = GeminiService()
            assert service._api_key is None
            assert service._model is None

    def test_initialization_with_whitespace_api_key(self):
        """Test service initialization with whitespace in API key."""
        with patch.dict('sys.modules', {
            'google.generativeai': Mock(),
            'google.api_core.exceptions': Mock(),
        }):
            from src.scanner.services.gemini_service import GeminiService
            
            service = GeminiService(api_key="  test-key  ")
            assert service._api_key == "test-key"

    def test_initialization_with_empty_api_key(self):
        """Test service initialization with empty API key."""
        with patch.dict('sys.modules', {
            'google.generativeai': Mock(),
            'google.api_core.exceptions': Mock(),
        }):
            from src.scanner.services.gemini_service import GeminiService
            
            service = GeminiService(api_key="")
            assert service._api_key == ""

    def test_get_optimized_prompt(self):
        """Test _get_optimized_prompt method."""
        with patch.dict('sys.modules', {
            'google.generativeai': Mock(),
            'google.api_core.exceptions': Mock(),
        }):
            from src.scanner.services.gemini_service import GeminiService
            
            service = GeminiService(api_key="test-key")
            
            prompt = service._get_optimized_prompt()
            
            assert isinstance(prompt, str)
            assert len(prompt) > 0
            assert "TCG_SEARCH_START" in prompt
            assert "TCG_SEARCH_END" in prompt
            assert "CARD TYPE DETECTION" in prompt
            assert "authenticity_score" in prompt
            assert "readability_score" in prompt
            assert "pokemon_front" in prompt
            assert "VISUAL ANALYSIS" in prompt

    def test_get_generation_config_standard(self):
        """Test _get_generation_config method with standard settings."""
        mock_genai = Mock()
        mock_config_obj = Mock()
        mock_genai.types.GenerationConfig.return_value = mock_config_obj
        
        with patch.dict('sys.modules', {
            'google.generativeai': mock_genai,
            'google.api_core.exceptions': Mock(),
        }):
            from src.scanner.services.gemini_service import GeminiService
            
            service = GeminiService(api_key="test-key")
            
            config = service._get_generation_config(retry_unlimited=False)
            
            assert config == mock_config_obj
            mock_genai.types.GenerationConfig.assert_called_once()

    def test_get_generation_config_unlimited(self):
        """Test _get_generation_config method with unlimited tokens."""
        mock_genai = Mock()
        mock_config_obj = Mock()
        mock_genai.types.GenerationConfig.return_value = mock_config_obj
        
        with patch.dict('sys.modules', {
            'google.generativeai': mock_genai,
            'google.api_core.exceptions': Mock(),
        }):
            from src.scanner.services.gemini_service import GeminiService
            
            service = GeminiService(api_key="test-key")
            
            config = service._get_generation_config(retry_unlimited=True)
            
            assert config == mock_config_obj
            mock_genai.types.GenerationConfig.assert_called_once()

    def test_model_property_with_api_key(self):
        """Test model property lazy loading with API key."""
        mock_genai = Mock()
        mock_model = Mock()
        mock_genai.GenerativeModel.return_value = mock_model
        
        with patch.dict('sys.modules', {
            'google.generativeai': mock_genai,
            'google.api_core.exceptions': Mock(),
        }):
            with patch('src.scanner.services.gemini_service.os.environ', {}):
                from src.scanner.services.gemini_service import GeminiService
                
                service = GeminiService(api_key="test-key")
                
                # Access model property
                model = service.model
                
                # Verify configuration and model creation
                mock_genai.configure.assert_called_once_with(api_key="test-key")
                mock_genai.GenerativeModel.assert_called_once()
                assert model == mock_model
                assert service._model == mock_model

    def test_model_property_without_api_key(self):
        """Test model property lazy loading without API key."""
        mock_genai = Mock()
        mock_model = Mock()
        mock_genai.GenerativeModel.return_value = mock_model
        
        with patch.dict('sys.modules', {
            'google.generativeai': mock_genai,
            'google.api_core.exceptions': Mock(),
        }):
            from src.scanner.services.gemini_service import GeminiService
            
            service = GeminiService()
            
            # Access model property
            model = service.model
            
            # Should not configure but still create model
            mock_genai.configure.assert_not_called()
            mock_genai.GenerativeModel.assert_called_once()
            assert model == mock_model

    def test_model_property_configuration_error(self):
        """Test model property when configuration fails."""
        mock_genai = Mock()
        mock_genai.configure.side_effect = Exception("Configuration failed")
        
        with patch.dict('sys.modules', {
            'google.generativeai': mock_genai,
            'google.api_core.exceptions': Mock(),
        }):
            with patch('src.scanner.services.gemini_service.os.environ', {}):
                from src.scanner.services.gemini_service import GeminiService
                
                service = GeminiService(api_key="invalid-key")
                
                with pytest.raises(Exception) as exc_info:
                    service.model
                
                assert "Configuration failed" in str(exc_info.value)

    def test_model_property_caching(self):
        """Test that model property is cached."""
        mock_genai = Mock()
        mock_model = Mock()
        mock_genai.GenerativeModel.return_value = mock_model
        
        with patch.dict('sys.modules', {
            'google.generativeai': mock_genai,
            'google.api_core.exceptions': Mock(),
        }):
            from src.scanner.services.gemini_service import GeminiService
            
            service = GeminiService(api_key="test-key")
            
            # Access model multiple times
            model1 = service.model
            model2 = service.model
            
            # Should only create once
            mock_genai.GenerativeModel.assert_called_once()
            assert model1 == model2
            assert model1 == mock_model

    def test_count_tokens_success(self):
        """Test count_tokens method with successful response."""
        mock_genai = Mock()
        mock_model = Mock()
        mock_token_count = Mock()
        mock_token_count.total_tokens = 42
        mock_model.count_tokens.return_value = mock_token_count
        mock_genai.GenerativeModel.return_value = mock_model
        
        with patch.dict('sys.modules', {
            'google.generativeai': mock_genai,
            'google.api_core.exceptions': Mock(),
        }):
            from src.scanner.services.gemini_service import GeminiService
            
            service = GeminiService(api_key="test-key")
            
            result = service.count_tokens("This is a test prompt")
            
            assert result == 42
            mock_model.count_tokens.assert_called_once_with("This is a test prompt")

    def test_count_tokens_error(self):
        """Test count_tokens method with error."""
        mock_genai = Mock()
        mock_model = Mock()
        mock_model.count_tokens.side_effect = Exception("Token counting failed")
        mock_genai.GenerativeModel.return_value = mock_model
        
        with patch.dict('sys.modules', {
            'google.generativeai': mock_genai,
            'google.api_core.exceptions': Mock(),
        }):
            from src.scanner.services.gemini_service import GeminiService
            
            service = GeminiService(api_key="test-key")
            
            result = service.count_tokens("This is a test prompt")
            
            assert result == 0

    def test_basic_functionality_works(self):
        """Test that basic functionality works without async calls."""
        with patch.dict('sys.modules', {
            'google.generativeai': Mock(),
            'google.api_core.exceptions': Mock(),
        }):
            from src.scanner.services.gemini_service import GeminiService
            
            service = GeminiService(api_key="test-key")
            
            # Test that the basic methods work
            assert service._api_key == "test-key"
            
            # Test the prompt generation
            prompt = service._get_optimized_prompt()
            assert "TCG_SEARCH_START" in prompt
            assert "authenticity_score" in prompt

    def test_prompt_content_comprehensive(self):
        """Test that the prompt contains comprehensive Pokemon card analysis content."""
        with patch.dict('sys.modules', {
            'google.generativeai': Mock(),
            'google.api_core.exceptions': Mock(),
        }):
            from src.scanner.services.gemini_service import GeminiService
            
            service = GeminiService(api_key="test-key")
            
            prompt = service._get_optimized_prompt()
            
            # Test comprehensive content
            assert "CARD TYPE DETECTION" in prompt
            assert "VISUAL ANALYSIS" in prompt
            assert "AUTHENTICITY ASSESSMENT" in prompt
            assert "READABILITY ASSESSMENT" in prompt
            assert "UNCERTAINTY AND CONFIDENCE HANDLING" in prompt
            assert "CARD NUMBER READING" in prompt
            assert "Hidden Fates Shiny Vault" in prompt
            assert "BREAK CARD DETECTION" in prompt
            assert "PRIME CARD DETECTION" in prompt
            
            # Test specific card type options
            assert "pokemon_front" in prompt
            assert "pokemon_back" in prompt
            assert "non_pokemon" in prompt
            
            # Test set name mappings mentioned
            assert "XY BREAKpoint" in prompt
            assert "HeartGold & SoulSilver" in prompt
            
            # Test error handling instructions
            assert "If you cannot clearly read" in prompt
            assert "indicate uncertainty" in prompt

    def test_generation_config_parameters(self):
        """Test generation config with different parameters."""
        mock_genai = Mock()
        mock_config_obj = Mock()
        mock_genai.types.GenerationConfig.return_value = mock_config_obj
        
        with patch.dict('sys.modules', {
            'google.generativeai': mock_genai,
            'google.api_core.exceptions': Mock(),
        }):
            from src.scanner.services.gemini_service import GeminiService
            
            service = GeminiService(api_key="test-key")
            
            # Test standard config
            config1 = service._get_generation_config(retry_unlimited=False)
            assert config1 == mock_config_obj
            
            # Test unlimited config
            config2 = service._get_generation_config(retry_unlimited=True)
            assert config2 == mock_config_obj
            
            # Should be called twice
            assert mock_genai.types.GenerationConfig.call_count == 2

    def test_service_attributes_after_initialization(self):
        """Test service attributes are properly set after initialization."""
        with patch.dict('sys.modules', {
            'google.generativeai': Mock(),
            'google.api_core.exceptions': Mock(),
        }):
            from src.scanner.services.gemini_service import GeminiService
            
            # Test with API key
            service1 = GeminiService(api_key="test-key")
            assert service1._api_key == "test-key"
            assert service1._model is None
            
            # Test without API key
            service2 = GeminiService()
            assert service2._api_key is None
            assert service2._model is None
            
            # Test with None API key
            service3 = GeminiService(api_key=None)
            assert service3._api_key is None
            assert service3._model is None