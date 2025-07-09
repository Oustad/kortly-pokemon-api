"""Consolidated tests for response_parser.py with comprehensive coverage."""

import pytest
import json
from unittest.mock import Mock, patch
from typing import Dict, Any, Optional, List

from src.scanner.services.response_parser import (
    contains_vague_indicators,
    parse_gemini_response,
    create_simplified_response,
    _extract_market_prices,
    _get_image_url,
    _create_alternative_match
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


class TestContainsVagueIndicators:
    """Test contains_vague_indicators function."""

    def test_contains_vague_indicators_basic(self):
        """Test vague indicators detection with clear indicators."""
        # Test with vague language
        parsed_data = {
            'name': 'possibly Pikachu',
            'set_name': 'Base Set'
        }
        assert contains_vague_indicators(parsed_data) is True

    def test_contains_vague_indicators_clean_data(self):
        """Test vague indicators with clean data."""
        parsed_data = {
            'name': 'Pikachu',
            'set_name': 'Base Set',
            'number': '25'
        }
        assert contains_vague_indicators(parsed_data) is False

    def test_contains_vague_indicators_empty_name(self):
        """Test vague indicators with empty name."""
        parsed_data = {
            'name': '',
            'set_name': 'Base Set'
        }
        assert contains_vague_indicators(parsed_data) is True

    def test_contains_vague_indicators_short_name(self):
        """Test vague indicators with very short name."""
        parsed_data = {
            'name': 'A',
            'set_name': 'Base Set'
        }
        assert contains_vague_indicators(parsed_data) is True

    def test_contains_vague_indicators_card_back(self):
        """Test vague indicators with card back type."""
        parsed_data = {
            'name': '',
            'card_type_info': {
                'card_type': 'pokemon_back'
            }
        }
        # Card backs should not trigger vague indicators
        assert contains_vague_indicators(parsed_data) is False

    def test_contains_vague_indicators_high_readability(self):
        """Test vague indicators with high readability score."""
        parsed_data = {
            'name': 'unclear Pokemon',
            'authenticity_info': {
                'readability_score': 95
            }
        }
        # High readability should override vague detection
        assert contains_vague_indicators(parsed_data) is False

    def test_contains_vague_indicators_various_phrases(self):
        """Test different vague phrases."""
        vague_phrases = [
            'not visible', 'likely', 'appears to be', 'hard to tell',
            'unclear', "can't see", 'maybe', 'unknown', 'possibly',
            'seems like', 'uncertain'
        ]
        
        for phrase in vague_phrases:
            parsed_data = {
                'name': f'this is {phrase} text',
                'set_name': 'Base Set'
            }
            assert contains_vague_indicators(parsed_data) is True, f"Failed to detect vague phrase: {phrase}"

    def test_contains_vague_indicators_set_name_field(self):
        """Test vague indicators in set_name field."""
        parsed_data = {
            'name': 'Pikachu',
            'set_name': 'not sure what set'
        }
        assert contains_vague_indicators(parsed_data) is True

    def test_contains_vague_indicators_number_field(self):
        """Test vague indicators in number field."""
        parsed_data = {
            'name': 'Pikachu',
            'set_name': 'Base Set',
            'number': 'unclear number'
        }
        assert contains_vague_indicators(parsed_data) is True

    def test_contains_vague_indicators_missing_fields(self):
        """Test with missing critical fields."""
        parsed_data = {
            'other_field': 'some value'
        }
        # Missing name should trigger vague indicator
        assert contains_vague_indicators(parsed_data) is True

    def test_contains_vague_indicators_whitespace_name(self):
        """Test with whitespace-only name."""
        parsed_data = {
            'name': '   ',
            'set_name': 'Base Set'
        }
        assert contains_vague_indicators(parsed_data) is True

    def test_contains_vague_indicators_word_boundaries(self):
        """Test that word boundaries work correctly."""
        # Should NOT trigger on substring matches
        parsed_data = {
            'name': 'energy card',  # "era" is in "energy" but shouldn't match "era"
            'set_name': 'Legendary Collection'  # "legendary" contains "end" but shouldn't match
        }
        assert contains_vague_indicators(parsed_data) is False

    def test_contains_vague_indicators_exact_match(self):
        """Test exact phrase matching."""
        parsed_data = {
            'name': 'maybe',  # Exact match should trigger
            'set_name': 'Base Set'
        }
        assert contains_vague_indicators(parsed_data) is True

    def test_contains_vague_indicators_case_insensitive(self):
        """Test case insensitive matching."""
        parsed_data = {
            'name': 'UNCLEAR Pokemon',
            'set_name': 'Base Set'
        }
        assert contains_vague_indicators(parsed_data) is True


class TestParseGeminiResponse:
    """Test parse_gemini_response function."""

    def test_parse_gemini_response_valid_json(self):
        """Test parsing valid JSON response."""
        response = '{"name": "Pikachu", "set_name": "Base Set", "number": "25"}'
        result = parse_gemini_response(response)
        
        assert result["name"] == "Pikachu"
        assert result["set_name"] == "Base Set"
        assert result["number"] == "25"

    def test_parse_gemini_response_tcg_search_format(self):
        """Test parsing TCG_SEARCH_START/END format."""
        response = '''
        Some text before
        TCG_SEARCH_START
        {
            "name": "Pikachu",
            "set_name": "Base Set",
            "number": "25",
            "hp": "60",
            "types": ["Electric"],
            "card_type": "pokemon_front",
            "is_pokemon_card": true,
            "language": "en"
        }
        TCG_SEARCH_END
        Some text after
        '''
        
        result = parse_gemini_response(response)
        
        assert result['name'] == 'Pikachu'
        assert result['set_name'] == 'Base Set'
        assert result['number'] == '25'
        assert result['hp'] == '60'
        assert result['types'] == ['Electric']
        assert result['card_type_info']['card_type'] == 'pokemon_front'
        assert result['card_type_info']['is_pokemon_card'] is True
        assert result['language_info']['detected_language'] == 'en'

    def test_parse_gemini_response_with_markdown(self):
        """Test parsing response with markdown code blocks."""
        response = '''```json
        {
            "name": "Charizard",
            "set_name": "Base Set",
            "number": "4",
            "hp": "120",
            "types": ["Fire"]
        }
        ```'''
        result = parse_gemini_response(response)
        
        assert result["name"] == "Charizard"
        assert result["set_name"] == "Base Set"
        assert result["number"] == "4"
        assert result["hp"] == "120"
        assert result["types"] == ["Fire"]

    def test_parse_gemini_response_raw_json(self):
        """Test parsing raw JSON from response."""
        response = '''
        Analysis shows {"name": "Blastoise", "set_name": "Base Set", "number": "2", "hp": "100", "types": ["Water"]} in the image.
        '''
        
        result = parse_gemini_response(response)
        
        assert result['name'] == 'Blastoise'
        assert result['set_name'] == 'Base Set'
        assert result['number'] == '2'
        assert result['hp'] == '100'
        assert result['types'] == ['Water']

    def test_parse_gemini_response_name_cleaning(self):
        """Test name cleaning functionality."""
        response = '''
        TCG_SEARCH_START
        {
            "name": "Pikachu (with artifacts)",
            "set_name": "Base Set",
            "card_type": "pokemon_front"
        }
        TCG_SEARCH_END
        '''
        
        result = parse_gemini_response(response)
        
        assert result['name'] == 'Pikachu'  # Should remove parentheses

    def test_parse_gemini_response_number_with_set_size(self):
        """Test number parsing with set size extraction."""
        response = '''
        TCG_SEARCH_START
        {
            "name": "Pikachu",
            "number": "25/102",
            "set_name": "Base Set",
            "card_type": "pokemon_front"
        }
        TCG_SEARCH_END
        '''
        
        result = parse_gemini_response(response)
        
        assert result['number'] == '25'
        assert result['set_size'] == 102

    def test_parse_gemini_response_types_validation(self):
        """Test type validation and cleaning."""
        response = '''
        TCG_SEARCH_START
        {
            "name": "Pikachu",
            "types": ["Electric", "InvalidType", "Fire"],
            "card_type": "pokemon_front"
        }
        TCG_SEARCH_END
        '''
        
        result = parse_gemini_response(response)
        
        assert result['types'] == ['Electric', 'Fire']  # Should filter out invalid types

    def test_parse_gemini_response_authenticity_scores(self):
        """Test authenticity and readability score parsing."""
        response = '''
        TCG_SEARCH_START
        {
            "name": "Pikachu",
            "authenticity_score": 85,
            "readability_score": 90,
            "card_type": "pokemon_front"
        }
        TCG_SEARCH_END
        '''
        
        result = parse_gemini_response(response)
        
        assert result['authenticity_info']['authenticity_score'] == 85
        assert result['authenticity_info']['readability_score'] == 90

    def test_parse_gemini_response_language_info(self):
        """Test language information parsing."""
        response = '''
        TCG_SEARCH_START
        {
            "name": "Pikachu",
            "original_name": "ピカチュウ",
            "language": "ja",
            "card_type": "pokemon_front"
        }
        TCG_SEARCH_END
        '''
        
        result = parse_gemini_response(response)
        
        assert result['language_info']['detected_language'] == 'ja'
        assert result['language_info']['original_name'] == 'ピカチュウ'
        assert result['language_info']['is_translation'] is True
        assert result['language_info']['translated_name'] == 'Pikachu'

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

    def test_parse_gemini_response_fallback_parsing(self):
        """Test fallback regex parsing."""
        response = '''
        Name: Pikachu
        Set: Base Set
        Number: 25
        '''
        
        result = parse_gemini_response(response)
        
        assert result['name'] == 'Pikachu'
        assert result['card_type_info']['card_type'] == 'pokemon_front'
        assert result['language_info']['detected_language'] == 'en'

    def test_parse_gemini_response_card_type_validation(self):
        """Test card type validation."""
        response = '''
        TCG_SEARCH_START
        {
            "name": "Pikachu",
            "card_type": "invalid_type"
        }
        TCG_SEARCH_END
        '''
        
        result = parse_gemini_response(response)
        
        assert result['card_type_info']['card_type'] == 'pokemon_front'  # Should default


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

    def test_create_simplified_response_with_gemini_fallback(self):
        """Test creating response with Gemini fallback."""
        gemini_analysis = Mock()
        gemini_analysis.structured_data = {
            'name': 'Charizard',
            'set_name': 'Base Set',
            'number': '4',
            'hp': '120',
            'types': ['Fire']
        }
        gemini_analysis.language_info = Mock()
        gemini_analysis.language_info.detected_language = 'en'
        
        processing_info = ProcessingInfo(
            quality_score=75,
            quality_feedback=QualityFeedback(overall="fair"),
            target_time_ms=1000,
            actual_time_ms=900,
            model_used="test-model",
            image_enhanced=False,
            performance_rating="fair",
            timing_breakdown={"total": 900}
        )
        
        result = create_simplified_response(None, processing_info, gemini_analysis)
        
        assert result.name == "Charizard"
        assert result.set_name == "Base Set"
        assert result.number == "4"
        assert result.hp == "120"
        assert result.types == ['Fire']
        assert result.match_score == 0
        assert result.quality_score == 75

    def test_create_simplified_response_minimal_fallback(self):
        """Test creating response with minimal fallback."""
        processing_info = ProcessingInfo(
            quality_score=60,
            quality_feedback=QualityFeedback(overall="poor"),
            target_time_ms=1000,
            actual_time_ms=1200,
            model_used="test-model",
            image_enhanced=False,
            performance_rating="poor",
            timing_breakdown={"total": 1200}
        )
        
        result = create_simplified_response(None, processing_info)
        
        assert result.name == "Unknown Card"
        assert result.set_name is None
        assert result.match_score == 0
        assert result.quality_score == 60
        assert result.other_matches == []

    def test_create_simplified_response_extract_name_from_raw(self):
        """Test extracting name from raw Gemini response."""
        gemini_analysis = Mock()
        gemini_analysis.structured_data = None
        gemini_analysis.raw_response = '{"name": "Extracted Pokemon"}'
        gemini_analysis.language_info = None
        
        processing_info = ProcessingInfo(
            quality_score=70,
            quality_feedback=QualityFeedback(overall="fair"),
            target_time_ms=1000,
            actual_time_ms=950,
            model_used="test-model",
            image_enhanced=False,
            performance_rating="fair",
            timing_breakdown={"total": 950}
        )
        
        result = create_simplified_response(None, processing_info, gemini_analysis)
        
        assert result.name == "Extracted Pokemon"
        assert result.match_score == 0
        assert result.quality_score == 70