"""Main card scanning endpoint for Pokemon card scanner."""

import base64
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..config import get_config
from ..models.schemas import (
    CostInfo,
    ErrorResponse,
    GeminiAnalysis,
    MatchScore,
    PokemonCard,
    ProcessingInfo,
    QualityFeedback,
    ScanRequest,
    ScanResponse,
    SimplifiedScanResponse,
)
from ..services.gemini_service import GeminiService
from ..services.image_processor import ImageProcessor
from ..services.metrics_service import get_metrics_service, RequestMetrics
from ..services.processing_pipeline import ProcessingPipeline
from ..services.tcg_client import PokemonTcgClient
from ..services.webhook_service import send_error_webhook
from ..utils.cost_tracker import CostTracker

logger = logging.getLogger(__name__)
config = get_config()

router = APIRouter(prefix="/api/v1", tags=["scanner"])

# Constants
MINIMUM_SCORE_THRESHOLD = 750  # Cards below this score are likely wrong matches


def _get_set_family(set_name: str) -> Optional[List[str]]:
    """
    Map generic set names to their specific family expansions.
    
    Args:
        set_name: Generic set name extracted by AI
        
    Returns:
        List of specific set names to search, or None if no family mapping
    """
    if not set_name:
        return None
        
    set_name_lower = set_name.lower().strip()
    logger.info(f"🔍 _get_set_family called with: '{set_name}' (normalized: '{set_name_lower}')")
    
    # XY-era set families
    if set_name_lower in ["xy", "x y", "xy base"]:
        return [
            "XY", 
            "XY BREAKpoint", 
            "XY BREAKthrough", 
            "XY Fates Collide",
            "XY Steam Siege",
            "XY Evolutions",
            "XY Flashfire",
            "XY Furious Fists", 
            "XY Phantom Forces",
            "XY Primal Clash",
            "XY Roaring Skies",
            "XY Ancient Origins"
        ]
    
    # Sun & Moon era
    elif set_name_lower in ["sun moon", "sun & moon", "sm"]:
        return [
            "Sun & Moon",
            "Sun & Moon Guardians Rising", 
            "Sun & Moon Burning Shadows",
            "Sun & Moon Crimson Invasion",
            "Sun & Moon Ultra Prism",
            "Sun & Moon Forbidden Light",
            "Sun & Moon Celestial Storm",
            "Sun & Moon Lost Thunder",
            "Sun & Moon Team Up",
            "Sun & Moon Unbroken Bonds",
            "Sun & Moon Unified Minds",
            "Sun & Moon Cosmic Eclipse"
        ]
    
    # Sword & Shield era
    elif set_name_lower in ["sword shield", "sword & shield", "swsh"]:
        return [
            "Sword & Shield",
            "Sword & Shield Rebel Clash",
            "Sword & Shield Darkness Ablaze", 
            "Sword & Shield Vivid Voltage",
            "Sword & Shield Battle Styles",
            "Sword & Shield Chilling Reign",
            "Sword & Shield Evolving Skies",
            "Sword & Shield Fusion Strike",
            "Sword & Shield Brilliant Stars",
            "Sword & Shield Astral Radiance",
            "Sword & Shield Lost Origin",
            "Sword & Shield Silver Tempest"
        ]
    
    # HeartGold/SoulSilver era
    elif set_name_lower in ["heartgold", "soulsilver", "hgss", "hs", "heart gold", "soul silver"]:
        return [
            "HeartGold & SoulSilver",
            "HS—Unleashed", 
            "HS—Undaunted",
            "HS—Triumphant",
            "Unleashed",
            "Undaunted", 
            "Triumphant"
        ]
    
    # Specific HGSS set searches
    elif set_name_lower in ["undaunted", "hs undaunted", "hs—undaunted"]:
        logger.info(f"   ✅ Matched Undaunted set family")
        return ["HS—Undaunted", "Undaunted"]
    elif set_name_lower in ["unleashed", "hs unleashed", "hs—unleashed"]:
        logger.info(f"   ✅ Matched Unleashed set family")
        return ["HS—Unleashed", "Unleashed"]  
    elif set_name_lower in ["triumphant", "hs triumphant", "hs—triumphant"]:
        logger.info(f"   ✅ Matched Triumphant set family")
        return ["HS—Triumphant", "Triumphant"]
        
    # No family mapping found
    logger.info(f"   ❌ No set family mapping found for '{set_name}'")
    return None


def _is_xy_family_match(gemini_set: str, card_set: str) -> bool:
    """
    Check if two sets are within the same XY family.
    
    Args:
        gemini_set: Set name from AI (lowercased)
        card_set: Set name from TCG API (lowercased)
        
    Returns:
        True if both sets are in the XY family
    """
    xy_sets = [
        "xy", "xy base",
        "xy flashfire", "xy furious fists", "xy phantom forces", 
        "xy primal clash", "xy roaring skies", "xy ancient origins",
        "xy breakthrough", "xy breakpoint", "xy fates collide", 
        "xy steam siege", "xy evolutions"
    ]
    
    # Normalize set names for comparison
    gemini_normalized = gemini_set.replace(" ", "").replace("-", "").lower()
    card_normalized = card_set.replace(" ", "").replace("-", "").lower()
    
    gemini_is_xy = any(xy_set.replace(" ", "").replace("-", "") in gemini_normalized for xy_set in xy_sets)
    card_is_xy = any(xy_set.replace(" ", "").replace("-", "") in card_normalized for xy_set in xy_sets)
    
    return gemini_is_xy and card_is_xy


def _get_set_from_total_count(total_count: int) -> Optional[str]:
    """
    Map total card count to XY set name.
    
    Args:
        total_count: Total number of cards in the set (from "40/122" format)
        
    Returns:
        XY set name or None if no match found
    """
    # XY Set total card counts (extracted from ranges)
    xy_total_counts = {
        146: "XY",  # Base XY set
        109: "XY Flashfire",
        113: "XY Furious Fists", 
        124: "XY Phantom Forces",
        164: "XY Primal Clash",  # Note: Same as BREAKthrough
        110: "XY Roaring Skies",
        100: "XY Ancient Origins",
        122: "XY BREAKpoint",  # This should match Greninja "41/122"
        125: "XY Fates Collide",
        116: "XY Steam Siege",
        # Note: XY Evolutions has 113 cards (same as Furious Fists)
        # Note: XY BREAKthrough has 164 cards (same as Primal Clash)
    }
    
    # Handle duplicates by checking for specific context clues
    if total_count in xy_total_counts:
        return xy_total_counts[total_count]
    
    # Handle ambiguous cases (164 cards could be Primal Clash or BREAKthrough)
    if total_count == 164:
        # Return most common/likely option, correction logic will refine further
        return "XY BREAKthrough"
    elif total_count == 113:
        # Return most common/likely option between Furious Fists and Evolutions
        return "XY Furious Fists"
    
    logger.info(f"   ❌ No XY set found for total count: {total_count}")
    return None


def _correct_xy_set_based_on_number(card_number: str, search_params: Dict[str, Any]) -> Optional[str]:
    """
    Correct XY set identification based on card number, total count, and visual features.
    
    Args:
        card_number: The card number extracted by AI (e.g., "41/122")
        search_params: Full search parameters including visual features
        
    Returns:
        Corrected set name or None if no correction needed
    """
    if not card_number:
        return None
    
    logger.info(f"🔍 XY correction logic running for card number: '{card_number}'")
    
    # Try to extract both individual number and total count from formats like "41/122"
    total_count = None
    individual_num = None
    
    # Parse "41/122" format
    if '/' in card_number:
        parts = card_number.split('/')
        if len(parts) == 2:
            try:
                individual_num = int(parts[0].strip())
                total_count = int(parts[1].strip())
                logger.info(f"   📊 Parsed: individual={individual_num}, total={total_count}")
            except ValueError:
                logger.warning(f"   ⚠️ Failed to parse card number format: '{card_number}'")
    
    # Fallback: extract just the individual number
    if individual_num is None:
        number_match = re.search(r'(\d+)', card_number)
        if number_match:
            individual_num = int(number_match.group(1))
            logger.info(f"   📊 Fallback parsed individual number: {individual_num}")
    
    if individual_num is None:
        logger.warning(f"   ❌ Could not extract any number from: '{card_number}'")
        return None
    
    # PRIMARY: Use total count to identify set if available
    if total_count:
        set_from_total = _get_set_from_total_count(total_count)
        if set_from_total:
            logger.info(f"   ✅ Set identified by total count ({total_count}): {set_from_total}")
            
            # Validate that individual number falls within expected range
            xy_set_ranges = {
                "XY": (1, 146), "XY Flashfire": (1, 109), "XY Furious Fists": (1, 113),
                "XY Phantom Forces": (1, 124), "XY Primal Clash": (1, 164), 
                "XY Roaring Skies": (1, 110), "XY Ancient Origins": (1, 100),
                "XY BREAKthrough": (1, 164), "XY BREAKpoint": (1, 122),
                "XY Fates Collide": (1, 125), "XY Steam Siege": (1, 116), 
                "XY Evolutions": (1, 113)
            }
            
            if set_from_total in xy_set_ranges:
                min_num, max_num = xy_set_ranges[set_from_total]
                if min_num <= individual_num <= max_num:
                    logger.info(f"   ✅ Individual number {individual_num} is valid for {set_from_total} (range: {min_num}-{max_num})")
                    return set_from_total
                else:
                    logger.warning(f"   ⚠️ Individual number {individual_num} outside expected range for {set_from_total} ({min_num}-{max_num})")
    
    # SECONDARY: Use visual features for additional validation
    visual_features = search_params.get('visual_features', {})
    name = search_params.get('name', '').lower()
    
    # BREAK cards are strong indicators of BREAKpoint/BREAKthrough
    if 'break' in name:
        if individual_num <= 123:
            logger.info(f"   ✅ BREAK card #{individual_num} → XY BREAKpoint")
            return "XY BREAKpoint" 
        elif individual_num <= 164:
            logger.info(f"   ✅ BREAK card #{individual_num} → XY BREAKthrough")
            return "XY BREAKthrough"
    
    # TERTIARY: Check visual features
    foil_pattern = visual_features.get('foil_pattern', '').lower()
    if 'gold' in foil_pattern or 'yellow' in foil_pattern:
        if 'textured' in foil_pattern or 'break' in foil_pattern:
            # Likely a BREAK card
            if individual_num <= 123:
                logger.info(f"   ✅ Gold foil card #{individual_num} → XY BREAKpoint")
                return "XY BREAKpoint"
            elif individual_num <= 164:
                logger.info(f"   ✅ Gold foil card #{individual_num} → XY BREAKthrough") 
                return "XY BREAKthrough"
    
    logger.info(f"   ❌ No correction determined for card number: '{card_number}'")
    return None


def _extract_set_name_from_symbol(set_symbol_desc: str) -> Optional[str]:
    """
    Extract actual set name from set symbol descriptions.
    
    Args:
        set_symbol_desc: Description of set symbol from AI (e.g., "Plasma Freeze set symbol")
    
    Returns:
        Actual set name or None if not found
    """
    if not set_symbol_desc:
        return None
    
    desc_lower = set_symbol_desc.lower().strip()
    logger.info(f"🔍 _extract_set_name_from_symbol called with: '{set_symbol_desc}' (normalized: '{desc_lower}')")
    
    # Map symbol descriptions to actual set names
    symbol_mappings = {
        # HeartGold/SoulSilver era
        'heartgold': 'HeartGold & SoulSilver',
        'soulsilver': 'HeartGold & SoulSilver', 
        'heart gold': 'HeartGold & SoulSilver',
        'soul silver': 'HeartGold & SoulSilver',
        'hgss': 'HeartGold & SoulSilver',
        'unleashed': 'HS—Unleashed',
        'undaunted': 'HS—Undaunted',
        'triumphant': 'HS—Triumphant',
        'hs unleashed': 'HS—Unleashed',
        'hs undaunted': 'HS—Undaunted', 
        'hs triumphant': 'HS—Triumphant',
        
        # Black & White era
        'plasma freeze': 'Plasma Freeze',
        'plasma storm': 'Plasma Storm', 
        'plasma blast': 'Plasma Blast',
        'black white': 'Black & White',
        'black & white': 'Black & White',
        'emerging powers': 'Emerging Powers',
        'noble victories': 'Noble Victories',
        'next destinies': 'Next Destinies',
        'dark explorers': 'Dark Explorers',
        'dragons exalted': 'Dragons Exalted',
        'boundaries crossed': 'Boundaries Crossed',
        'legendary treasures': 'Legendary Treasures',
        
        # XY era
        'xy flashfire': 'XY Flashfire',
        'xy furious fists': 'XY Furious Fists',
        'xy phantom forces': 'XY Phantom Forces',
        'xy primal clash': 'XY Primal Clash',
        'xy roaring skies': 'XY Roaring Skies',
        'xy ancient origins': 'XY Ancient Origins',
        'xy breakthrough': 'XY BREAKthrough',
        'xy breakthrough': 'XY BREAKthrough',
        'xy breakpoint': 'XY BREAKpoint',
        'xy fates collide': 'XY Fates Collide',
        'xy steam siege': 'XY Steam Siege',
        'xy evolutions': 'XY Evolutions',
        
        # Sun & Moon era
        'sun moon': 'Sun & Moon',
        'sun & moon': 'Sun & Moon',
        'guardians rising': 'Sun & Moon Guardians Rising',
        'burning shadows': 'Sun & Moon Burning Shadows',
        'crimson invasion': 'Sun & Moon Crimson Invasion',
        'ultra prism': 'Sun & Moon Ultra Prism',
        'forbidden light': 'Sun & Moon Forbidden Light',
        'celestial storm': 'Sun & Moon Celestial Storm',
        'lost thunder': 'Sun & Moon Lost Thunder',
        'team up': 'Sun & Moon Team Up',
        'unbroken bonds': 'Sun & Moon Unbroken Bonds',
        'unified minds': 'Sun & Moon Unified Minds',
        'cosmic eclipse': 'Sun & Moon Cosmic Eclipse',
        
        # Sword & Shield era
        'sword shield': 'Sword & Shield',
        'sword & shield': 'Sword & Shield',
        'rebel clash': 'Sword & Shield Rebel Clash',
        'darkness ablaze': 'Sword & Shield Darkness Ablaze',
        'vivid voltage': 'Sword & Shield Vivid Voltage',
        'battle styles': 'Sword & Shield Battle Styles',
        'chilling reign': 'Sword & Shield Chilling Reign',
        'evolving skies': 'Sword & Shield Evolving Skies',
        'fusion strike': 'Sword & Shield Fusion Strike',
        'brilliant stars': 'Sword & Shield Brilliant Stars',
        'astral radiance': 'Sword & Shield Astral Radiance',
        'lost origin': 'Sword & Shield Lost Origin',
        'silver tempest': 'Sword & Shield Silver Tempest',
    }
    
    # Check for direct matches first
    for keyword, set_name in symbol_mappings.items():
        if keyword in desc_lower:
            logger.info(f"   ✅ Found symbol mapping: '{keyword}' → '{set_name}'")
            return set_name
    
    # Look for pattern like "X set symbol" or "X symbol"
    # Remove common suffixes
    for suffix in [' set symbol', ' symbol', ' logo', ' set logo']:
        if desc_lower.endswith(suffix):
            base_name = desc_lower[:-len(suffix)].strip()
            if base_name in symbol_mappings:
                logger.info(f"   ✅ Found suffix mapping: '{base_name}' → '{symbol_mappings[base_name]}'")
                return symbol_mappings[base_name]
    
    logger.info(f"   ❌ No symbol mapping found for '{set_symbol_desc}'")
    return None


def save_processed_image(image_data: bytes, original_filename: str, stage: str = "processed") -> Optional[str]:
    """
    Save processed image to disk for testing and debugging purposes.
    
    Args:
        image_data: The image data as bytes
        original_filename: Original filename for reference
        stage: Stage of processing ("original" or "processed")
        
    Returns:
        Relative path to saved image or None if failed
    """
    try:
        # Create processed_images directory if it doesn't exist
        processed_dir = Path("processed_images")
        processed_dir.mkdir(exist_ok=True)
        
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Remove last 3 microsecond digits
        
        # Create filename
        name_without_ext = Path(original_filename).stem if original_filename else "image"
        extension = ".jpg"  # Always save as JPEG since we process to JPEG
        filename = f"{name_without_ext}_{stage}_{timestamp}{extension}"
        
        # Full path
        file_path = processed_dir / filename
        
        # Save the image
        with open(file_path, "wb") as f:
            f.write(image_data)
        
        logger.info(f"💾 Saved {stage} image: {file_path}")
        return str(file_path)
        
    except Exception as e:
        logger.error(f"❌ Failed to save {stage} image: {str(e)}")
        return None


def calculate_match_score(card_data: Dict[str, Any], gemini_params: Dict[str, Any]) -> int:
    """
    Calculate match score for a TCG card based on Gemini parameters.
    
    Args:
        card_data: Card data from TCG API
        gemini_params: Parsed parameters from Gemini
        
    Returns:
        Match score (higher = better match)
    """
    score = 0
    
    # Name matching (very high priority for exact matches)
    if gemini_params.get("name") and card_data.get("name"):
        gemini_name = gemini_params.get("name", "").lower().strip()
        card_name = card_data.get("name", "").lower().strip()
        
        # Exact name match gets highest priority
        if gemini_name == card_name:
            score += 2000  # Very high score for exact name match
        # Penalize tag team cards when searching for single Pokemon
        elif "&" in card_name and "&" not in gemini_name:
            # Card is a tag team but search is for single Pokemon
            if gemini_name in card_name:
                score += 100  # Low score for partial match on tag team
        # Normal partial matches
        elif gemini_name in card_name or card_name in gemini_name:
            score += 300
    
    # Card number match (high priority) - exact match required
    if gemini_params.get("number") and card_data.get("number"):
        gemini_number = str(gemini_params.get("number", "")).strip()
        card_number = str(card_data.get("number", "")).strip()
        
        if gemini_number == card_number:
            score += 1000  # High score for exact number match
        elif gemini_number in card_number or card_number in gemini_number:
            score += 500   # Partial number match (e.g., "60" matches "SV60")
    
    # HP match (high priority)
    if gemini_params.get("hp") and card_data.get("hp"):
        gemini_hp = str(gemini_params.get("hp", "")).strip()
        card_hp = str(card_data.get("hp", "")).strip()
        
        if gemini_hp == card_hp:
            score += 400
    
    # Types match (medium priority)
    card_types = card_data.get("types", [])
    gemini_types = gemini_params.get("types", [])
    if gemini_types and card_types:
        # Count matching types
        matching_types = len([t for t in gemini_types if t in card_types])
        score += matching_types * 100
    
    # Set name match (already handled by search, but good to verify)
    if gemini_params.get("set_name") and card_data.get("set", {}).get("name"):
        gemini_set = str(gemini_params.get("set_name") or "").lower().strip()
        card_set = str(card_data.get("set", {}).get("name") or "").lower().strip()
        
        if gemini_set == card_set:
            score += 200
        elif gemini_set in card_set or card_set in gemini_set:
            score += 100
    
    # Bonus for Shiny Vault cards when appropriate
    if card_data.get("number", "").startswith("SV") and gemini_params.get("set_name") == "Hidden Fates":
        score += 300  # Bonus for Shiny Vault cards from Hidden Fates
    
    return score


def calculate_match_score_detailed(card_data: Dict[str, Any], gemini_params: Dict[str, Any]) -> tuple[int, Dict[str, int]]:
    """
    Calculate match score with detailed breakdown for transparency.
    CRITICAL: Set + Number + Name combinations get MASSIVE priority over name-only matches.
    
    Returns:
        Tuple of (total_score, score_breakdown_dict)
    """
    score_breakdown = {
        "set_number_name_triple": 0,  # NEW: Highest priority combination
        "set_number_combo": 0,        # NEW: High priority combination
        "name_exact": 0,
        "name_partial": 0,
        "name_tag_team_penalty": 0,
        "number_exact": 0,
        "number_partial": 0,
        "number_mismatch_penalty": 0,  # NEW: Penalty for wrong number
        "hp_match": 0,
        "type_matches": 0,
        "set_exact": 0,
        "set_partial": 0,
        "set_family_match": 0,        # NEW: For XY family matches
        "shiny_vault_bonus": 0,
        "visual_series_match": 0,      # NEW: Visual feature bonuses
        "visual_era_match": 0,         # NEW: Visual era consistency
        "visual_foil_match": 0,        # NEW: Foil pattern match
    }
    
    # Check for critical combination matches first
    has_set_match = False
    has_number_match = False
    has_name_match = False
    
    # Set name match check with XY family handling
    if gemini_params.get("set_name") and card_data.get("set", {}).get("name"):
        gemini_set = str(gemini_params.get("set_name") or "").lower().strip()
        card_set = str(card_data.get("set", {}).get("name") or "").lower().strip()
        
        if gemini_set == card_set:
            has_set_match = True
            score_breakdown["set_exact"] = 2000  # Increased from 200
        elif gemini_set in card_set or card_set in gemini_set:
            # Special handling for XY family sets
            if _is_xy_family_match(gemini_set, card_set):
                # Within XY family but not exact match - moderate bonus instead of penalty
                score_breakdown["set_family_match"] = 800
                logger.debug(f"      XY family match: {gemini_set} <-> {card_set}")
            else:
                score_breakdown["set_partial"] = 500  # Increased from 100
    
    # Card number match check
    if gemini_params.get("number") and card_data.get("number"):
        gemini_number = str(gemini_params.get("number", "")).strip()
        card_number = str(card_data.get("number", "")).strip()
        
        if gemini_number == card_number:
            has_number_match = True
            score_breakdown["number_exact"] = 2000  # Increased from 1000
        elif gemini_number in card_number or card_number in gemini_number:
            score_breakdown["number_partial"] = 800  # Increased from 500
    
    # Name matching check
    if gemini_params.get("name") and card_data.get("name"):
        gemini_name = gemini_params.get("name", "").lower().strip()
        card_name = card_data.get("name", "").lower().strip()
        
        # Exact name match
        if gemini_name == card_name:
            has_name_match = True
            score_breakdown["name_exact"] = 1500  # Decreased from 2000
        # Penalize tag team cards when searching for single Pokemon
        elif "&" in card_name and "&" not in gemini_name:
            # Card is a tag team but search is for single Pokemon
            if gemini_name in card_name:
                score_breakdown["name_partial"] = 100
                score_breakdown["name_tag_team_penalty"] = -500  # Stronger penalty
        # Normal partial matches
        elif gemini_name in card_name or card_name in gemini_name:
            score_breakdown["name_partial"] = 300
    
    # PRIME CARD SPECIAL HANDLING
    if gemini_params.get("name") and card_data.get("name"):
        gemini_name = str(gemini_params.get("name", "")).lower().strip()
        card_name = str(card_data.get("name", "")).lower().strip()
        
        # Both are Prime cards - strong bonus
        if "prime" in gemini_name and "prime" in card_name:
            score_breakdown["prime_card_match"] = 800
            logger.debug(f"      Prime card match bonus: {gemini_name} <-> {card_name}")
        
        # AI detected Prime but card is not Prime - penalty
        elif "prime" in gemini_name and "prime" not in card_name:
            # Check if the base Pokemon name matches (e.g., "Houndoom Prime" vs "Houndoom")
            base_gemini_name = gemini_name.replace(" prime", "").strip()
            if base_gemini_name in card_name:
                score_breakdown["prime_vs_regular_penalty"] = -400
                logger.debug(f"      Prime vs regular penalty: {gemini_name} <-> {card_name}")
        
        # Card is Prime but AI didn't detect - smaller penalty
        elif "prime" not in gemini_name and "prime" in card_name:
            base_card_name = card_name.replace(" prime", "").strip()
            if base_card_name in gemini_name:
                score_breakdown["missed_prime_penalty"] = -200
    
    # CRITICAL COMBINATION BONUSES
    # Triple match: Set + Number + Name = MASSIVE bonus
    if has_set_match and has_number_match and has_name_match:
        score_breakdown["set_number_name_triple"] = 5000  # HUGE bonus for perfect match
    # Dual match: Set + Number = Large bonus
    elif has_set_match and has_number_match:
        score_breakdown["set_number_combo"] = 3000  # Large bonus for set+number match
    
    # CRITICAL PENALTY: If we have a specific number from AI but card doesn't match, HEAVILY penalize
    if gemini_params.get("number") and card_data.get("number"):
        gemini_number = str(gemini_params.get("number", "")).strip()
        card_number = str(card_data.get("number", "")).strip()
        
        # If numbers are completely different (not even partial match), massive penalty
        if gemini_number != card_number and gemini_number not in card_number and card_number not in gemini_number:
            score_breakdown["number_mismatch_penalty"] = -2000  # Heavy penalty for wrong number
    
    # HP match (medium priority)
    if gemini_params.get("hp") and card_data.get("hp"):
        gemini_hp = str(gemini_params.get("hp", "")).strip()
        card_hp = str(card_data.get("hp", "")).strip()
        
        if gemini_hp == card_hp:
            score_breakdown["hp_match"] = 400
    
    # Types match (HIGH priority - critical for correct identification)
    card_types = card_data.get("types", [])
    gemini_types = gemini_params.get("types", [])
    
    if gemini_types and card_types:
        # Convert to standardized format for comparison
        card_types_clean = [str(t).strip().title() for t in card_types if t]
        gemini_types_clean = [str(t).strip().title() for t in gemini_types if t]
        
        # Count matching types
        matching_types = len([t for t in gemini_types_clean if t in card_types_clean])
        total_gemini_types = len(gemini_types_clean)
        total_card_types = len(card_types_clean)
        
        if matching_types > 0:
            # Strong bonus for matching types
            if matching_types == total_gemini_types and matching_types == total_card_types:
                # Perfect type match (all types match exactly)
                score_breakdown["type_perfect_match"] = 800
            elif matching_types == total_gemini_types:
                # All AI-detected types match (partial match)
                score_breakdown["type_ai_complete_match"] = 600
            else:
                # Some types match
                score_breakdown["type_partial_match"] = matching_types * 300
        else:
            # MAJOR PENALTY for completely wrong types (e.g., Fire vs Darkness)
            if total_gemini_types > 0 and total_card_types > 0:
                score_breakdown["type_mismatch_penalty"] = -1500
                logger.debug(f"      Type mismatch penalty: AI detected {gemini_types_clean} but card has {card_types_clean}")
    
    elif gemini_types and not card_types:
        # AI detected types but card has none - minor penalty
        score_breakdown["type_missing_penalty"] = -200
    
    # Special case: Shiny Vault cards
    if card_data.get("number", "").startswith("SV") and gemini_params.get("set_name") == "Hidden Fates":
        score_breakdown["shiny_vault_bonus"] = 300
    
    # VISUAL FEATURE MATCHING - Critical for differentiating similar cards
    visual_features = gemini_params.get("visual_features", {})
    if visual_features:
        # Card series matching (e-Card, EX, XY, etc.)
        if visual_features.get("card_series"):
            gemini_series = str(visual_features["card_series"]).lower() if visual_features["card_series"] else ""
            # Map card series to likely set patterns
            series_patterns = {
                "e-card": ["aquapolis", "skyridge", "expedition"],
                "ex": ["ruby", "sapphire", "emerald", "firered", "leafgreen"],
                "xy": ["xy", "breakpoint", "breakthrough", "fates collide", "steam siege", "evolutions", 
                       "flashfire", "furious fists", "phantom forces", "primal clash", "roaring skies", "ancient origins"],
                "sun moon": ["sun", "moon", "ultra", "cosmic", "guardians rising", "burning shadows", 
                            "crimson invasion", "forbidden light", "celestial storm", "lost thunder"],
                "sword shield": ["sword", "shield", "battle styles", "chilling reign", "rebel clash", 
                                "darkness ablaze", "vivid voltage", "evolving skies", "fusion strike"],
            }
            
            card_set_name = card_data.get("set", {}).get("name") or ""
            card_set_name = card_set_name.lower() if card_set_name else ""
            for series, patterns in series_patterns.items():
                if series in gemini_series:
                    if card_set_name and any(pattern in card_set_name for pattern in patterns):
                        score_breakdown["visual_series_match"] = 500  # Significant bonus for series match
                        break
        
        # Visual era consistency (vintage cards should match vintage sets)
        if visual_features.get("visual_era"):
            gemini_era = str(visual_features["visual_era"]).lower() if visual_features["visual_era"] else ""
            card_set_name = card_data.get("set", {}).get("name") or ""
            card_set_name = card_set_name.lower() if card_set_name else ""
            
            # Era-based set categorization
            if "vintage" in gemini_era or "classic" in gemini_era:
                vintage_sets = ["base", "jungle", "fossil", "aquapolis", "skyridge", "expedition"]
                if card_set_name and any(vintage in card_set_name for vintage in vintage_sets):
                    score_breakdown["visual_era_match"] = 300
            elif "modern" in gemini_era:
                modern_indicators = ["xy", "sun", "moon", "sword", "shield", "scarlet", "violet"]
                if card_set_name and any(modern in card_set_name for modern in modern_indicators):
                    score_breakdown["visual_era_match"] = 300
        
        # Foil pattern matching (helps distinguish variants)
        if visual_features.get("foil_pattern"):
            foil_pattern = str(visual_features["foil_pattern"]).lower() if visual_features["foil_pattern"] else ""
            # This would require more detailed card data analysis
            # For now, give small bonus for any foil detection
            if any(word in foil_pattern for word in ["holo", "foil", "crystal", "rainbow", "cosmos"]):
                score_breakdown["visual_foil_match"] = 100
    
    total_score = sum(score_breakdown.values())
    return total_score, score_breakdown


def select_best_match(tcg_results: List[Dict[str, Any]], gemini_params: Dict[str, Any]) -> tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Select the best matching card from TCG results and return all scored matches.
    
    Args:
        tcg_results: List of card data from TCG API
        gemini_params: Parsed parameters from Gemini
        
    Returns:
        Tuple of (best_match_data, all_scored_matches)
    """
    if not tcg_results:
        return None, []
    
    best_score = -1
    best_match = None
    all_scored_matches = []
    
    for card_data in tcg_results:
        score, score_breakdown = calculate_match_score_detailed(card_data, gemini_params)
        
        match_info = {
            "card_data": card_data,
            "score": score,
            "score_breakdown": score_breakdown,
            "card_id": card_data.get("id"),
            "card_name": card_data.get("name"),
            "card_number": card_data.get("number"),
            "card_hp": card_data.get("hp"),
            "set_name": card_data.get("set", {}).get("name"),
            "types": card_data.get("types", []),
            "rarity": card_data.get("rarity"),
        }
        all_scored_matches.append(match_info)
        
        if score > best_score:
            best_score = score
            best_match = card_data
    
    # Advanced sorting with tie-breaking logic
    def advanced_sort_key(match):
        """
        Multi-criteria sorting for tie-breaking:
        1. Primary: Score (highest first)
        2. Tie-break 1: Exact number match bonus 
        3. Tie-break 2: Rarity priority (Rare > Uncommon > Common)
        4. Tie-break 3: Market price (higher value preferred)
        5. Tie-break 4: Card ID for consistency
        """
        score = match["score"]
        
        # Tie-break 1: Exact number match gets priority
        has_exact_number = match["score_breakdown"].get("number_exact", 0) > 0
        exact_number_bonus = 1000 if has_exact_number else 0
        
        # Tie-break 2: Rarity priority
        rarity = str(match.get("rarity") or "").lower()
        rarity_priority = {
            "rare": 300,
            "uncommon": 200, 
            "common": 100,
            "promo": 400,  # Promos often more valuable
            "secret rare": 500,
            "ultra rare": 450,
        }.get(rarity, 0)
        
        # Tie-break 3: Market price preference
        market_price = 0
        card_data = match["card_data"]
        if card_data.get("tcgplayer", {}).get("prices"):
            prices = card_data["tcgplayer"]["prices"]
            # Look for highest variant price
            for variant in ["holofoil", "normal", "reverseHolofoil"]:
                if variant in prices and prices[variant].get("market"):
                    market_price = max(market_price, prices[variant]["market"])
        
        # Tie-break 4: Card ID for consistency (lower = priority, usually means earlier/more common)
        card_id = match.get("card_id", "zzz")  # Default to low priority
        id_priority = -ord(card_id[0]) if card_id else 0  # Negative for reverse order
        
        return (score, exact_number_bonus, rarity_priority, market_price, id_priority)
    
    # Sort with advanced tie-breaking
    all_scored_matches.sort(key=advanced_sort_key, reverse=True)
    
    # Update best_match to the top result after advanced sorting
    if all_scored_matches:
        best_match = all_scored_matches[0]["card_data"]
        best_score = all_scored_matches[0]["score"]
    
    # Log the scoring details for debugging
    logger.info(f"🎯 Match scoring with tie-breaking (showing top 5):")
    for i, match in enumerate(all_scored_matches[:5]):
        exact_num = "✓" if match["score_breakdown"].get("number_exact", 0) > 0 else "✗"
        rarity = match.get("rarity", "Unknown")
        logger.info(f"   {i+1}. {match.get('card_name', 'Unknown')} #{match.get('card_number', '?')} - Score: {match['score']} | ExactNum: {exact_num} | Rarity: {rarity}")
        if match['score_breakdown']:
            breakdown_str = ", ".join([f"{k}: {v}" for k, v in match['score_breakdown'].items() if v > 0])
            logger.info(f"      Breakdown: {breakdown_str}")
    
    # Check if best match score meets minimum threshold
    if best_match:
        if best_score >= MINIMUM_SCORE_THRESHOLD:
            logger.info(f"✅ Selected best match after tie-breaking: {best_match.get('name')} #{best_match.get('number')} (Score: {best_score})")
        else:
            logger.info(f"❌ Best match score {best_score} below threshold {MINIMUM_SCORE_THRESHOLD}")
            logger.info(f"   📊 Highest scoring card: {best_match.get('name')} #{best_match.get('number')} from {best_match.get('set', {}).get('name')}")
            logger.info(f"   💡 This suggests no good matches found - likely card not in database or poor AI extraction")
            return None, all_scored_matches  # Return no match if score too low
    
    return best_match, all_scored_matches


def create_simplified_response(
    best_match: Optional[PokemonCard],
    processing_info: ProcessingInfo,
    gemini_analysis: Optional[GeminiAnalysis] = None
) -> SimplifiedScanResponse:
    """Create a simplified response from the scan results."""
    
    # If we have a best match from TCG, use that data
    if best_match:
        # Extract market prices - flatten the structure
        market_prices = None
        if best_match.market_prices:
            market_prices = {}
            # Handle different price structures
            if isinstance(best_match.market_prices, dict):
                # Check for card type variants (normal, holofoil, reverseHolofoil, etc.)
                price_data = None
                
                # Priority order for price variants
                for variant in ['normal', 'holofoil', 'reverseHolofoil', '1stEditionNormal', '1stEditionHolofoil']:
                    if variant in best_match.market_prices:
                        price_data = best_match.market_prices[variant]
                        break
                
                # If no variant found, check for direct price structure
                if not price_data and 'low' in best_match.market_prices:
                    price_data = best_match.market_prices
                
                # Extract prices from the data
                if price_data and isinstance(price_data, dict):
                    market_prices['low'] = price_data.get('low', 0)
                    market_prices['mid'] = price_data.get('mid', 0)
                    market_prices['high'] = price_data.get('high', 0)
                    market_prices['market'] = price_data.get('market', price_data.get('mid', 0))
        
        # Get image URL
        image_url = None
        if best_match.images:
            image_url = best_match.images.get('large') or best_match.images.get('small')
        
        return SimplifiedScanResponse(
            name=best_match.name,
            set_name=best_match.set_name,
            number=best_match.number,
            hp=best_match.hp,
            types=best_match.types,
            rarity=best_match.rarity,
            image=image_url,
            market_prices=market_prices,
            quality_score=processing_info.quality_score
        )
    
    # Fallback to Gemini data if no TCG match
    elif gemini_analysis and gemini_analysis.structured_data:
        data = gemini_analysis.structured_data
        return SimplifiedScanResponse(
            name=data.get('name', 'Unknown'),
            set_name=data.get('set_name'),
            number=data.get('number'),
            hp=data.get('hp'),
            types=data.get('types'),
            rarity=data.get('rarity'),
            image=None,  # No image from Gemini
            market_prices=None,  # No prices without TCG match
            quality_score=processing_info.quality_score
        )
    
    # Fallback response for cases where we have minimal data
    else:
        # Extract any available data from Gemini analysis
        name = "Unknown Card"
        if gemini_analysis and hasattr(gemini_analysis, 'raw_response'):
            # Try to extract at least a name from the raw response
            import re
            name_match = re.search(r'"name":\s*"([^"]+)"', gemini_analysis.raw_response)
            if name_match:
                name = name_match.group(1)
        
        return SimplifiedScanResponse(
            name=name,
            set_name=None,
            number=None,
            hp=None,
            types=None,
            rarity=None,
            image=None,
            market_prices=None,
            quality_score=processing_info.quality_score
        )


def parse_gemini_response(gemini_response: str) -> Dict[str, Any]:
    """
    Parse Gemini's response to extract structured TCG search parameters.
    
    Args:
        gemini_response: Raw text response from Gemini with TCG_SEARCH_START/END markers
        
    Returns:
        Dictionary with parsed search parameters
    """
    # First try to extract structured JSON from TCG_SEARCH markers
    tcg_pattern = r'TCG_SEARCH_START\s*(\{.*?\})\s*TCG_SEARCH_END'
    match = re.search(tcg_pattern, gemini_response, re.DOTALL | re.IGNORECASE)
    
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
                # Remove common artifacts
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
                    # CRITICAL: Correct XY-era set misidentification
                    is_xy_era = set_name.upper().startswith("XY") or set_name.upper() == "XY"
                    if is_xy_era and 'number' in search_params:
                        # Check if this might need correction based on number ranges and total count
                        card_number = str(search_params.get('number', '')).strip()
                        corrected_set = _correct_xy_set_based_on_number(card_number, search_params)
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
                extracted_set_name = _extract_set_name_from_symbol(set_symbol_desc)
                if extracted_set_name:
                    cleaned_params['set_name'] = extracted_set_name
                    logger.info(f"🔍 Extracted set name '{extracted_set_name}' from symbol description: '{set_symbol_desc}'")
            
            # Clean number
            if 'number' in search_params and search_params['number']:
                number = str(search_params['number']).strip()
                # Extract card number (preserve prefix letters like H in H11/H32)
                number_match = re.search(r'([A-Za-z]*\d+)', number)
                if number_match:
                    cleaned_params['number'] = number_match.group(1)
                else:
                    # Fallback: just clean whitespace if no standard pattern found
                    cleaned_params['number'] = number.split('/')[0].strip()
            
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


@router.post("/scan", responses={500: {"model": ErrorResponse}})
async def scan_pokemon_card(request: ScanRequest):
    """
    Scan a Pokemon card image and identify it using intelligent processing pipeline.
    
    This endpoint:
    1. Assesses image quality and routes to appropriate processing tier
    2. Uses optimized Gemini AI analysis based on quality score
    3. Searches the Pokemon TCG database for matches
    4. Returns comprehensive card information with quality metrics
    
    Processing time varies by quality: excellent (1s), good (1-2s), poor (2-4s).
    Cost: ~$0.003-0.005 per scan depending on processing tier.
    """
    start_time = time.time()
    cost_tracker = CostTracker()
    
    try:
        # Decode base64 image
        try:
            image_data = base64.b64decode(request.image)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 image data: {str(e)}")
        
        logger.info(f"🔍 Starting intelligent card scan for {request.filename or 'uploaded image'}")
        
        # Save original image for testing
        original_path = save_processed_image(image_data, request.filename or "image", "original")
        
        # Initialize processing pipeline
        gemini_service = GeminiService(api_key=config.google_api_key)
        processing_pipeline = ProcessingPipeline(gemini_service)
        
        # User preferences from request options
        user_preferences = {}
        if request.options.prefer_speed is not None:
            user_preferences['prefer_speed'] = request.options.prefer_speed
        if request.options.prefer_quality is not None:
            user_preferences['prefer_quality'] = request.options.prefer_quality
        if request.options.max_processing_time is not None:
            user_preferences['max_processing_time'] = request.options.max_processing_time
        
        # Run through processing pipeline
        pipeline_result = await processing_pipeline.process_image(
            image_data,
            request.filename or "image",
            user_preferences if user_preferences else None
        )
        
        if not pipeline_result['success']:
            # Extract quality feedback from pipeline error result
            quality_feedback = None
            if 'processing' in pipeline_result and 'quality_feedback' in pipeline_result['processing']:
                quality_feedback = pipeline_result['processing']['quality_feedback']
            
            # Return user-friendly error with quality feedback
            error_message = pipeline_result.get('error', 'Processing pipeline failed')
            error_detail = {
                "message": error_message,
                "error_type": "image_quality" if "quality too low" in error_message.lower() else "processing_failed",
            }
            
            if quality_feedback:
                error_detail["quality_feedback"] = quality_feedback
            
            raise HTTPException(
                status_code=400 if "quality too low" in pipeline_result.get('error', '').lower() else 500,
                detail=json.dumps(error_detail),
            )
        
        # Extract Gemini result and parse for TCG search
        gemini_data = pipeline_result.get('card_data')
        if not gemini_data:
            raise HTTPException(
                status_code=500,
                detail="Processing pipeline did not return card data",
            )
        
        # Check if Gemini processing was successful
        if not gemini_data.get('success', False):
            raise HTTPException(
                status_code=500,
                detail=f"Gemini processing failed: {gemini_data.get('error', 'Unknown error')}",
            )
        
        # Ensure response field exists before parsing
        if 'response' not in gemini_data:
            raise HTTPException(
                status_code=500,
                detail="Gemini response missing required data",
            )
        
        parsed_data = parse_gemini_response(gemini_data["response"])
        
        # Log the extracted parameters for debugging
        logger.info(f"🎯 Extracted TCG search parameters from Gemini:")
        logger.info(f"   📛 Name: '{parsed_data.get('name')}'")
        logger.info(f"   🏷️ Set: '{parsed_data.get('set_name')}'")
        logger.info(f"   🔢 Number: '{parsed_data.get('number')}'")
        logger.info(f"   ❤️ HP: '{parsed_data.get('hp')}'")
        logger.info(f"   🎨 Types: {parsed_data.get('types')}")
        
        # Create card type info object
        card_type_info = None
        if parsed_data.get("card_type_info"):
            from ..models.schemas import CardTypeInfo
            card_type_info = CardTypeInfo(**parsed_data["card_type_info"])
            
        # Create language info object
        language_info = None
        if parsed_data.get("language_info"):
            from ..models.schemas import LanguageInfo
            language_info = LanguageInfo(**parsed_data["language_info"])

        # Create Gemini analysis object
        gemini_analysis = GeminiAnalysis(
            raw_response=gemini_data["response"],
            structured_data=parsed_data,
            card_type_info=card_type_info,
            language_info=language_info,
            confidence=0.9 if parsed_data.get("name") else 0.5,
            tokens_used={
                "prompt": gemini_data.get("prompt_tokens", 0),
                "response": gemini_data.get("response_tokens", 0),
            },
        )
        
        # Track Gemini cost
        gemini_cost = 0.0
        if request.options.include_cost_tracking:
            gemini_cost = cost_tracker.track_gemini_usage(
                prompt_tokens=gemini_data.get("prompt_tokens", 0),
                response_tokens=gemini_data.get("response_tokens", 0),
                includes_image=True,
                operation="identify_card",
            )
        
        # Step 3: Search TCG database
        logger.info("🎯 Searching Pokemon TCG database...")
        logger.info(f"🔍 Search parameters: name='{parsed_data.get('name')}', set='{parsed_data.get('set_name')}', number='{parsed_data.get('number')}', hp='{parsed_data.get('hp')}'")
        tcg_start = time.time()
        
        tcg_client = PokemonTcgClient()
        tcg_matches = []
        search_attempts = []
        best_match_card = None
        all_match_scores = []  # Initialize here so it's always available
        
        if parsed_data.get("name"):
            all_search_results = []  # Collect results from all strategies
            
            # Strategy 1: HIGHEST PRIORITY - Set + Number + Name (exact match)
            if parsed_data.get("set_name") and parsed_data.get("number"):
                logger.info("🎯 Strategy 1: Set + Number + Name (PRIORITY)")
                logger.info(f"   🔍 Searching for: name='{parsed_data['name']}', set='{parsed_data.get('set_name')}', number='{parsed_data.get('number')}'")
                strategy1_results = await tcg_client.search_cards(
                    name=parsed_data["name"],
                    set_name=parsed_data.get("set_name"),
                    number=parsed_data.get("number"),
                    page_size=5,
                    fuzzy=False,
                )
                if strategy1_results.get("data"):
                    all_search_results.extend(strategy1_results["data"])
                    logger.info(f"✅ Strategy 1 found {len(strategy1_results['data'])} exact matches")
                    for result in strategy1_results["data"][:3]:  # Log first 3 matches
                        logger.info(f"   📄 Found: {result.get('name')} #{result.get('number')} from {result.get('set', {}).get('name')}")
                else:
                    logger.info("   ❌ Strategy 1: No exact matches found")
                
                search_attempts.append({
                    "strategy": "set_number_name_exact",
                    "query": {
                        "name": parsed_data["name"],
                        "set_name": parsed_data.get("set_name"),
                        "number": parsed_data.get("number"),
                    },
                    "results": len(strategy1_results.get("data", [])),
                })
                
                # Strategy 1.5: Set Family + Number + Name (for cases like "XY" -> "XY BREAKpoint")
                if len(all_search_results) == 0 and parsed_data.get("set_name") and parsed_data.get("number"):
                    set_family = _get_set_family(parsed_data.get("set_name"))
                    if set_family:
                        logger.info(f"🔄 Strategy 1.5: Set Family expansion for '{parsed_data.get('set_name')}'")
                        logger.info(f"   📚 Set family contains: {set_family}")
                        for family_set in set_family:
                            logger.info(f"   🔍 Searching in family set: '{family_set}'")
                            strategy1_5_results = await tcg_client.search_cards(
                                name=parsed_data["name"],
                                set_name=family_set,
                                number=parsed_data.get("number"),
                                page_size=3,
                                fuzzy=False,
                            )
                            if strategy1_5_results.get("data"):
                                new_results = [card for card in strategy1_5_results["data"] 
                                             if not any(existing["id"] == card["id"] for existing in all_search_results)]
                                all_search_results.extend(new_results)
                                logger.info(f"✅ Strategy 1.5 found {len(new_results)} matches in {family_set}")
                                for result in new_results[:2]:  # Log first 2 matches
                                    logger.info(f"   📄 Found: {result.get('name')} #{result.get('number')} from {result.get('set', {}).get('name')}")
                            else:
                                logger.info(f"   ❌ No matches in '{family_set}'")
                                
                        search_attempts.append({
                            "strategy": "set_family_number_name",
                            "query": {
                                "name": parsed_data["name"],
                                "set_family": set_family,
                                "number": parsed_data.get("number"),
                            },
                            "results": len([r for r in all_search_results if "strategy1_5" in str(r)]),
                        })
            
            # Strategy 2: Set + Name (without number constraint)
            if parsed_data.get("set_name"):
                logger.info("🔄 Strategy 2: Set + Name (no number)")
                logger.info(f"   🔍 Searching for: name='{parsed_data['name']}', set='{parsed_data.get('set_name')}'")
                strategy2_results = await tcg_client.search_cards(
                    name=parsed_data["name"],
                    set_name=parsed_data.get("set_name"),
                    page_size=10,
                    fuzzy=False,
                )
                if strategy2_results.get("data"):
                    # Only add if not already found in strategy 1
                    new_results = [card for card in strategy2_results["data"] 
                                 if not any(existing["id"] == card["id"] for existing in all_search_results)]
                    all_search_results.extend(new_results)
                    logger.info(f"✅ Strategy 2 found {len(new_results)} additional matches")
                    for result in new_results[:3]:  # Log first 3 new matches
                        logger.info(f"   📄 Found: {result.get('name')} #{result.get('number')} from {result.get('set', {}).get('name')}")
                else:
                    logger.info("   ❌ Strategy 2: No set+name matches found")
                
                search_attempts.append({
                    "strategy": "set_name_only",
                    "query": {
                        "name": parsed_data["name"],
                        "set_name": parsed_data.get("set_name"),
                    },
                    "results": len(strategy2_results.get("data", [])),
                })
            
            # Strategy 3: Name + HP (cross-set search with HP validation)
            if parsed_data.get("hp") and len(all_search_results) < 5:
                logger.info("🔄 Strategy 3: Name + HP (cross-set)")
                strategy3_results = await tcg_client.search_cards(
                    name=parsed_data["name"],
                    hp=parsed_data.get("hp"),
                    page_size=10,
                    fuzzy=False,
                )
                if strategy3_results.get("data"):
                    new_results = [card for card in strategy3_results["data"] 
                                 if not any(existing["id"] == card["id"] for existing in all_search_results)]
                    all_search_results.extend(new_results)
                    logger.info(f"✅ Strategy 3 found {len(new_results)} HP-matching cards")
                
                search_attempts.append({
                    "strategy": "name_hp_cross_set",
                    "query": {
                        "name": parsed_data["name"],
                        "hp": parsed_data.get("hp"),
                    },
                    "results": len(strategy3_results.get("data", [])),
                })
            
            # Strategy 4: Special case for Hidden Fates Shiny Vault numbers
            if parsed_data.get("set_name") == "Hidden Fates" and parsed_data.get("number") and len(all_search_results) < 3:
                logger.info("🔄 Strategy 4: Hidden Fates with SV prefix")
                sv_number = f"SV{parsed_data['number']}"
                strategy4_results = await tcg_client.search_cards(
                    name=parsed_data["name"],
                    set_name=parsed_data.get("set_name"),
                    number=sv_number,
                    page_size=5,
                    fuzzy=False,
                )
                if strategy4_results.get("data"):
                    new_results = [card for card in strategy4_results["data"] 
                                 if not any(existing["id"] == card["id"] for existing in all_search_results)]
                    all_search_results.extend(new_results)
                    logger.info(f"✅ Strategy 4 found {len(new_results)} SV-prefixed cards")
                
                search_attempts.append({
                    "strategy": "hidden_fates_sv_prefix",
                    "query": {
                        "name": parsed_data["name"],
                        "set_name": parsed_data.get("set_name"),
                        "number": sv_number,
                    },
                    "results": len(strategy4_results.get("data", [])),
                })
            
            # Strategy 5: Fallback - Name only (fuzzy search)
            if len(all_search_results) < 5:
                logger.info("🔄 Strategy 5: Fallback name-only (fuzzy)")
                strategy5_results = await tcg_client.search_cards(
                    name=parsed_data["name"],
                    page_size=15,
                    fuzzy=True,
                )
                if strategy5_results.get("data"):
                    new_results = [card for card in strategy5_results["data"] 
                                 if not any(existing["id"] == card["id"] for existing in all_search_results)]
                    all_search_results.extend(new_results[:10])  # Limit fallback results
                    logger.info(f"✅ Strategy 5 found {len(new_results[:10])} fallback matches")
                
                search_attempts.append({
                    "strategy": "fuzzy_name_only_fallback",
                    "query": {
                        "name": parsed_data["name"],
                    },
                    "results": len(strategy5_results.get("data", [])),
                })
            
            # Use combined results
            tcg_results = {"data": all_search_results}
            
            # Log search strategy results
            logger.info(f"📊 Search Strategy Summary:")
            for attempt in search_attempts:
                logger.info(f"   📊 {attempt['strategy']}: {attempt['results']} results")
            
            logger.info(f"🎯 Total combined search results: {len(all_search_results)} cards found")
            if all_search_results:
                logger.info(f"📋 Sample results:")
                for i, result in enumerate(all_search_results[:5]):  # Show first 5
                    logger.info(f"   {i+1}. {result.get('name')} #{result.get('number')} from {result.get('set', {}).get('name')}")
            
            # Convert to PokemonCard objects and find best match
            tcg_card_data = tcg_results.get("data", [])
            for card_data in tcg_card_data:
                tcg_matches.append(PokemonCard(
                    id=card_data["id"],
                    name=card_data["name"],
                    set_name=card_data.get("set", {}).get("name"),
                    number=card_data.get("number"),
                    types=card_data.get("types"),
                    hp=card_data.get("hp"),
                    rarity=card_data.get("rarity"),
                    images=card_data.get("images"),
                    market_prices=card_data.get("tcgplayer", {}).get("prices") if card_data.get("tcgplayer") else None,
                ))
            
            # Select the best match using intelligent scoring and get all matches
            best_match_data, all_scored_matches = select_best_match(tcg_card_data, parsed_data)
            
            # Check if no good match was found due to low scores
            if best_match_data is None and all_scored_matches:
                highest_score = all_scored_matches[0]["score"] if all_scored_matches else 0
                highest_card = all_scored_matches[0] if all_scored_matches else None
                
                logger.warning(f"❌ Card not found: Highest score {highest_score} below threshold {MINIMUM_SCORE_THRESHOLD}")
                if highest_card:
                    logger.info(f"   📊 Best candidate: {highest_card.get('card_name')} #{highest_card.get('card_number')} from {highest_card.get('set_name')}")
                
                error_detail = {
                    "message": "Card not found: No matching Pokemon cards found in database",
                    "error_type": "card_not_found",
                    "details": {
                        "highest_score": highest_score,
                        "required_score": MINIMUM_SCORE_THRESHOLD,
                        "score_gap": MINIMUM_SCORE_THRESHOLD - highest_score
                    },
                    "suggestions": [
                        "Try a clearer image with better lighting",
                        "Ensure the card is fully visible and centered",
                        "Make sure the image is not blurry or distorted",
                        "Check that it's a Pokemon trading card (not a different card game)"
                    ]
                }
                
                raise HTTPException(
                    status_code=404,
                    detail=json.dumps(error_detail)
                )
            
            best_match_card = None
            logger.info(f"📊 Processing {len(all_scored_matches)} scored matches for detailed response")
            
            # Process all scored matches
            for match_info in all_scored_matches:
                # Create PokemonCard object for this match
                card_data = match_info["card_data"]
                pokemon_card = PokemonCard(
                    id=card_data["id"],
                    name=card_data["name"],
                    set_name=card_data.get("set", {}).get("name"),
                    number=card_data.get("number"),
                    types=card_data.get("types"),
                    hp=card_data.get("hp"),
                    rarity=card_data.get("rarity"),
                    images=card_data.get("images"),
                    market_prices=card_data.get("tcgplayer", {}).get("prices") if card_data.get("tcgplayer") else None,
                )
                
                # Determine confidence level
                score = match_info["score"]
                if score >= 1500:
                    confidence = "high"
                elif score >= 500:
                    confidence = "medium"
                else:
                    confidence = "low"
                
                # Generate human-readable reasoning
                reasoning = []
                breakdown = match_info["score_breakdown"]
                
                # Show combination bonuses first (most important)
                if breakdown.get("set_number_name_triple"):
                    reasoning.append(f"🎯 PERFECT MATCH: Set+Number+Name (+{breakdown['set_number_name_triple']})")
                elif breakdown.get("set_number_combo"):
                    reasoning.append(f"🎯 STRONG MATCH: Set+Number (+{breakdown['set_number_combo']})")
                
                if breakdown.get("name_exact"):
                    reasoning.append(f"Exact name match (+{breakdown['name_exact']})")
                elif breakdown.get("name_partial"):
                    reasoning.append(f"Partial name match (+{breakdown['name_partial']})")
                if breakdown.get("number_exact"):
                    reasoning.append(f"Exact number match (+{breakdown['number_exact']})")
                elif breakdown.get("number_partial"):
                    reasoning.append(f"Partial number match (+{breakdown['number_partial']})")
                if breakdown.get("set_exact"):
                    reasoning.append(f"Exact set match (+{breakdown['set_exact']})")
                elif breakdown.get("set_partial"):
                    reasoning.append(f"Partial set match (+{breakdown['set_partial']})")
                if breakdown.get("hp_match"):
                    reasoning.append(f"HP match (+{breakdown['hp_match']})")
                if breakdown.get("type_matches"):
                    reasoning.append(f"Type matches (+{breakdown['type_matches']})")
                if breakdown.get("shiny_vault_bonus"):
                    reasoning.append(f"Shiny Vault bonus (+{breakdown['shiny_vault_bonus']})")
                if breakdown.get("visual_series_match"):
                    reasoning.append(f"🎨 Series match (+{breakdown['visual_series_match']})")
                if breakdown.get("visual_era_match"):
                    reasoning.append(f"🕰️ Era match (+{breakdown['visual_era_match']})")
                if breakdown.get("visual_foil_match"):
                    reasoning.append(f"✨ Foil match (+{breakdown['visual_foil_match']})")
                if breakdown.get("name_tag_team_penalty"):
                    reasoning.append(f"Tag team penalty ({breakdown['name_tag_team_penalty']})")
                if breakdown.get("number_mismatch_penalty"):
                    reasoning.append(f"❌ WRONG NUMBER ({breakdown['number_mismatch_penalty']})")
                
                match_score = MatchScore(
                    card=pokemon_card,
                    score=score,
                    score_breakdown=breakdown,
                    confidence=confidence,
                    reasoning=reasoning
                )
                all_match_scores.append(match_score)
            
            # Find best match card
            if best_match_data:
                # Find the corresponding PokemonCard object
                for card in tcg_matches:
                    if card.id == best_match_data["id"]:
                        best_match_card = card
                        break
            
            # Track TCG usage
            if request.options.include_cost_tracking and config.enable_cost_tracking:
                cost_tracker.track_tcg_usage("search")
        else:
            logger.info("⚠️ TCG search skipped - no Pokemon name identified")
        
        tcg_time = (time.time() - tcg_start) * 1000
        
        # Save processed image for testing
        processed_path = None
        if pipeline_result.get('processed_image_data'):
            processed_path = save_processed_image(
                pipeline_result['processed_image_data'], 
                request.filename or "image", 
                "processed"
            )
        
        # Build comprehensive processing info
        processing_metadata = pipeline_result['processing']
        quality_feedback = QualityFeedback(
            overall=processing_metadata['quality_feedback']['overall'],
            issues=processing_metadata['quality_feedback']['issues'],
            suggestions=processing_metadata['quality_feedback']['suggestions']
        )
        
        processing_info = ProcessingInfo(
            quality_score=processing_metadata['quality_score'],
            quality_feedback=quality_feedback,
            processing_tier=processing_metadata['processing_tier'],
            target_time_ms=processing_metadata['target_time_ms'],
            actual_time_ms=processing_metadata['actual_time_ms'] + tcg_time,  # Include TCG time
            model_used=processing_metadata['model_used'],
            image_enhanced=processing_metadata['image_enhanced'],
            performance_rating=processing_metadata['performance_rating'],
            timing_breakdown={
                **processing_metadata['timing_breakdown'],
                'tcg_search_ms': tcg_time
            },
            processing_log=processing_metadata['processing_log'] + [
                f"TCG search: {tcg_time:.1f}ms",
                f"Found {len(tcg_matches)} matches" if tcg_matches else "No TCG matches found"
            ]
        )
        
        # Prepare cost info
        cost_info = None
        if request.options.include_cost_tracking:
            cost_info = CostInfo(
                gemini_cost=gemini_cost,
                total_cost=gemini_cost,  # TCG API is free
                cost_breakdown={
                    "gemini_image": CostTracker.GEMINI_COSTS["image_processing"],
                    "gemini_tokens": gemini_cost - CostTracker.GEMINI_COSTS["image_processing"],
                    "tcg_api": 0.0,
                },
            )
        
        # Determine success based on card type and results
        scan_success = True
        error_message = None
        
        if card_type_info:
            card_type = card_type_info.card_type
            
            if card_type == "pokemon_front":
                # Pokemon front cards should have TCG matches
                scan_success = best_match_card is not None
                if not scan_success:
                    error_message = "Pokemon card identified but no TCG database matches found"
                    
            elif card_type == "pokemon_back":
                # Card back detected - return user-friendly error
                raise HTTPException(
                    status_code=400,
                    detail=json.dumps({
                        "message": "Card back detected. Please photograph the front of the card.",
                        "quality_feedback": {
                            "overall": processing_info.quality_feedback.overall,
                            "issues": ["Card back detected"],
                            "suggestions": ["Please photograph the front of the card to identify it"]
                        }
                    })
                )
                
            elif card_type == "non_pokemon":
                # Non-Pokemon card detected - return user-friendly error
                raise HTTPException(
                    status_code=400,
                    detail=json.dumps({
                        "message": "Non-Pokemon card detected. This scanner only supports Pokemon TCG cards.",
                        "quality_feedback": {
                            "overall": processing_info.quality_feedback.overall,
                            "issues": ["Non-Pokemon card detected"],
                            "suggestions": ["Please scan a Pokemon TCG card"]
                        }
                    })
                )
                
            elif card_type == "unknown":
                # Unknown cards - consider failed if no data extracted
                scan_success = parsed_data.get("name") is not None
                if not scan_success:
                    error_message = "Could not determine card type or extract card data"
        else:
            # Fallback to original logic if no card type info  
            scan_success = True  # Default to success for now

        # Prepare response
        response = ScanResponse(
            success=scan_success,
            card_identification=gemini_analysis,
            tcg_matches=tcg_matches if tcg_matches else None,
            all_tcg_matches=all_match_scores if all_match_scores else None,
            best_match=best_match_card,
            processing=processing_info,
            cost_info=cost_info,
            error=error_message,
        )
        
        logger.info(f"🔍 Response prepared: tcg_matches={len(tcg_matches) if tcg_matches else 0}, all_tcg_matches={len(all_match_scores) if all_match_scores else 0}")
        
        total_time = processing_info.actual_time_ms
        logger.info(
            f"✅ Intelligent scan complete in {total_time:.0f}ms "
            f"(tier: {processing_info.processing_tier}, "
            f"quality: {processing_info.quality_score:.1f})"
            f"{f', cost: ${gemini_cost:.6f}' if cost_info else ''}"
        )
        
        # Record metrics
        metrics_service = get_metrics_service()
        metrics_service.record_request(RequestMetrics(
            timestamp=datetime.now(),
            endpoint="/api/v1/scan",
            method="POST",
            status_code=200,
            processing_time_ms=total_time,
            image_size_bytes=len(image_data),
            gemini_cost=gemini_cost,
            tcg_matches=len(tcg_matches) if tcg_matches else 0,
        ))
        
        # Return simplified response if requested (default)
        if request.options.response_format != "detailed":
            return create_simplified_response(
                best_match=best_match_card,
                processing_info=processing_info,
                gemini_analysis=gemini_analysis
            )
        
        # Return detailed response if explicitly requested
        return response
        
    except HTTPException as e:
        # Log and send webhook for HTTP errors
        error_context = {
            "status_code": e.status_code,
            "filename": request.filename,
            "processing_time_ms": int((time.time() - start_time) * 1000),
        }
        
        # Send webhook notification for critical errors
        if e.status_code >= 500:
            await send_error_webhook(
                error_message=f"HTTP {e.status_code}: {e.detail}",
                level="ERROR",
                endpoint="/api/v1/scan",
                context=error_context,
            )
        
        raise
    except Exception as e:
        logger.error(f"❌ Card scan failed: {str(e)}")
        
        # Calculate total time even on error
        total_time = (time.time() - start_time) * 1000
        
        # Prepare error context
        error_context = {
            "filename": request.filename,
            "processing_time_ms": int(total_time),
            "error_type": type(e).__name__,
        }
        
        # Send webhook notification
        await send_error_webhook(
            error_message=f"Card scan failed: {str(e)}",
            level="ERROR",
            endpoint="/api/v1/scan",
            context=error_context,
            traceback=str(e),
        )
        
        # Record error metrics
        metrics_service = get_metrics_service()
        metrics_service.record_request(RequestMetrics(
            timestamp=datetime.now(),
            endpoint="/api/v1/scan",
            method="POST",
            status_code=500,
            processing_time_ms=total_time,
            image_size_bytes=len(image_data) if 'image_data' in locals() else None,
            error_type=type(e).__name__,
        ))
        
        # Create minimal processing info for error response
        quality_feedback = QualityFeedback(
            overall="unknown",
            issues=["Processing failed"],
            suggestions=["Try uploading a different image"]
        )
        
        processing_info_obj = ProcessingInfo(
            quality_score=0.0,
            quality_feedback=quality_feedback,
            processing_tier="failed",
            target_time_ms=2000,
            actual_time_ms=total_time,
            model_used="none",
            image_enhanced=False,
            performance_rating="failed",
            timing_breakdown={"error_ms": total_time},
            processing_log=[f"Error: {str(e)}"]
        )
        
        return ScanResponse(
            success=False,
            error=str(e),
            processing=processing_info_obj,
        )


@router.get("/processed-images/list")
async def list_processed_images():
    """
    List all processed images for testing purposes.
    
    Returns a list of available processed images with metadata.
    """
    try:
        processed_dir = Path("processed_images")
        if not processed_dir.exists():
            return {"images": []}
        
        images = []
        for image_file in processed_dir.glob("*.jpg"):
            try:
                stat = image_file.stat()
                # Parse filename to extract info
                parts = image_file.stem.split('_')
                if len(parts) >= 3:
                    name = '_'.join(parts[:-2])  # Everything except stage and timestamp
                    stage = parts[-2]
                    timestamp = parts[-1]
                else:
                    name = image_file.stem
                    stage = "unknown"
                    timestamp = ""
                
                images.append({
                    "filename": image_file.name,
                    "path": str(image_file),
                    "url": f"/api/v1/processed-images/{image_file.name}",
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "stage": stage,
                    "original_name": name,
                    "timestamp": timestamp,
                })
            except Exception as e:
                logger.warning(f"Error processing image file {image_file}: {e}")
                continue
        
        # Sort by modification time, newest first
        images.sort(key=lambda x: x["modified"], reverse=True)
        
        return {"images": images}
        
    except Exception as e:
        logger.error(f"Error listing processed images: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/processed-images/{filename}")
async def get_processed_image(filename: str):
    """
    Serve a processed image file.
    
    Args:
        filename: Name of the image file to serve
        
    Returns:
        The image file
    """
    try:
        processed_dir = Path("processed_images")
        file_path = processed_dir / filename
        
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="Image not found")
        
        # Verify it's actually an image file
        if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            raise HTTPException(status_code=400, detail="Invalid image file type")
        
        return FileResponse(
            path=str(file_path),
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=3600"}  # Cache for 1 hour
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving image {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


