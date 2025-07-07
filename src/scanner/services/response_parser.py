"""Response parsing service for Pokemon card scanner."""

import json
import logging
import re
from typing import Any, Dict, Optional

from ..models.schemas import PokemonCard, ProcessingInfo, GeminiAnalysis, ScanResponse, AlternativeMatch, MatchScore

logger = logging.getLogger(__name__)


def contains_vague_indicators(parsed_data: Dict[str, Any]) -> bool:
    """
    Check if Gemini response indicates it couldn't read the card clearly.
    
    Args:
        parsed_data: Parsed data from Gemini response
        
    Returns:
        True if response contains vague indicators suggesting poor image quality
    """
    # Check card type first - card backs legitimately don't have names
    card_type_info = parsed_data.get('card_type_info', {})
    card_type = card_type_info.get('card_type', '')
    
    # Skip quality checks for card backs - they legitimately don't have Pokemon names
    if card_type == 'pokemon_back':
        logger.info("🔍 Card back detected - skipping vague indicator checks")
        return False
    
    # Check if Gemini gave high readability score - trust that over vague detection
    authenticity_info = parsed_data.get('authenticity_info', {})
    readability_score = authenticity_info.get('readability_score')
    if readability_score and readability_score >= 90:
        logger.info(f"🔍 High readability score ({readability_score}) - skipping vague indicator checks")
        return False
    
    # Phrases that indicate Gemini couldn't clearly identify details
    # Use word boundaries to prevent substring matches (e.g., "era" in "energy")
    vague_phrases = [
        "not visible", "not fully visible", "likely", "possibly", 
        "appears to be", "hard to tell", "unclear", "can't see",
        "cannot see", "difficult to see", "seems like", "looks like",
        "maybe", "unknown", "uncertain", "not sure"
    ]
    
    # Check critical fields for vague indicators
    critical_fields = ['set_name', 'number', 'name']
    for field in critical_fields:
        field_value = parsed_data.get(field, '') or ''
        value = str(field_value).lower()
        if value:
            # Use more precise matching to avoid false positives
            for phrase in vague_phrases:
                # Check for whole word matches or phrase boundaries
                if (f" {phrase} " in f" {value} " or 
                    value.startswith(phrase + " ") or 
                    value.endswith(" " + phrase) or
                    value == phrase):
                    logger.info(f"🔍 Vague indicator found in {field}: '{value}' (matched: '{phrase}')")
                    return True
    
    # Additional check for completely empty critical fields
    name = parsed_data.get('name', '').strip()
    if not name or len(name) < 2:
        logger.info("🔍 Vague indicator: Pokemon name missing or too short")
        return True
    
    return False


def _extract_market_prices(card: PokemonCard) -> Optional[Dict[str, float]]:
    """Extract and flatten market prices from a PokemonCard."""
    if not card.market_prices:
        return None
    
    market_prices = {}
    if isinstance(card.market_prices, dict):
        # Check for card type variants (normal, holofoil, reverseHolofoil, etc.)
        price_data = None
        
        # Priority order for price variants
        for variant in ['normal', 'holofoil', 'reverseHolofoil', '1stEditionNormal', '1stEditionHolofoil']:
            if variant in card.market_prices:
                price_data = card.market_prices[variant]
                break
        
        # If no variant found, check for direct price structure
        if not price_data and 'low' in card.market_prices:
            price_data = card.market_prices
        
        # Extract prices from the data
        if price_data and isinstance(price_data, dict):
            market_prices['low'] = price_data.get('low', 0)
            market_prices['mid'] = price_data.get('mid', 0)
            market_prices['high'] = price_data.get('high', 0)
            market_prices['market'] = price_data.get('market', price_data.get('mid', 0))
            return market_prices
    
    return None


def _get_image_url(card: PokemonCard) -> Optional[str]:
    """Extract image URL from a PokemonCard."""
    if card.images:
        return card.images.get('large') or card.images.get('small')
    return None


def _create_alternative_match(match_score_item: Dict[str, Any]) -> AlternativeMatch:
    """Create an AlternativeMatch from a MatchScore item."""
    card = match_score_item.get('card')
    score = match_score_item.get('score', 0)
    
    return AlternativeMatch(
        name=card.get('name', 'Unknown'),
        set_name=card.get('set', {}).get('name') if card.get('set') else None,
        number=card.get('number'),
        hp=card.get('hp'),
        types=card.get('types'),
        rarity=card.get('rarity'),
        image=card.get('images', {}).get('large') or card.get('images', {}).get('small') if card.get('images') else None,
        match_score=score,
        market_prices=_extract_market_prices(PokemonCard(**card)) if card else None
    )


def create_simplified_response(
    best_match: Optional[PokemonCard],
    processing_info: ProcessingInfo,
    gemini_analysis: Optional[GeminiAnalysis] = None,
    all_match_scores: Optional[list] = None,
    best_match_score: int = 0
) -> ScanResponse:
    """Create a unified response from the scan results."""
    
    # Extract detected language from Gemini analysis
    detected_language = "en"  # Default
    if gemini_analysis and gemini_analysis.language_info:
        detected_language = gemini_analysis.language_info.detected_language
    elif gemini_analysis and gemini_analysis.structured_data:
        lang_info = gemini_analysis.structured_data.get('language_info', {})
        detected_language = lang_info.get('detected_language', 'en')
    
    # Create other matches from all_match_scores (excluding best match, limit to 5, score >= 750)
    other_matches = []
    if all_match_scores:
        MINIMUM_SCORE_THRESHOLD = 750
        # Skip first match (best match) and filter by threshold
        for match_item in all_match_scores[1:]:  # Skip index 0 (best match)
            if match_item.get('score', 0) >= MINIMUM_SCORE_THRESHOLD and len(other_matches) < 5:
                try:
                    other_matches.append(_create_alternative_match(match_item))
                except Exception as e:
                    logger.warning(f"Failed to create alternative match: {e}")
                    continue
    
    # If we have a best match from TCG, use that data
    if best_match:
        return ScanResponse(
            name=best_match.name,
            set_name=best_match.set_name,
            number=best_match.number,
            hp=best_match.hp,
            types=best_match.types,
            rarity=best_match.rarity,
            image=_get_image_url(best_match),
            detected_language=detected_language,
            match_score=best_match_score,
            market_prices=_extract_market_prices(best_match),
            quality_score=processing_info.quality_score,
            other_matches=other_matches
        )
    
    # Fallback to Gemini data if no TCG match
    elif gemini_analysis and gemini_analysis.structured_data:
        data = gemini_analysis.structured_data
        return ScanResponse(
            name=data.get('name', 'Unknown'),
            set_name=data.get('set_name'),
            number=data.get('number'),
            hp=data.get('hp'),
            types=data.get('types'),
            rarity=data.get('rarity'),
            image=None,  # No image from Gemini
            detected_language=detected_language,
            match_score=0,  # No TCG match
            market_prices=None,  # No prices without TCG match
            quality_score=processing_info.quality_score,
            other_matches=[]  # No alternatives without TCG match
        )
    
    # Fallback response for cases where we have minimal data
    else:
        # Extract any available data from Gemini analysis
        name = "Unknown Card"
        if gemini_analysis and hasattr(gemini_analysis, 'raw_response'):
            # Try to extract at least a name from the raw response
            name_match = re.search(r'"name":\s*"([^"]+)"', gemini_analysis.raw_response)
            if name_match:
                name = name_match.group(1)
        
        return ScanResponse(
            name=name,
            set_name=None,
            number=None,
            hp=None,
            types=None,
            rarity=None,
            image=None,
            detected_language=detected_language,
            match_score=0,
            market_prices=None,
            quality_score=processing_info.quality_score,
            other_matches=[]
        )


def parse_gemini_response(gemini_response: str) -> Dict[str, Any]:
    """
    Parse Gemini's response to extract structured TCG search parameters.
    
    Args:
        gemini_response: Raw text response from Gemini with various possible formats
        
    Returns:
        Dictionary with parsed search parameters
    """
    # Import here to avoid circular imports
    from .card_matcher import correct_set_based_on_number_pattern, correct_xy_set_based_on_number, extract_set_name_from_symbol
    
    # Try multiple parsing strategies in order of preference
    
    # Strategy 1: Extract structured JSON from TCG_SEARCH markers (preferred format)
    tcg_pattern = r'TCG_SEARCH_START\s*(\{.*?\})\s*TCG_SEARCH_END'
    match = re.search(tcg_pattern, gemini_response, re.DOTALL | re.IGNORECASE)
    
    if match:
        logger.info("📋 Found TCG_SEARCH_START/END format")
    else:
        # Strategy 2: Extract JSON from markdown code blocks
        markdown_pattern = r'```json\s*(\{.*?\})\s*```'
        match = re.search(markdown_pattern, gemini_response, re.DOTALL | re.IGNORECASE)
        
        if match:
            logger.info("📋 Found markdown ```json format")
        else:
            # Strategy 3: Extract raw JSON object from anywhere in response
            json_pattern = r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})'
            matches = re.findall(json_pattern, gemini_response, re.DOTALL)
            
            # Find the largest JSON object (most likely to be complete)
            if matches:
                match_obj = max(matches, key=len)
                # Create a fake match object for consistency
                class FakeMatch:
                    def group(self, n):
                        return match_obj
                match = FakeMatch()
                logger.info("📋 Found raw JSON format")
            else:
                match = None
    
    if match:
        try:
            json_str = match.group(1).strip()
            # Clean up any potential issues with the JSON
            json_str = re.sub(r'[\n\r\t]', ' ', json_str)  # Remove newlines/tabs
            json_str = re.sub(r'\s+', ' ', json_str)       # Normalize whitespace
            
            search_params = json.loads(json_str)
            
            # Clean up the extracted parameters
            cleaned_params = {}
            
            # Extract card type information (with fallback defaults)
            card_type_info = {}
            if 'card_type' in search_params and search_params.get('card_type'):
                card_type = str(search_params.get('card_type', '')).strip().lower()
                # Validate card type
                valid_types = ['pokemon_front', 'pokemon_back', 'non_pokemon', 'unknown']
                if card_type in valid_types:
                    card_type_info['card_type'] = card_type
                else:
                    card_type_info['card_type'] = 'pokemon_front'  # Default to Pokemon front for safety
            else:
                card_type_info['card_type'] = 'pokemon_front'  # Default assumption
            
            # Extract is_pokemon_card flag
            if 'is_pokemon_card' in search_params:
                is_pokemon = search_params.get('is_pokemon_card')
                if isinstance(is_pokemon, bool):
                    card_type_info['is_pokemon_card'] = is_pokemon
                elif isinstance(is_pokemon, str):
                    card_type_info['is_pokemon_card'] = is_pokemon.lower() in ['true', '1', 'yes']
                else:
                    card_type_info['is_pokemon_card'] = card_type_info['card_type'] in ['pokemon_front', 'pokemon_back']
            else:
                card_type_info['is_pokemon_card'] = card_type_info['card_type'] in ['pokemon_front', 'pokemon_back']
            
            # Extract card side
            if 'card_side' in search_params and search_params.get('card_side'):
                card_side = str(search_params.get('card_side', '')).strip().lower()
                valid_sides = ['front', 'back', 'unknown']
                if card_side in valid_sides:
                    card_type_info['card_side'] = card_side
                else:
                    card_type_info['card_side'] = 'unknown'
            else:
                # Infer from card_type if not provided
                if card_type_info['card_type'] == 'pokemon_front':
                    card_type_info['card_side'] = 'front'
                elif card_type_info['card_type'] == 'pokemon_back':
                    card_type_info['card_side'] = 'back'
                else:
                    card_type_info['card_side'] = 'unknown'
                    
            cleaned_params['card_type_info'] = card_type_info
            
            # Extract language information
            language_info = {}
            if 'language' in search_params and search_params['language']:
                language_info['detected_language'] = str(search_params['language']).strip().lower()
            else:
                language_info['detected_language'] = 'en'  # Default to English
                
            if 'original_name' in search_params and search_params['original_name']:
                language_info['original_name'] = str(search_params['original_name']).strip()
            
            # Clean name (this may be translated)
            if 'name' in search_params and search_params['name']:
                name = str(search_params['name']).strip()
                
                # FIRST: Convert energy symbols to text (before cleaning removes them!)
                from ..services.tcg_client import _normalize_energy_symbols
                name = _normalize_energy_symbols(name)
                
                # THEN: Remove common artifacts
                name = re.sub(r'\s*\(.*?\)', '', name)  # Remove parentheses
                name = re.sub(r'[^\w\s-]', '', name)   # Remove special chars except dash
                name = name.strip()
                if name and len(name) > 1:
                    cleaned_params['name'] = name
                    
                    # Check if translation occurred
                    original_name = language_info.get('original_name', '')
                    if original_name and original_name.lower() != name.lower():
                        language_info['translated_name'] = name
                        language_info['is_translation'] = True
                        language_info['translation_note'] = f"Translated '{original_name}' to '{name}' for database search"
                    else:
                        language_info['is_translation'] = False
                        
            cleaned_params['language_info'] = language_info
            
            # Clean set_name
            if 'set_name' in search_params and search_params['set_name']:
                set_name = str(search_params['set_name']).strip()
                if set_name and set_name.lower() not in ['unknown', 'n/a', 'not visible']:
                    # CRITICAL: Pattern-based set correction based on card number
                    card_number = str(search_params.get('number', '')).strip()
                    corrected_set = correct_set_based_on_number_pattern(set_name, card_number)
                    if corrected_set and corrected_set != set_name:
                        logger.info(f"🔧 Corrected set name from '{set_name}' to '{corrected_set}' based on number pattern")
                        cleaned_params['set_name'] = corrected_set
                    else:
                        # CRITICAL: Correct XY-era set misidentification
                        is_xy_era = set_name.upper().startswith("XY") or set_name.upper() == "XY"
                        if is_xy_era and 'number' in search_params:
                            # Check if this might need correction based on number ranges and total count
                            corrected_set = correct_xy_set_based_on_number(card_number, search_params)
                            if corrected_set and corrected_set != set_name:
                                logger.info(f"🔧 Corrected set name from '{set_name}' to '{corrected_set}' based on card features")
                                cleaned_params['set_name'] = corrected_set
                            else:
                                cleaned_params['set_name'] = set_name
                        else:
                            cleaned_params['set_name'] = set_name
            
            # If set_name is missing, try to extract it from set_symbol description
            if 'set_name' not in cleaned_params and 'set_symbol' in search_params and search_params['set_symbol']:
                set_symbol_desc = str(search_params['set_symbol']).strip().lower()
                extracted_set_name = extract_set_name_from_symbol(set_symbol_desc)
                if extracted_set_name:
                    cleaned_params['set_name'] = extracted_set_name
                    logger.info(f"🔍 Extracted set name '{extracted_set_name}' from symbol description: '{set_symbol_desc}'")
            
            # Clean number and extract set size
            if 'number' in search_params and search_params['number']:
                number = str(search_params['number']).strip()
                
                # Extract set size if present (e.g., "4/102" -> set_size = 102)
                set_size = None
                if '/' in number:
                    parts = number.split('/')
                    if len(parts) == 2 and parts[1].strip().isdigit():
                        set_size = int(parts[1].strip())
                        logger.debug(f"🔢 Extracted set size: {set_size} from number '{number}'")
                
                # Extract card number (preserve prefix letters like H in H11/H32 and suffix letters like a in 177a)
                number_match = re.search(r'([A-Za-z]*\d+[A-Za-z]*)', number)
                if number_match:
                    cleaned_params['number'] = number_match.group(1)
                else:
                    # Fallback: just clean whitespace if no standard pattern found
                    cleaned_params['number'] = number.split('/')[0].strip()
                
                # Store set size for matching
                if set_size:
                    cleaned_params['set_size'] = set_size
            
            # Clean HP
            if 'hp' in search_params and search_params['hp']:
                hp = str(search_params['hp']).strip()
                # Extract just digits
                hp_match = re.search(r'(\d+)', hp)
                if hp_match:
                    cleaned_params['hp'] = hp_match.group(1)
            
            # Clean types
            if 'types' in search_params and search_params['types']:
                types = search_params['types']
                if isinstance(types, list):
                    valid_types = []
                    known_types = [
                        'Fire', 'Water', 'Grass', 'Electric', 'Psychic', 'Fighting',
                        'Dark', 'Metal', 'Fairy', 'Dragon', 'Normal', 'Flying',
                        'Bug', 'Rock', 'Ghost', 'Ice', 'Steel', 'Poison', 'Ground'
                    ]
                    for ptype in types:
                        ptype_clean = str(ptype).strip().title()
                        if ptype_clean in known_types:
                            valid_types.append(ptype_clean)
                    if valid_types:
                        cleaned_params['types'] = valid_types[:2]  # Limit to 2 types
            
            # Add supertype if not present
            if 'supertype' in search_params:
                cleaned_params['supertype'] = search_params['supertype']
            
            # Extract visual distinguishing features for better card differentiation
            visual_features = {}
            
            if 'set_symbol' in search_params and search_params['set_symbol']:
                visual_features['set_symbol'] = str(search_params['set_symbol']).strip()
            
            if 'card_series' in search_params and search_params['card_series']:
                visual_features['card_series'] = str(search_params['card_series']).strip()
            
            if 'visual_era' in search_params and search_params['visual_era']:
                visual_features['visual_era'] = str(search_params['visual_era']).strip()
            
            if 'foil_pattern' in search_params and search_params['foil_pattern']:
                visual_features['foil_pattern'] = str(search_params['foil_pattern']).strip()
            
            if 'border_color' in search_params and search_params['border_color']:
                visual_features['border_color'] = str(search_params['border_color']).strip()
            
            if 'energy_symbol_style' in search_params and search_params['energy_symbol_style']:
                visual_features['energy_symbol_style'] = str(search_params['energy_symbol_style']).strip()
            
            if visual_features:
                cleaned_params['visual_features'] = visual_features
            
            # Extract authenticity and readability information
            authenticity_info = {}
            
            # Parse authenticity score
            if 'authenticity_score' in search_params and search_params['authenticity_score']:
                try:
                    score = int(search_params['authenticity_score'])
                    if 0 <= score <= 100:
                        authenticity_info['authenticity_score'] = score
                except (ValueError, TypeError):
                    logger.warning(f"Invalid authenticity_score: {search_params['authenticity_score']}")
            
            # Parse readability score
            if 'readability_score' in search_params and search_params['readability_score']:
                try:
                    score = int(search_params['readability_score'])
                    if 0 <= score <= 100:
                        authenticity_info['readability_score'] = score
                except (ValueError, TypeError):
                    logger.warning(f"Invalid readability_score: {search_params['readability_score']}")
            
            if authenticity_info:
                cleaned_params['authenticity_info'] = authenticity_info
            
            logger.info(f"✅ Extracted structured TCG search parameters: {cleaned_params}")
            return cleaned_params
            
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Failed to parse structured JSON from Gemini: {e}")
    
    # Fallback to regex parsing if structured format fails
    logger.info("🔄 Falling back to regex parsing...")
    search_params = {}
    
    # Extract Pokemon name (most important)
    name_patterns = [
        r"(?:Name|Pokemon|Card):\s*([^\n\r]+)",
        r"1\.\s*([^\n\r]+)",
        r"Pokemon name:\s*([^\n\r]+)"
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, gemini_response, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            # Clean up common artifacts
            name = re.sub(r'\s*\(.*?\)', '', name)  # Remove parentheses
            name = re.sub(r'[^\w\s-]', '', name)   # Remove special chars except dash
            name = name.strip()
            if name and len(name) > 2:
                search_params['name'] = name
                break
    
    # Add default card type info for fallback parsing
    if search_params:
        search_params['card_type_info'] = {
            'card_type': 'pokemon_front',  # Assume Pokemon front card
            'is_pokemon_card': True,
            'card_side': 'front'
        }
        search_params['language_info'] = {
            'detected_language': 'en',
            'is_translation': False
        }
    
    logger.info(f"📋 Fallback extracted TCG search parameters: {search_params}")
    return search_params