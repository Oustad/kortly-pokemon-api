"""Extended tests for response_parser.py to achieve higher coverage."""

import pytest
from unittest.mock import Mock, patch
from src.scanner.services.response_parser import (
    _extract_market_prices,
    _get_image_url,
    _create_alternative_match,
    create_simplified_response,
    parse_gemini_response
)
from src.scanner.models.schemas import (
    PokemonCard,
    ProcessingInfo,
    GeminiAnalysis,
    LanguageInfo,
    QualityFeedback,
    AlternativeMatch,
    ScanResponse
)


class TestExtractMarketPrices:
    """Test _extract_market_prices function."""

    def test_extract_market_prices_normal_variant(self):
        """Test extracting market prices from normal variant."""
        card = PokemonCard(
            id="test-1",
            name="Pikachu",
            market_prices={
                "normal": {
                    "low": 1.0,
                    "mid": 2.0,
                    "high": 3.0,
                    "market": 2.5
                }
            }
        )
        result = _extract_market_prices(card)
        assert result == {
            "low": 1.0,
            "mid": 2.0,
            "high": 3.0,
            "market": 2.5
        }

    def test_extract_market_prices_holofoil_variant(self):
        """Test extracting market prices from holofoil variant."""
        card = PokemonCard(
            id="test-1",
            name="Charizard",
            market_prices={
                "holofoil": {
                    "low": 100.0,
                    "mid": 150.0,
                    "high": 200.0,
                    "market": 175.0
                }
            }
        )
        result = _extract_market_prices(card)
        assert result == {
            "low": 100.0,
            "mid": 150.0,
            "high": 200.0,
            "market": 175.0
        }

    def test_extract_market_prices_direct_structure(self):
        """Test extracting market prices from direct structure."""
        card = PokemonCard(
            id="test-1",
            name="Pikachu",
            market_prices={
                "low": 5.0,
                "mid": 10.0,
                "high": 15.0,
                "market": 12.0
            }
        )
        result = _extract_market_prices(card)
        assert result == {
            "low": 5.0,
            "mid": 10.0,
            "high": 15.0,
            "market": 12.0
        }

    def test_extract_market_prices_no_market_uses_mid(self):
        """Test that market price defaults to mid when missing."""
        card = PokemonCard(
            id="test-1",
            name="Pikachu",
            market_prices={
                "normal": {
                    "low": 1.0,
                    "mid": 2.0,
                    "high": 3.0
                }
            }
        )
        result = _extract_market_prices(card)
        assert result["market"] == 2.0

    def test_extract_market_prices_no_prices(self):
        """Test with no market prices."""
        card = PokemonCard(
            id="test-1",
            name="Pikachu",
            market_prices=None
        )
        result = _extract_market_prices(card)
        assert result is None

    def test_extract_market_prices_empty_dict(self):
        """Test with empty market prices dict."""
        card = PokemonCard(
            id="test-1",
            name="Pikachu",
            market_prices={}
        )
        result = _extract_market_prices(card)
        assert result is None

    def test_extract_market_prices_priority_order(self):
        """Test that normal takes priority over other variants."""
        card = PokemonCard(
            id="test-1",
            name="Pikachu",
            market_prices={
                "reverseHolofoil": {
                    "low": 20.0,
                    "mid": 30.0,
                    "high": 40.0
                },
                "normal": {
                    "low": 1.0,
                    "mid": 2.0,
                    "high": 3.0
                }
            }
        )
        result = _extract_market_prices(card)
        assert result["low"] == 1.0  # Should use normal, not reverseHolofoil


class TestGetImageUrl:
    """Test _get_image_url function."""

    def test_get_image_url_large_available(self):
        """Test getting large image URL."""
        card = PokemonCard(
            id="test-1",
            name="Pikachu",
            images={
                "large": "https://example.com/large.png",
                "small": "https://example.com/small.png"
            }
        )
        result = _get_image_url(card)
        assert result == "https://example.com/large.png"

    def test_get_image_url_small_only(self):
        """Test getting small image URL when large unavailable."""
        card = PokemonCard(
            id="test-1",
            name="Pikachu",
            images={
                "small": "https://example.com/small.png"
            }
        )
        result = _get_image_url(card)
        assert result == "https://example.com/small.png"

    def test_get_image_url_no_images(self):
        """Test with no images."""
        card = PokemonCard(
            id="test-1",
            name="Pikachu",
            images=None
        )
        result = _get_image_url(card)
        assert result is None

    def test_get_image_url_empty_images(self):
        """Test with empty images dict."""
        card = PokemonCard(
            id="test-1",
            name="Pikachu",
            images={}
        )
        result = _get_image_url(card)
        assert result is None


class TestCreateAlternativeMatch:
    """Test _create_alternative_match function."""

    def test_create_alternative_match_complete_data(self):
        """Test creating alternative match with complete data."""
        match_score_item = {
            "card": {
                "id": "test-1",
                "name": "Pikachu",
                "set": {"name": "Base Set"},
                "number": "25",
                "hp": "60",
                "types": ["Lightning"],
                "rarity": "Common",
                "images": {"large": "https://example.com/large.png"}
            },
            "score": 850
        }
        
        result = _create_alternative_match(match_score_item)
        
        assert isinstance(result, AlternativeMatch)
        assert result.name == "Pikachu"
        assert result.set_name == "Base Set"
        assert result.number == "25"
        assert result.hp == "60"
        assert result.types == ["Lightning"]
        assert result.rarity == "Common"
        assert result.image == "https://example.com/large.png"
        assert result.match_score == 850

    def test_create_alternative_match_minimal_data(self):
        """Test creating alternative match with minimal data."""
        match_score_item = {
            "card": {
                "id": "test-1",
                "name": "Pikachu"
            },
            "score": 750
        }
        
        result = _create_alternative_match(match_score_item)
        
        assert result.name == "Pikachu"
        assert result.set_name is None
        assert result.number is None
        assert result.hp is None
        assert result.types is None
        assert result.rarity is None
        assert result.image is None
        assert result.match_score == 750

    def test_create_alternative_match_no_score(self):
        """Test creating alternative match without score."""
        match_score_item = {
            "card": {
                "id": "test-1",
                "name": "Pikachu"
            }
        }
        
        result = _create_alternative_match(match_score_item)
        assert result.match_score == 0

    def test_create_alternative_match_empty_card(self):
        """Test creating alternative match with empty card data."""
        match_score_item = {
            "card": {},
            "score": 800
        }
        
        result = _create_alternative_match(match_score_item)
        assert result.name == "Unknown"
        assert result.match_score == 800

    def test_create_alternative_match_no_set_name(self):
        """Test creating alternative match without set."""
        match_score_item = {
            "card": {
                "id": "test-1",
                "name": "Pikachu",
                "set": None
            },
            "score": 800
        }
        
        result = _create_alternative_match(match_score_item)
        assert result.set_name is None

    def test_create_alternative_match_small_image_fallback(self):
        """Test image fallback to small when large unavailable."""
        match_score_item = {
            "card": {
                "id": "test-1",
                "name": "Pikachu",
                "images": {"small": "https://example.com/small.png"}
            },
            "score": 800
        }
        
        result = _create_alternative_match(match_score_item)
        assert result.image == "https://example.com/small.png"


class TestCreateSimplifiedResponse:
    """Test create_simplified_response function."""

    def test_create_simplified_response_with_best_match(self):
        """Test creating response with best match."""
        best_match = PokemonCard(
            id="test-1",
            name="Pikachu",
            set_name="Base Set",
            number="25",
            hp="60",
            types=["Lightning"],
            rarity="Common",
            images={"large": "https://example.com/large.png"},
            market_prices={"normal": {"low": 1.0, "mid": 2.0, "high": 3.0}}
        )
        
        processing_info = ProcessingInfo(
            quality_score=85.0,
            quality_feedback=QualityFeedback(overall="good", issues=[], suggestions=[]),
            target_time_ms=1000,
            actual_time_ms=800.0,
            model_used="gemini-2.0-flash",
            image_enhanced=False,
            performance_rating="good",
            timing_breakdown={"total": 800.0}
        )
        
        result = create_simplified_response(
            best_match=best_match,
            processing_info=processing_info,
            best_match_score=900
        )
        
        assert isinstance(result, ScanResponse)
        assert result.name == "Pikachu"
        assert result.set_name == "Base Set"
        assert result.number == "25"
        assert result.hp == "60"
        assert result.types == ["Lightning"]
        assert result.rarity == "Common"
        assert result.image == "https://example.com/large.png"
        assert result.detected_language == "en"
        assert result.match_score == 900
        assert result.quality_score == 85.0
        assert result.market_prices == {"low": 1.0, "mid": 2.0, "high": 3.0, "market": 2.0}

    def test_create_simplified_response_no_best_match(self):
        """Test creating response without best match."""
        processing_info = ProcessingInfo(
            quality_score=30.0,
            quality_feedback=QualityFeedback(overall="poor", issues=["blurry"], suggestions=["better lighting"]),
            target_time_ms=1000,
            actual_time_ms=500.0,
            model_used="gemini-2.0-flash",
            image_enhanced=False,
            performance_rating="good",
            timing_breakdown={"total": 500.0}
        )
        
        result = create_simplified_response(
            best_match=None,
            processing_info=processing_info,
            best_match_score=0
        )
        
        assert result.name == "Unknown Card"
        assert result.quality_score == 30.0
        assert result.match_score == 0

    def test_create_simplified_response_with_gemini_language(self):
        """Test creating response with Gemini language analysis."""
        best_match = PokemonCard(
            id="test-1",
            name="Pikachu",
            set_name="Base Set"
        )
        
        processing_info = ProcessingInfo(
            quality_score=85.0,
            quality_feedback=QualityFeedback(overall="good", issues=[], suggestions=[]),
            target_time_ms=1000,
            actual_time_ms=800.0,
            model_used="gemini-2.0-flash",
            image_enhanced=False,
            performance_rating="good",
            timing_breakdown={"total": 800.0}
        )
        
        gemini_analysis = GeminiAnalysis(
            raw_response="test response",
            language_info=LanguageInfo(
                detected_language="ja",
                original_name="ピカチュウ",
                translated_name="Pikachu"
            )
        )
        
        result = create_simplified_response(
            best_match=best_match,
            processing_info=processing_info,
            gemini_analysis=gemini_analysis,
            best_match_score=800
        )
        
        assert result.detected_language == "ja"

    def test_create_simplified_response_with_other_matches(self):
        """Test creating response with other matches."""
        best_match = PokemonCard(
            id="test-1",
            name="Pikachu",
            set_name="Base Set"
        )
        
        processing_info = ProcessingInfo(
            quality_score=85.0,
            quality_feedback=QualityFeedback(overall="good", issues=[], suggestions=[]),
            target_time_ms=1000,
            actual_time_ms=800.0,
            model_used="gemini-2.0-flash",
            image_enhanced=False,
            performance_rating="good",
            timing_breakdown={"total": 800.0}
        )
        
        all_match_scores = [
            {
                "card": {
                    "id": "test-1",
                    "name": "Pikachu",
                    "set": {"name": "Base Set"},
                    "number": "25"
                },
                "score": 900
            },
            {
                "card": {
                    "id": "test-2",
                    "name": "Pikachu",
                    "set": {"name": "Base Set 2"},
                    "number": "58"
                },
                "score": 800
            },
            {
                "card": {
                    "id": "test-3",
                    "name": "Pikachu",
                    "set": {"name": "Jungle"},
                    "number": "60"
                },
                "score": 700  # Below threshold, should be filtered out
            }
        ]
        
        result = create_simplified_response(
            best_match=best_match,
            processing_info=processing_info,
            all_match_scores=all_match_scores,
            best_match_score=900
        )
        
        # Should have 1 other match (Base Set 2), excluding best match and low score
        assert len(result.other_matches) == 1
        assert result.other_matches[0].set_name == "Base Set 2"
        assert result.other_matches[0].match_score == 800


class TestParseGeminiResponse:
    """Test parse_gemini_response function."""

    def test_parse_gemini_response_valid_json(self):
        """Test parsing valid JSON response."""
        response = '{"name": "Pikachu", "set_name": "Base Set", "number": "25"}'
        result = parse_gemini_response(response)
        
        assert result["name"] == "Pikachu"
        assert result["set_name"] == "Base Set"
        assert result["number"] == "25"

    def test_parse_gemini_response_with_markdown(self):
        """Test parsing response with markdown code blocks."""
        response = '''```json
        {
            "name": "Charizard",
            "set_name": "Base Set",
            "number": "4"
        }
        ```'''
        result = parse_gemini_response(response)
        
        assert result["name"] == "Charizard"
        assert result["set_name"] == "Base Set"
        assert result["number"] == "4"

    def test_parse_gemini_response_invalid_json(self):
        """Test parsing invalid JSON."""
        response = 'This is not valid JSON'
        result = parse_gemini_response(response)
        
        # Should return empty dict for invalid JSON
        assert result == {}

    def test_parse_gemini_response_empty_string(self):
        """Test parsing empty string."""
        response = ''
        result = parse_gemini_response(response)
        
        assert result == {}

    def test_parse_gemini_response_multiple_code_blocks(self):
        """Test parsing response with multiple code blocks."""
        response = '''Here's the analysis:
        ```json
        {
            "name": "Blastoise",
            "set_name": "Base Set"
        }
        ```
        
        And some more text with another block:
        ```json
        {
            "additional": "data"
        }
        ```'''
        result = parse_gemini_response(response)
        
        # Should use first valid JSON block
        assert result["name"] == "Blastoise"
        assert result["set_name"] == "Base Set"

    def test_parse_gemini_response_json_with_extra_text(self):
        """Test parsing JSON with extra text around it."""
        response = '''The card analysis is:
        
        {"name": "Venusaur", "set_name": "Base Set", "hp": "100"}
        
        This concludes the analysis.'''
        result = parse_gemini_response(response)
        
        assert result["name"] == "Venusaur"
        assert result["set_name"] == "Base Set"
        assert result["hp"] == "100"

    def test_parse_gemini_response_malformed_json(self):
        """Test parsing malformed JSON."""
        response = '{"name": "Pikachu", "set_name": "Base Set"'  # Missing closing brace
        result = parse_gemini_response(response)
        
        assert result == {}

    def test_parse_gemini_response_nested_json(self):
        """Test parsing nested JSON structure."""
        response = '''```json
        {
            "name": "Alakazam",
            "set_name": "Base Set",
            "card_type_info": {
                "card_type": "pokemon_front",
                "is_pokemon_card": true
            }
        }
        ```'''
        result = parse_gemini_response(response)
        
        assert result["name"] == "Alakazam"
        assert result["set_name"] == "Base Set"
        assert result["card_type_info"]["card_type"] == "pokemon_front"