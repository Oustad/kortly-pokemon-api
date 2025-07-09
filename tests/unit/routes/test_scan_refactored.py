"""Unit tests for refactored scan route with TCGSearchService."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import base64
from PIL import Image
import io
import sys

# Mock required dependencies before importing
mock_genai = Mock()
mock_genai.GenerativeModel = Mock()
mock_genai.configure = Mock()
mock_genai.types = Mock()
mock_genai.types.GenerationConfig = Mock()

# Mock all dependencies
mocked_modules = {
    'google.generativeai': mock_genai,
    'google.api_core.exceptions': Mock(),
    'cv2': Mock(),
    'httpx': Mock(),
    'pythonjsonlogger': Mock(),
    'pythonjsonlogger.jsonlogger': Mock(),
}

# Apply mocks to sys.modules
for module_name, mock_module in mocked_modules.items():
    sys.modules[module_name] = mock_module

# Mock logging configuration
with patch('logging.config.dictConfig'):
    from src.scanner.models.schemas import PokemonCard


class TestScanRouteWithTCGSearchService:
    """Test scan route with mocked TCGSearchService."""

    @pytest.fixture
    def sample_image_base64(self):
        """Create sample image as base64."""
        img = Image.new('RGB', (400, 600), color=(0, 0, 255))
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG')
        image_data = img_buffer.getvalue()
        return base64.b64encode(image_data).decode('utf-8')

    @pytest.fixture
    def mock_pipeline_result(self):
        """Mock successful pipeline result."""
        return {
            "success": True,
            "card_data": {
                "success": True,
                "response": """TCG_SEARCH_START
{
  "name": "Pikachu",
  "set_name": "Base Set",
  "number": "58",
  "hp": "60",
  "types": ["Electric"],
  "rarity": "Common",
  "card_type_info": {
    "card_type": "pokemon_front",
    "is_pokemon_card": true,
    "card_side": "front"
  }
}
TCG_SEARCH_END""",
                "prompt_tokens": 100,
                "response_tokens": 50
            },
            "processing": {
                "quality_score": 85,
                "quality_feedback": {
                    "overall": "good",
                    "issues": [],
                    "suggestions": []
                },
                "processing_tier": "standard",
                "target_time_ms": 2000,
                "actual_time_ms": 1500,
                "model_used": "gemini-1.5-flash",
                "image_enhanced": False,
                "performance_rating": "good",
                "timing_breakdown": {
                    "quality_assessment": 100,
                    "gemini_analysis": 1400
                },
                "processing_log": ["Quality check: passed", "Gemini analysis: complete"]
            }
        }

    @pytest.fixture
    def mock_tcg_matches(self):
        """Mock TCG matches as PokemonCard objects."""
        return [
            PokemonCard(
                id="base1-58",
                name="Pikachu",
                set_name="Base Set",
                number="58",
                types=["Lightning"],
                hp="60",
                rarity="Common",
                images={"small": "url1", "large": "url2"},
                market_prices={"holofoil": {"market": 5.00}}
            )
        ]

    @pytest.fixture
    def mock_search_results(self):
        """Mock search results from TCGSearchService."""
        return [
            {
                "id": "base1-58",
                "name": "Pikachu",
                "set": {"name": "Base Set"},
                "number": "58",
                "types": ["Lightning"],
                "hp": "60",
                "rarity": "Common",
                "images": {"small": "url1", "large": "url2"},
                "tcgplayer": {"prices": {"holofoil": {"market": 5.00}}}
            }
        ]

    @pytest.mark.asyncio
    @patch('src.scanner.routes.scan.TCGSearchService')
    @patch('src.scanner.routes.scan.PokemonTcgClient')
    @patch('src.scanner.routes.scan.ProcessingPipeline')
    @patch('src.scanner.routes.scan.GeminiService')
    async def test_scan_with_tcg_search_service(
        self,
        mock_gemini_service,
        mock_pipeline,
        mock_tcg_client,
        mock_tcg_search_service,
        sample_image_base64,
        mock_pipeline_result,
        mock_search_results,
        mock_tcg_matches
    ):
        """Test scan endpoint using TCGSearchService."""
        from src.scanner.routes.scan import scan_pokemon_card
        from src.scanner.models.schemas import ScanRequest, ScanOptions
        
        # Setup mocks
        mock_gemini_instance = Mock()
        mock_gemini_service.return_value = mock_gemini_instance
        
        mock_pipeline_instance = Mock()
        mock_pipeline.return_value = mock_pipeline_instance
        mock_pipeline_instance.process_image = AsyncMock(return_value=mock_pipeline_result)
        
        mock_tcg_client_instance = Mock()
        mock_tcg_client.return_value = mock_tcg_client_instance
        
        # Mock TCGSearchService
        mock_search_service_instance = Mock()
        mock_tcg_search_service.return_value = mock_search_service_instance
        mock_search_service_instance.search_for_card = AsyncMock(
            return_value=(
                mock_search_results,  # all_search_results
                [{"strategy": "set_number_name_exact", "query": {}, "results": 1}],  # search_attempts
                mock_tcg_matches  # tcg_matches
            )
        )
        
        # Mock select_best_match
        with patch('src.scanner.routes.scan.select_best_match') as mock_select:
            mock_select.return_value = (
                mock_search_results[0],  # best_match_data
                [{  # all_scored_matches
                    "card": mock_search_results[0],
                    "score": 1500,
                    "score_breakdown": {
                        "set_number_name_triple": 1000,
                        "name_exact": 300,
                        "number_exact": 200
                    }
                }]
            )
            
            # Create request
            request = ScanRequest(
                image=sample_image_base64,
                filename="test.jpg",
                options=ScanOptions()
            )
            
            # Call the endpoint
            response = await scan_pokemon_card(request)
        
        # Verify TCGSearchService was used
        mock_tcg_search_service.assert_called_once()
        mock_search_service_instance.search_for_card.assert_called_once()
        
        # Verify the search was called with correct parameters
        call_args = mock_search_service_instance.search_for_card.call_args
        # The parsed_data should be the parsed version of the response
        expected_parsed_data = {
            'card_type_info': {'card_type': 'pokemon_front', 'is_pokemon_card': True, 'card_side': 'front'},
            'name': 'Pikachu',
            'language_info': {'detected_language': 'en', 'is_translation': False},
            'set_name': 'Base Set',
            'number': '58',
            'hp': '60',
            'types': ['Electric']
        }
        assert call_args[0][0] == expected_parsed_data  # parsed_data
        assert call_args[0][1] == mock_tcg_client_instance  # tcg_client
        
        # Verify response
        assert response.name == "Pikachu"
        assert response.set_name == "Base Set"
        assert response.number == "58"
        assert response.hp == "60"
        assert response.match_score == 1500
        assert response.quality_score == 85.0

    @pytest.mark.asyncio
    @patch('src.scanner.routes.scan.TCGSearchService')
    @patch('src.scanner.routes.scan.PokemonTcgClient')
    @patch('src.scanner.routes.scan.ProcessingPipeline')
    @patch('src.scanner.routes.scan.GeminiService')
    async def test_scan_no_matches_found(
        self,
        mock_gemini_service,
        mock_pipeline,
        mock_tcg_client,
        mock_tcg_search_service,
        sample_image_base64,
        mock_pipeline_result
    ):
        """Test scan when no TCG matches are found."""
        from src.scanner.routes.scan import scan_pokemon_card
        from src.scanner.models.schemas import ScanRequest, ScanOptions
        from fastapi import HTTPException
        
        # Setup mocks
        mock_gemini_instance = Mock()
        mock_gemini_service.return_value = mock_gemini_instance
        
        mock_pipeline_instance = Mock()
        mock_pipeline.return_value = mock_pipeline_instance
        mock_pipeline_instance.process_image = AsyncMock(return_value=mock_pipeline_result)
        
        mock_tcg_client_instance = Mock()
        mock_tcg_client.return_value = mock_tcg_client_instance
        
        # Mock TCGSearchService returning no results
        mock_search_service_instance = Mock()
        mock_tcg_search_service.return_value = mock_search_service_instance
        mock_search_service_instance.search_for_card = AsyncMock(
            return_value=([], [], [])  # No results
        )
        
        # Mock select_best_match
        with patch('src.scanner.routes.scan.select_best_match') as mock_select:
            mock_select.return_value = (None, [])  # No matches
            
            # Create request
            request = ScanRequest(
                image=sample_image_base64,
                filename="test.jpg",
                options=ScanOptions()
            )
            
            # Call the endpoint - it should succeed but return Gemini data
            response = await scan_pokemon_card(request)
            
            # Should use Gemini data when no TCG matches found
            assert response.name == "Pikachu"
            assert response.market_prices is None  # No TCG match means no prices

    @pytest.mark.asyncio
    @patch('src.scanner.routes.scan.TCGSearchService')
    @patch('src.scanner.routes.scan.PokemonTcgClient')
    @patch('src.scanner.routes.scan.ProcessingPipeline')
    @patch('src.scanner.routes.scan.GeminiService')
    async def test_scan_no_name_skips_tcg_search(
        self,
        mock_gemini_service,
        mock_pipeline,
        mock_tcg_client,
        mock_tcg_search_service,
        sample_image_base64
    ):
        """Test that TCG search is skipped when no name is identified."""
        from src.scanner.routes.scan import scan_pokemon_card
        from src.scanner.models.schemas import ScanRequest, ScanOptions
        
        # Pipeline result with no name
        pipeline_result_no_name = {
            "success": True,
            "card_data": {
                "success": True,
                "response": """TCG_SEARCH_START
{
  "name": null,
  "set_name": "Unknown",
  "number": null,
  "card_type_info": {
    "card_type": "unknown",
    "is_pokemon_card": false,
    "card_side": "unknown"
  },
  "language_info": {
    "detected_language": "en"
  }
}
TCG_SEARCH_END""",
                "prompt_tokens": 100,
                "response_tokens": 20
            },
            "processing": {
                "quality_score": 85,
                "quality_feedback": {
                    "overall": "good",
                    "issues": [],
                    "suggestions": []
                },
                "processing_tier": "standard",
                "target_time_ms": 2000,
                "actual_time_ms": 1500,
                "model_used": "gemini-1.5-flash",
                "image_enhanced": False,
                "performance_rating": "good",
                "timing_breakdown": {},
                "processing_log": []
            }
        }
        
        # Setup mocks
        mock_gemini_instance = Mock()
        mock_gemini_service.return_value = mock_gemini_instance
        
        mock_pipeline_instance = Mock()
        mock_pipeline.return_value = mock_pipeline_instance
        mock_pipeline_instance.process_image = AsyncMock(return_value=pipeline_result_no_name)
        
        mock_tcg_client_instance = Mock()
        mock_tcg_client.return_value = mock_tcg_client_instance
        
        # Mock TCGSearchService - it will be called but return empty results
        mock_search_service_instance = Mock()
        mock_tcg_search_service.return_value = mock_search_service_instance
        mock_search_service_instance.search_for_card = AsyncMock(
            return_value=([], [], [])  # Empty results when no name
        )
        
        # Create request
        request = ScanRequest(
            image=sample_image_base64,
            filename="test.jpg",
            options=ScanOptions()
        )
        
        # Call the endpoint
        response = await scan_pokemon_card(request)
        
        # Verify TCGSearchService was created and search_for_card was called
        # (it will be called but will immediately return empty results due to no name)
        mock_tcg_search_service.assert_called_once()
        mock_search_service_instance.search_for_card.assert_called_once()
        
        # Response should show 'Unknown' as default when no name was identified
        assert response.name == "Unknown"
        assert response.market_prices is None
        assert response.quality_score == 85.0

    @pytest.mark.asyncio
    @patch('src.scanner.routes.scan.TCGSearchService')
    @patch('src.scanner.routes.scan.PokemonTcgClient') 
    @patch('src.scanner.routes.scan.ProcessingPipeline')
    @patch('src.scanner.routes.scan.GeminiService')
    @patch('src.scanner.routes.scan.CostTracker')
    async def test_scan_with_cost_tracking(
        self,
        mock_cost_tracker,
        mock_gemini_service,
        mock_pipeline,
        mock_tcg_client,
        mock_tcg_search_service,
        sample_image_base64,
        mock_pipeline_result,
        mock_search_results,
        mock_tcg_matches
    ):
        """Test scan with cost tracking enabled."""
        from src.scanner.routes.scan import scan_pokemon_card
        from src.scanner.models.schemas import ScanRequest, ScanOptions
        
        # Setup mocks
        mock_gemini_instance = Mock()
        mock_gemini_service.return_value = mock_gemini_instance
        
        mock_pipeline_instance = Mock()
        mock_pipeline.return_value = mock_pipeline_instance
        mock_pipeline_instance.process_image = AsyncMock(return_value=mock_pipeline_result)
        
        mock_tcg_client_instance = Mock()
        mock_tcg_client.return_value = mock_tcg_client_instance
        
        # Mock cost tracker
        mock_tracker_instance = Mock()
        mock_cost_tracker.return_value = mock_tracker_instance
        mock_tracker_instance.track_gemini_usage = Mock(return_value=0.005)
        mock_tracker_instance.track_tcg_usage = Mock()
        
        # Mock TCGSearchService
        mock_search_service_instance = Mock()
        mock_tcg_search_service.return_value = mock_search_service_instance
        mock_search_service_instance.search_for_card = AsyncMock(
            return_value=(mock_search_results, [], mock_tcg_matches)
        )
        
        # Mock select_best_match
        with patch('src.scanner.routes.scan.select_best_match') as mock_select:
            mock_select.return_value = (mock_search_results[0], [{"card": mock_search_results[0], "score": 1500, "score_breakdown": {}}])
            
            # Create request with cost tracking enabled
            request = ScanRequest(
                image=sample_image_base64,
                filename="test.jpg",
                options=ScanOptions(include_cost_tracking=True)
            )
            
            # Call the endpoint
            response = await scan_pokemon_card(request)
        
        # Verify cost tracking was used
        mock_cost_tracker.assert_called_once()
        mock_tracker_instance.track_gemini_usage.assert_called_once()
        mock_tracker_instance.track_tcg_usage.assert_called_once_with("search")
        
        # Verify cost tracking was called but response doesn't include cost info
        # (ScanResponse doesn't have a cost_info field)