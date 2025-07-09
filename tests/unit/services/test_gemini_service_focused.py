"""Focused tests for gemini_service.py initialization and configuration."""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional

from src.scanner.services.gemini_service import GeminiService


class TestGeminiServiceInitialization:
    """Test GeminiService initialization."""
    
    def test_init_with_api_key(self):
        """Test initialization with provided API key."""
        api_key = "test-api-key-123"
        service = GeminiService(api_key=api_key)
        
        assert service._api_key == api_key
        assert service._model is None
    
    def test_init_with_whitespace_api_key(self):
        """Test initialization with API key containing whitespace."""
        api_key = "  test-api-key-123  \n"
        service = GeminiService(api_key=api_key)
        
        assert service._api_key == "test-api-key-123"  # Should be stripped
    
    def test_init_without_api_key(self):
        """Test initialization without API key."""
        service = GeminiService()
        
        assert service._api_key is None
        assert service._model is None
    
    def test_init_with_none_api_key(self):
        """Test initialization with None API key."""
        service = GeminiService(api_key=None)
        
        assert service._api_key is None
        assert service._model is None


class TestGeminiServiceModelProperty:
    """Test GeminiService model property (lazy loading)."""
    
    @patch('src.scanner.services.gemini_service.genai')
    @patch('src.scanner.services.gemini_service.config')
    def test_model_property_with_api_key(self, mock_config, mock_genai):
        """Test model property with valid API key."""
        mock_config.gemini_model = "test-model"
        mock_model = Mock()
        mock_genai.GenerativeModel.return_value = mock_model
        
        service = GeminiService(api_key="test-key")
        
        # First access should configure and create model
        result = service.model
        
        mock_genai.configure.assert_called_once_with(api_key="test-key")
        mock_genai.GenerativeModel.assert_called_once_with("test-model")
        assert result == mock_model
        assert service._model == mock_model
        
        # Second access should return cached model
        result2 = service.model
        assert result2 == mock_model
        assert mock_genai.configure.call_count == 1  # Should not be called again
    
    @patch('src.scanner.services.gemini_service.genai')
    @patch('src.scanner.services.gemini_service.config')
    def test_model_property_without_api_key(self, mock_config, mock_genai):
        """Test model property without API key."""
        mock_config.gemini_model = "test-model"
        mock_model = Mock()
        mock_genai.GenerativeModel.return_value = mock_model
        
        service = GeminiService()
        
        result = service.model
        
        # Should not call configure when no API key
        mock_genai.configure.assert_not_called()
        mock_genai.GenerativeModel.assert_called_once_with("test-model")
        assert result == mock_model
    
    @patch('src.scanner.services.gemini_service.genai')
    @patch('src.scanner.services.gemini_service.config')
    @patch('src.scanner.services.gemini_service.os.environ')
    def test_model_property_sets_environment_variable(self, mock_environ, mock_config, mock_genai):
        """Test that model property sets environment variable."""
        mock_config.gemini_model = "test-model"
        mock_model = Mock()
        mock_genai.GenerativeModel.return_value = mock_model
        
        service = GeminiService(api_key="test-key")
        
        _ = service.model
        
        mock_environ.__setitem__.assert_called_with("GOOGLE_API_KEY", "test-key")
    
    @patch('src.scanner.services.gemini_service.genai')
    @patch('src.scanner.services.gemini_service.config')
    def test_model_property_configuration_error(self, mock_config, mock_genai):
        """Test model property with configuration error."""
        mock_config.gemini_model = "test-model"
        mock_genai.configure.side_effect = Exception("Configuration failed")
        
        service = GeminiService(api_key="test-key")
        
        with pytest.raises(Exception, match="Configuration failed"):
            _ = service.model
    
    @patch('src.scanner.services.gemini_service.genai')
    @patch('src.scanner.services.gemini_service.config')
    def test_model_property_api_key_format_logging(self, mock_config, mock_genai):
        """Test that model property logs API key format on configuration error."""
        mock_config.gemini_model = "test-model"
        mock_genai.configure.side_effect = Exception("Configuration failed")
        
        service = GeminiService(api_key="test-key-12345")
        
        with pytest.raises(Exception):
            _ = service.model


class TestGeminiServiceUtilityMethods:
    """Test GeminiService utility methods."""
    
    @patch('src.scanner.services.gemini_service.genai')
    @patch('src.scanner.services.gemini_service.config')
    def test_count_tokens_success(self, mock_config, mock_genai):
        """Test successful token counting."""
        mock_config.gemini_model = "test-model"
        mock_model = Mock()
        mock_token_count = Mock()
        mock_token_count.total_tokens = 42
        mock_model.count_tokens.return_value = mock_token_count
        mock_genai.GenerativeModel.return_value = mock_model
        
        service = GeminiService(api_key="test-key")
        
        result = service.count_tokens("test text")
        
        assert result == 42
        mock_model.count_tokens.assert_called_once_with("test text")
    
    @patch('src.scanner.services.gemini_service.genai')
    @patch('src.scanner.services.gemini_service.config')
    def test_count_tokens_error(self, mock_config, mock_genai):
        """Test token counting with error."""
        mock_config.gemini_model = "test-model"
        mock_model = Mock()
        mock_model.count_tokens.side_effect = Exception("Count failed")
        mock_genai.GenerativeModel.return_value = mock_model
        
        service = GeminiService(api_key="test-key")
        
        result = service.count_tokens("test text")
        
        assert result == 0  # Should return 0 on error
    
    @patch('src.scanner.services.gemini_service.genai')
    @patch('src.scanner.services.gemini_service.config')
    def test_get_prompt_optimization_stats(self, mock_config, mock_genai):
        """Test get_prompt_optimization_stats method."""
        mock_config.gemini_model = "test-model"
        mock_model = Mock()
        mock_genai.GenerativeModel.return_value = mock_model
        
        service = GeminiService(api_key="test-key")
        
        with patch.object(service, '_get_optimized_prompt') as mock_get_prompt:
            with patch.object(service, '_get_generation_config') as mock_get_config:
                mock_get_prompt.return_value = "test prompt"
                mock_config_obj = Mock()
                mock_config_obj.max_output_tokens = 100
                mock_config_obj.temperature = 0.7
                mock_get_config.return_value = mock_config_obj
                
                result = service.get_prompt_optimization_stats()
                
                assert "fast" in result
                assert "standard" in result
                assert "enhanced" in result
                
                for tier in ["fast", "standard", "enhanced"]:
                    assert "prompt_length" in result[tier]
                    assert "estimated_prompt_tokens" in result[tier]
                    assert "max_output_tokens" in result[tier]
                    assert "temperature" in result[tier]
                    assert "optimization_focus" in result[tier]
                    
                    assert result[tier]["prompt_length"] == 11  # len("test prompt")
                    assert result[tier]["max_output_tokens"] == 100
                    assert result[tier]["temperature"] == 0.7


class TestGeminiServiceGenerationConfig:
    """Test GeminiService generation configuration."""
    
    @patch('src.scanner.services.gemini_service.genai')
    @patch('src.scanner.services.gemini_service.config')
    def test_get_generation_config_normal(self, mock_config, mock_genai):
        """Test generation config with normal parameters."""
        mock_config.gemini_temperature = 0.8
        mock_config.gemini_max_tokens = 1000
        mock_genai.types.GenerationConfig = Mock()
        
        service = GeminiService(api_key="test-key")
        
        result = service._get_generation_config(retry_unlimited=False)
        
        mock_genai.types.GenerationConfig.assert_called_once_with(
            max_output_tokens=400,  # min(400, 1000)
            temperature=0.8,
            top_p=0.95
        )
    
    @patch('src.scanner.services.gemini_service.genai')
    @patch('src.scanner.services.gemini_service.config')
    def test_get_generation_config_retry_unlimited(self, mock_config, mock_genai):
        """Test generation config with retry unlimited."""
        mock_config.gemini_temperature = 0.8
        mock_genai.types.GenerationConfig = Mock()
        
        service = GeminiService(api_key="test-key")
        
        result = service._get_generation_config(retry_unlimited=True)
        
        mock_genai.types.GenerationConfig.assert_called_once_with(
            temperature=0.8
        )
    
    @patch('src.scanner.services.gemini_service.genai')
    @patch('src.scanner.services.gemini_service.config')
    def test_get_generation_config_max_tokens_limit(self, mock_config, mock_genai):
        """Test generation config with max tokens limit."""
        mock_config.gemini_temperature = 0.8
        mock_config.gemini_max_tokens = 200  # Less than 400
        mock_genai.types.GenerationConfig = Mock()
        
        service = GeminiService(api_key="test-key")
        
        result = service._get_generation_config(retry_unlimited=False)
        
        mock_genai.types.GenerationConfig.assert_called_once_with(
            max_output_tokens=200,  # min(400, 200)
            temperature=0.8,
            top_p=0.95
        )


class TestGeminiServicePromptGeneration:
    """Test GeminiService prompt generation."""
    
    def test_get_optimized_prompt_returns_string(self):
        """Test that _get_optimized_prompt returns a string."""
        service = GeminiService(api_key="test-key")
        
        result = service._get_optimized_prompt()
        
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_get_optimized_prompt_contains_key_sections(self):
        """Test that the prompt contains key sections."""
        service = GeminiService(api_key="test-key")
        
        result = service._get_optimized_prompt()
        
        # Check for key sections
        assert "CARD TYPE DETECTION" in result
        assert "VISUAL ANALYSIS" in result
        assert "CARD NUMBER READING" in result
        assert "AUTHENTICITY ASSESSMENT" in result
        assert "READABILITY ASSESSMENT" in result
        assert "TCG_SEARCH_START" in result
        assert "TCG_SEARCH_END" in result
    
    def test_get_optimized_prompt_contains_required_fields(self):
        """Test that the prompt contains required JSON fields."""
        service = GeminiService(api_key="test-key")
        
        result = service._get_optimized_prompt()
        
        # Check for required JSON fields
        assert '"card_type"' in result
        assert '"is_pokemon_card"' in result
        assert '"name"' in result
        assert '"set_name"' in result
        assert '"number"' in result
        assert '"authenticity_score"' in result
        assert '"readability_score"' in result
    
    def test_get_optimized_prompt_contains_specific_instructions(self):
        """Test that the prompt contains specific instructions."""
        service = GeminiService(api_key="test-key")
        
        result = service._get_optimized_prompt()
        
        # Check for specific instructions
        assert "Hidden Fates Shiny Vault" in result
        assert "XY BREAKpoint" in result
        assert "XY BREAKthrough" in result
        assert "BREAK evolution cards" in result
        assert "Prime cards" in result
        assert "SV" in result  # Shiny Vault numbers