"""Focused tests for response_parser.py parsing logic."""

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
    PokemonCard, ProcessingInfo, GeminiAnalysis, ScanResponse, 
    AlternativeMatch, MatchScore, QualityFeedback
)


class TestContainsVagueIndicators:
    """Test contains_vague_indicators function."""
    
    def test_contains_vague_indicators_pokemon_back_skipped(self):
        """Test that card backs skip vague indicator checks."""
        parsed_data = {
            'card_type_info': {'card_type': 'pokemon_back'},
            'name': 'unknown',
            'set_name': 'not visible'
        }
        
        result = contains_vague_indicators(parsed_data)
        assert result is False
    
    def test_contains_vague_indicators_high_readability_skipped(self):
        """Test that high readability scores skip vague checks."""
        parsed_data = {
            'card_type_info': {'card_type': 'pokemon_front'},
            'authenticity_info': {'readability_score': 95},
            'name': 'unclear',
            'set_name': 'not visible'
        }
        
        result = contains_vague_indicators(parsed_data)
        assert result is False
    
    def test_contains_vague_indicators_vague_in_name(self):
        """Test vague indicators in Pokemon name."""
        parsed_data = {
            'card_type_info': {'card_type': 'pokemon_front'},
            'name': 'likely pikachu',
            'set_name': 'Base Set'
        }
        
        result = contains_vague_indicators(parsed_data)
        assert result is True
    
    def test_contains_vague_indicators_vague_in_set_name(self):
        """Test vague indicators in set name."""
        parsed_data = {
            'card_type_info': {'card_type': 'pokemon_front'},
            'name': 'Pikachu',
            'set_name': 'appears to be Base Set'
        }
        
        result = contains_vague_indicators(parsed_data)
        assert result is True
    
    def test_contains_vague_indicators_vague_in_number(self):
        """Test vague indicators in card number."""
        parsed_data = {
            'card_type_info': {'card_type': 'pokemon_front'},
            'name': 'Pikachu',
            'set_name': 'Base Set',
            'number': 'not visible'
        }
        
        result = contains_vague_indicators(parsed_data)
        assert result is True
    
    def test_contains_vague_indicators_short_name(self):
        """Test detection of missing or too short names."""
        parsed_data = {
            'card_type_info': {'card_type': 'pokemon_front'},
            'name': 'P',
            'set_name': 'Base Set'
        }
        
        result = contains_vague_indicators(parsed_data)
        assert result is True
    
    def test_contains_vague_indicators_empty_name(self):
        """Test detection of empty names."""
        parsed_data = {
            'card_type_info': {'card_type': 'pokemon_front'},
            'name': '',
            'set_name': 'Base Set'
        }
        
        result = contains_vague_indicators(parsed_data)
        assert result is True
    
    def test_contains_vague_indicators_clean_data(self):
        """Test clean data returns False."""
        parsed_data = {
            'card_type_info': {'card_type': 'pokemon_front'},
            'name': 'Pikachu',
            'set_name': 'Base Set',
            'number': '25'
        }
        
        result = contains_vague_indicators(parsed_data)
        assert result is False
    
    def test_contains_vague_indicators_word_boundaries(self):
        """Test that word boundaries prevent false positives."""
        parsed_data = {
            'card_type_info': {'card_type': 'pokemon_front'},
            'name': 'Pikachu',
            'set_name': 'Legendary Collection',  # "legendary" contains "end" but shouldn't match
            'number': '25'
        }
        
        result = contains_vague_indicators(parsed_data)
        assert result is False
    
    def test_contains_vague_indicators_various_phrases(self):
        """Test various vague phrases."""
        vague_phrases = [
            "not visible", "possibly", "hard to tell", "unclear", 
            "seems like", "maybe", "unknown", "uncertain"
        ]
        
        for phrase in vague_phrases:
            parsed_data = {
                'card_type_info': {'card_type': 'pokemon_front'},
                'name': f'Pikachu {phrase}',
                'set_name': 'Base Set'
            }
            
            result = contains_vague_indicators(parsed_data)
            assert result is True, f"Failed to detect vague phrase: {phrase}"


class TestParseGeminiResponse:
    """Test parse_gemini_response function."""
    
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
    
    def test_parse_gemini_response_markdown_format(self):
        """Test parsing markdown code block format."""
        response = '''
        Here's the analysis:
        ```json
        {
            "name": "Charizard",
            "set_name": "Base Set",
            "number": "4",
            "hp": "120",
            "types": ["Fire"],
            "card_type": "pokemon_front"
        }
        ```
        '''
        
        result = parse_gemini_response(response)
        
        assert result['name'] == 'Charizard'
        assert result['set_name'] == 'Base Set'
        assert result['number'] == '4'
        assert result['hp'] == '120'
        assert result['types'] == ['Fire']
    
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
    
    def test_parse_gemini_response_invalid_json(self):
        """Test handling of invalid JSON."""
        response = '''
        TCG_SEARCH_START
        {
            "name": "Pikachu",
            "invalid": json structure
        }
        TCG_SEARCH_END
        '''
        
        result = parse_gemini_response(response)
        
        # Should fall back to regex parsing
        assert 'name' not in result or not result.get('name')
    
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
    
    def test_parse_gemini_response_empty_response(self):
        """Test handling of empty response."""
        response = ""
        
        result = parse_gemini_response(response)
        
        assert result == {}
    
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


class TestExtractMarketPrices:
    """Test _extract_market_prices function."""
    
    def test_extract_market_prices_normal_variant(self):
        """Test extracting prices from normal variant."""
        card = PokemonCard(
            id="test-id",
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
        
        assert result['low'] == 1.0
        assert result['mid'] == 2.0
        assert result['high'] == 3.0
        assert result['market'] == 2.5
    
    def test_extract_market_prices_holofoil_variant(self):
        """Test extracting prices from holofoil variant."""
        card = PokemonCard(
            id="test-id",
            name="Pikachu",
            market_prices={
                "holofoil": {
                    "low": 5.0,
                    "mid": 10.0,
                    "high": 15.0
                }
            }
        )
        
        result = _extract_market_prices(card)
        
        assert result['low'] == 5.0
        assert result['mid'] == 10.0
        assert result['high'] == 15.0
        assert result['market'] == 10.0  # Should use mid as fallback
    
    def test_extract_market_prices_no_prices(self):
        """Test with no market prices."""
        card = PokemonCard(id="test-id", name="Pikachu")
        
        result = _extract_market_prices(card)
        
        assert result is None
    
    def test_extract_market_prices_direct_structure(self):
        """Test direct price structure without variants."""
        card = PokemonCard(
            id="test-id",
            name="Pikachu",
            market_prices={
                "low": 1.0,
                "mid": 2.0,
                "high": 3.0
            }
        )
        
        result = _extract_market_prices(card)
        
        assert result['low'] == 1.0
        assert result['mid'] == 2.0
        assert result['high'] == 3.0
        assert result['market'] == 2.0


class TestGetImageUrl:
    """Test _get_image_url function."""
    
    def test_get_image_url_large_available(self):
        """Test getting large image URL."""
        card = PokemonCard(
            id="test-id",
            name="Pikachu",
            images={
                "large": "https://example.com/large.jpg",
                "small": "https://example.com/small.jpg"
            }
        )
        
        result = _get_image_url(card)
        
        assert result == "https://example.com/large.jpg"
    
    def test_get_image_url_small_fallback(self):
        """Test fallback to small image URL."""
        card = PokemonCard(
            id="test-id",
            name="Pikachu",
            images={
                "small": "https://example.com/small.jpg"
            }
        )
        
        result = _get_image_url(card)
        
        assert result == "https://example.com/small.jpg"
    
    def test_get_image_url_no_images(self):
        """Test with no images."""
        card = PokemonCard(id="test-id", name="Pikachu")
        
        result = _get_image_url(card)
        
        assert result is None


class TestCreateAlternativeMatch:
    """Test _create_alternative_match function."""
    
    def test_create_alternative_match_complete_data(self):
        """Test creating alternative match with complete data."""
        match_score_item = {
            'card': {
                'name': 'Pikachu',
                'set': {'name': 'Base Set'},
                'number': '25',
                'hp': '60',
                'types': ['Electric'],
                'rarity': 'Common',
                'images': {'large': 'https://example.com/large.jpg'}
            },
            'score': 850
        }
        
        with patch('src.scanner.services.response_parser.PokemonCard') as mock_card_class:
            mock_card_instance = Mock()
            mock_card_instance.market_prices = None
            mock_card_class.return_value = mock_card_instance
            
            result = _create_alternative_match(match_score_item)
            
            assert result.name == 'Pikachu'
            assert result.set_name == 'Base Set'
            assert result.number == '25'
            assert result.hp == '60'
            assert result.types == ['Electric']
            assert result.rarity == 'Common'
            assert result.image == 'https://example.com/large.jpg'
            assert result.match_score == 850
    
    def test_create_alternative_match_minimal_data(self):
        """Test creating alternative match with minimal data."""
        match_score_item = {
            'card': {
                'name': 'Charizard'
            },
            'score': 750
        }
        
        with patch('src.scanner.services.response_parser.PokemonCard') as mock_card_class:
            mock_card_instance = Mock()
            mock_card_instance.market_prices = None
            mock_card_class.return_value = mock_card_instance
            
            result = _create_alternative_match(match_score_item)
            
            assert result.name == 'Charizard'
            assert result.set_name is None
            assert result.number is None
            assert result.match_score == 750
    
    def test_create_alternative_match_no_card(self):
        """Test creating alternative match with minimal card data."""
        match_score_item = {
            'card': {},  # Empty card data
            'score': 750
        }
        
        with patch('src.scanner.services.response_parser._extract_market_prices') as mock_extract:
            mock_extract.return_value = None
            
            result = _create_alternative_match(match_score_item)
            
            assert result.name == 'Unknown'
            assert result.match_score == 750


class TestCreateSimplifiedResponse:
    """Test create_simplified_response function."""
    
    def test_create_simplified_response_with_best_match(self):
        """Test creating response with best match."""
        best_match = PokemonCard(
            id="test-id",
            name="Pikachu",
            set_name="Base Set",
            number="25",
            hp="60",
            types=["Electric"],
            rarity="Common"
        )
        
        processing_info = ProcessingInfo(
            quality_score=85,
            quality_feedback=QualityFeedback(overall="good"),
            target_time_ms=1000,
            actual_time_ms=800,
            model_used="test-model",
            image_enhanced=False,
            performance_rating="good",
            timing_breakdown={"total": 800}
        )
        
        result = create_simplified_response(best_match, processing_info, best_match_score=900)
        
        assert result.name == "Pikachu"
        assert result.set_name == "Base Set"
        assert result.number == "25"
        assert result.hp == "60"
        assert result.types == ["Electric"]
        assert result.rarity == "Common"
        assert result.match_score == 900
        assert result.quality_score == 85
    
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
    
    def test_create_simplified_response_with_other_matches(self):
        """Test creating response with other matches."""
        best_match = PokemonCard(id="test-id", name="Pikachu", set_name="Base Set")
        processing_info = ProcessingInfo(
            quality_score=85,
            quality_feedback=QualityFeedback(overall="good"),
            target_time_ms=1000,
            actual_time_ms=800,
            model_used="test-model",
            image_enhanced=False,
            performance_rating="good",
            timing_breakdown={"total": 800}
        )
        
        all_match_scores = [
            {'card': {'name': 'Pikachu', 'set': {'name': 'Base Set'}}, 'score': 900},
            {'card': {'name': 'Pikachu', 'set': {'name': 'Base Set 2'}}, 'score': 800},
            {'card': {'name': 'Pikachu', 'set': {'name': 'Jungle'}}, 'score': 700}  # Below threshold
        ]
        
        with patch('src.scanner.services.response_parser._create_alternative_match') as mock_create_alt:
            mock_alt_match = AlternativeMatch(
                name='Pikachu',
                set_name='Base Set 2',
                match_score=800
            )
            mock_create_alt.return_value = mock_alt_match
            
            result = create_simplified_response(best_match, processing_info, 
                                              all_match_scores=all_match_scores, 
                                              best_match_score=900)
            
            assert len(result.other_matches) == 1  # Only one above threshold
            assert result.other_matches[0].name == 'Pikachu'
            assert result.other_matches[0].set_name == 'Base Set 2'
            assert result.other_matches[0].match_score == 800
    
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