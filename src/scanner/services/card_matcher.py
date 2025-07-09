"""Card matching service for Pokemon card scanner."""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def get_set_family(set_name: str) -> Optional[List[str]]:
    """
    Map generic set names to their specific family expansions.

    Args:
        set_name: The set name to expand

    Returns:
        List of related set names or None if no expansion needed
    """
    if not set_name:
        return None

    set_name_lower = set_name.lower()

    # Comprehensive set family mapping
    set_families = {
        "base": ["Base Set", "Base", "Base Set 2"],
        "base set": ["Base Set", "Base", "Base Set 2"],
        "gym": ["Gym Heroes", "Gym Challenge"],
        "neo": ["Neo Genesis", "Neo Discovery", "Neo Destiny", "Neo Revelation"],
        "legendary": ["Legendary Collection"],
        "expedition": ["Expedition", "Expedition Base Set"],
        "aquapolis": ["Aquapolis"],
        "skyridge": ["Skyridge"],
        "ruby": ["Ruby & Sapphire"],
        "sapphire": ["Ruby & Sapphire"],
        "ruby & sapphire": ["Ruby & Sapphire"],
        "sandstorm": ["Sandstorm"],
        "dragon": ["Dragon"],
        "team magma": ["Team Magma vs Team Aqua"],
        "team aqua": ["Team Magma vs Team Aqua"],
        "hidden legends": ["Hidden Legends"],
        "firered": ["FireRed & LeafGreen"],
        "leafgreen": ["FireRed & LeafGreen"],
        "firered & leafgreen": ["FireRed & LeafGreen"],
        "team rocket": ["Team Rocket Returns"],
        "deoxys": ["Deoxys"],
        "emerald": ["Emerald"],
        "unseen forces": ["Unseen Forces"],
        "delta species": ["Delta Species"],
        "legend maker": ["Legend Maker"],
        "holon phantoms": ["Holon Phantoms"],
        "crystal guardians": ["Crystal Guardians"],
        "dragon frontiers": ["Dragon Frontiers"],
        "power keepers": ["Power Keepers"],
        "diamond": ["Diamond & Pearl"],
        "pearl": ["Diamond & Pearl"],
        "diamond & pearl": ["Diamond & Pearl"],
        "mysterious treasures": ["Mysterious Treasures"],
        "secret wonders": ["Secret Wonders"],
        "great encounters": ["Great Encounters"],
        "majestic dawn": ["Majestic Dawn"],
        "legends awakened": ["Legends Awakened"],
        "stormfront": ["Stormfront"],
        "platinum": ["Platinum"],
        "rising rivals": ["Rising Rivals"],
        "supreme victors": ["Supreme Victors"],
        "arceus": ["Arceus"],
        "heartgold": ["HeartGold & SoulSilver"],
        "soulsilver": ["HeartGold & SoulSilver"],
        "heartgold & soulsilver": ["HeartGold & SoulSilver"],
        "unleashed": ["Unleashed"],
        "undaunted": ["Undaunted"],
        "triumphant": ["Triumphant"],
        "call of legends": ["Call of Legends"],
        "black": ["Black & White"],
        "white": ["Black & White"],
        "black & white": ["Black & White"],
        "emerging powers": ["Emerging Powers"],
        "noble victories": ["Noble Victories"],
        "next destinies": ["Next Destinies"],
        "dark explorers": ["Dark Explorers"],
        "dragons exalted": ["Dragons Exalted"],
        "boundaries crossed": ["Boundaries Crossed"],
        "plasma storm": ["Plasma Storm"],
        "plasma freeze": ["Plasma Freeze"],
        "plasma blast": ["Plasma Blast"],
        "legendary treasures": ["Legendary Treasures"],
        "xy": ["XY"],
        "flashfire": ["Flashfire"],
        "furious fists": ["Furious Fists"],
        "phantom forces": ["Phantom Forces"],
        "primal clash": ["Primal Clash"],
        "roaring skies": ["Roaring Skies"],
        "ancient origins": ["Ancient Origins"],
        "breakthrough": ["BREAKthrough"],
        "breakpoint": ["BREAKpoint"],
        "generations": ["Generations"],
        "fates collide": ["Fates Collide"],
        "steam siege": ["Steam Siege"],
        "evolutions": ["Evolutions"],
        "sun": ["Sun & Moon"],
        "moon": ["Sun & Moon"],
        "sun & moon": ["Sun & Moon"],
        "guardians rising": ["Guardians Rising"],
        "burning shadows": ["Burning Shadows"],
        "shining legends": ["Shining Legends"],
        "crimson invasion": ["Crimson Invasion"],
        "ultra prism": ["Ultra Prism"],
        "forbidden light": ["Forbidden Light"],
        "celestial storm": ["Celestial Storm"],
        "dragon majesty": ["Dragon Majesty"],
        "lost thunder": ["Lost Thunder"],
        "team up": ["Team Up"],
        "detective pikachu": ["Detective Pikachu"],
        "unbroken bonds": ["Unbroken Bonds"],
        "unified minds": ["Unified Minds"],
        "hidden fates": ["Hidden Fates"],
        "cosmic eclipse": ["Cosmic Eclipse"],
        "sword": ["Sword & Shield"],
        "shield": ["Sword & Shield"],
        "sword & shield": ["Sword & Shield"],
        "rebel clash": ["Rebel Clash"],
        "darkness ablaze": ["Darkness Ablaze"],
        "champions path": ["Champion's Path"],
        "vivid voltage": ["Vivid Voltage"],
        "shining fates": ["Shining Fates"],
        "battle styles": ["Battle Styles"],
        "chilling reign": ["Chilling Reign"],
        "evolving skies": ["Evolving Skies"],
        "celebrations": ["Celebrations"],
        "fusion strike": ["Fusion Strike"],
        "brilliant stars": ["Brilliant Stars"],
        "astral radiance": ["Astral Radiance"],
        "pokemon go": ["Pokémon GO"],
        "lost origin": ["Lost Origin"],
        "silver tempest": ["Silver Tempest"],
        "crown zenith": ["Crown Zenith"],
        "scarlet": ["Scarlet & Violet"],
        "violet": ["Scarlet & Violet"],
        "scarlet & violet": ["Scarlet & Violet"],
        "paldea evolved": ["Paldea Evolved"],
        "obsidian flames": ["Obsidian Flames"],
        "151": ["151"],
        "paradox rift": ["Paradox Rift"],
        "paldean fates": ["Paldean Fates"],
        "temporal forces": ["Temporal Forces"],
        "twilight masquerade": ["Twilight Masquerade"],
        "shrouded fable": ["Shrouded Fable"],
        "stellar crown": ["Stellar Crown"],
        "surging sparks": ["Surging Sparks"],
    }

    return set_families.get(set_name_lower)


def is_xy_family_match(gemini_set: str, card_set: str) -> bool:
    """
    Check if two sets are both from the XY family and could be confused.

    Args:
        gemini_set: Set name from Gemini analysis
        card_set: Set name from card data

    Returns:
        True if both sets are from XY family
    """
    if not gemini_set or not card_set:
        return False

    xy_sets = {
        'xy', 'xy base', 'xy base set', 'kalos starter set',
        'flashfire', 'furious fists', 'phantom forces', 'primal clash',
        'roaring skies', 'ancient origins', 'breakthrough', 'breakpoint',
        'generations', 'fates collide', 'steam siege', 'evolutions'
    }

    gemini_lower = gemini_set.lower().strip()
    card_lower = card_set.lower().strip()

    return gemini_lower in xy_sets and card_lower in xy_sets


def get_set_from_total_count(total_count: int) -> Optional[str]:
    """
    Get the likely set name based on total card count.

    Args:
        total_count: Total number of cards in the set

    Returns:
        Most likely set name or None if count doesn't match known sets
    """
    # Map total counts to set names (focusing on sets that might be confused)
    count_to_set = {
        102: "Base Set",
        130: "Base Set 2",
        # Both Gym Heroes and Gym Challenge have 132 cards, so we can't reliably distinguish by count
        111: "Neo Genesis",
        75: "Neo Discovery",
        64: "Neo Revelation",
        105: "Neo Destiny",
        110: "Legendary Collection",
        165: "Expedition",
        147: "Aquapolis",
        144: "Skyridge",
        109: "Ruby & Sapphire",
        100: "Sandstorm",
        97: "Dragon",
        95: "Team Magma vs Team Aqua",
        101: "Hidden Legends",
        116: "FireRed & LeafGreen",
        111: "Team Rocket Returns",
        107: "Deoxys",
        106: "Emerald",
        115: "Unseen Forces",
        113: "Delta Species",
        92: "Legend Maker",
        110: "Holon Phantoms",
        100: "Crystal Guardians",
        101: "Dragon Frontiers",
        108: "Power Keepers",
        130: "Diamond & Pearl",
        123: "Mysterious Treasures",
        132: "Secret Wonders",
        106: "Great Encounters",
        100: "Majestic Dawn",
        146: "Legends Awakened",
        106: "Stormfront",
        127: "Platinum",
        111: "Rising Rivals",
        153: "Supreme Victors",
        99: "Arceus",
        123: "HeartGold & SoulSilver",
        95: "Unleashed",
        90: "Undaunted",
        102: "Triumphant",
        95: "Call of Legends",
        114: "Black & White",
        98: "Emerging Powers",
        101: "Noble Victories",
        99: "Next Destinies",
        108: "Dark Explorers",
        124: "Dragons Exalted",
        149: "Boundaries Crossed",
        135: "Plasma Storm",
        116: "Plasma Freeze",
        101: "Plasma Blast",
        140: "Legendary Treasures",
        146: "XY",
        106: "Flashfire",
        111: "Furious Fists",
        119: "Phantom Forces",
        160: "Primal Clash",
        108: "Roaring Skies",
        98: "Ancient Origins",
        162: "BREAKthrough",
        122: "BREAKpoint",
        115: "Generations",
        124: "Fates Collide",
        114: "Steam Siege",
        108: "Evolutions",
        149: "Sun & Moon",
        145: "Guardians Rising",
        147: "Burning Shadows",
        78: "Shining Legends",
        111: "Crimson Invasion",
        156: "Ultra Prism",
        131: "Forbidden Light",
        168: "Celestial Storm",
        70: "Dragon Majesty",
        214: "Lost Thunder",
        181: "Team Up",
        26: "Detective Pikachu",
        196: "Unbroken Bonds",
        236: "Unified Minds",
        68: "Hidden Fates",
        271: "Cosmic Eclipse",
        202: "Sword & Shield",
        192: "Rebel Clash",
        189: "Darkness Ablaze",
        73: "Champion's Path",
        185: "Vivid Voltage",
        72: "Shining Fates",
        163: "Battle Styles",
        198: "Chilling Reign",
        203: "Evolving Skies",
        25: "Celebrations",
        264: "Fusion Strike",
        174: "Brilliant Stars",
        189: "Astral Radiance",
        71: "Pokémon GO",
        196: "Lost Origin",
        195: "Silver Tempest",
        159: "Crown Zenith",
        198: "Scarlet & Violet",
        193: "Paldea Evolved",
        197: "Obsidian Flames",
        207: "151",
        182: "Paradox Rift",
        91: "Paldean Fates",
        162: "Temporal Forces",
        167: "Twilight Masquerade",
        64: "Shrouded Fable",
        142: "Stellar Crown",
        191: "Surging Sparks",
    }

    return count_to_set.get(total_count)


def correct_set_based_on_number_pattern(set_name: str, card_number: str) -> Optional[str]:
    """
    Correct set name based on card number patterns.

    Args:
        set_name: Original set name
        card_number: Card number to analyze

    Returns:
        Corrected set name or None if no correction needed
    """
    if not set_name or not card_number:
        return None

    # Extract numeric part from card number (e.g., "H11" -> 11, "177a" -> 177)
    number_match = re.search(r'(\d+)', card_number)
    if not number_match:
        return None

    number = int(number_match.group(1))
    set_lower = set_name.lower()

    # Set-specific corrections based on number ranges
    corrections = {
        # Base Set vs Base Set 2
        ("base set", lambda n: n > 102): "Base Set 2",
        ("base set 2", lambda n: n <= 102): "Base Set",

        # XY series corrections
        ("xy", lambda n: 107 <= n <= 146): "XY",
        ("flashfire", lambda n: 1 <= n <= 106): "Flashfire",
        ("furious fists", lambda n: 1 <= n <= 111): "Furious Fists",
        ("phantom forces", lambda n: 1 <= n <= 119): "Phantom Forces",
        ("primal clash", lambda n: 1 <= n <= 160): "Primal Clash",
        ("roaring skies", lambda n: 1 <= n <= 108): "Roaring Skies",
        ("ancient origins", lambda n: 1 <= n <= 98): "Ancient Origins",
        ("breakthrough", lambda n: 1 <= n <= 162): "BREAKthrough",
        ("breakpoint", lambda n: 1 <= n <= 122): "BREAKpoint",
        ("fates collide", lambda n: 1 <= n <= 124): "Fates Collide",
        ("steam siege", lambda n: 1 <= n <= 114): "Steam Siege",
        ("evolutions", lambda n: 1 <= n <= 108): "Evolutions",

        # Sun & Moon series
        ("sun & moon", lambda n: 1 <= n <= 149): "Sun & Moon",
        ("guardians rising", lambda n: 1 <= n <= 145): "Guardians Rising",
        ("burning shadows", lambda n: 1 <= n <= 147): "Burning Shadows",
        ("crimson invasion", lambda n: 1 <= n <= 111): "Crimson Invasion",
        ("ultra prism", lambda n: 1 <= n <= 156): "Ultra Prism",
        ("forbidden light", lambda n: 1 <= n <= 131): "Forbidden Light",
        ("celestial storm", lambda n: 1 <= n <= 168): "Celestial Storm",
        ("lost thunder", lambda n: 1 <= n <= 214): "Lost Thunder",

        # Sword & Shield series
        ("sword & shield", lambda n: 1 <= n <= 202): "Sword & Shield",
        ("rebel clash", lambda n: 1 <= n <= 192): "Rebel Clash",
        ("darkness ablaze", lambda n: 1 <= n <= 189): "Darkness Ablaze",
        ("vivid voltage", lambda n: 1 <= n <= 185): "Vivid Voltage",
        ("battle styles", lambda n: 1 <= n <= 163): "Battle Styles",
        ("chilling reign", lambda n: 1 <= n <= 198): "Chilling Reign",
        ("evolving skies", lambda n: 1 <= n <= 203): "Evolving Skies",
        ("fusion strike", lambda n: 1 <= n <= 264): "Fusion Strike",
        ("brilliant stars", lambda n: 1 <= n <= 174): "Brilliant Stars",
        ("astral radiance", lambda n: 1 <= n <= 189): "Astral Radiance",
        ("lost origin", lambda n: 1 <= n <= 196): "Lost Origin",
        ("silver tempest", lambda n: 1 <= n <= 195): "Silver Tempest",

        # Scarlet & Violet series
        ("scarlet & violet", lambda n: 1 <= n <= 198): "Scarlet & Violet",
        ("paldea evolved", lambda n: 1 <= n <= 193): "Paldea Evolved",
        ("obsidian flames", lambda n: 1 <= n <= 197): "Obsidian Flames",
        ("paradox rift", lambda n: 1 <= n <= 182): "Paradox Rift",
        ("temporal forces", lambda n: 1 <= n <= 162): "Temporal Forces",
        ("twilight masquerade", lambda n: 1 <= n <= 167): "Twilight Masquerade",
        ("stellar crown", lambda n: 1 <= n <= 142): "Stellar Crown",
        ("surging sparks", lambda n: 1 <= n <= 191): "Surging Sparks",
    }

    for (set_key, condition), correction in corrections.items():
        if set_lower == set_key and condition(number):
            return correction

    return None


def correct_xy_set_based_on_number(card_number: str, search_params: Dict[str, Any]) -> Optional[str]:
    """
    Specifically correct XY set names based on card number and additional context.

    Args:
        card_number: Card number to analyze
        search_params: Additional search parameters for context

    Returns:
        Corrected XY set name or None
    """
    if not card_number:
        return None

    # Extract numeric part
    number_match = re.search(r'(\d+)', card_number)
    if not number_match:
        return None

    number = int(number_match.group(1))

    # XY set number ranges (more specific than general correction)
    xy_ranges = {
        (1, 39): "XY",
        (40, 79): "XY",  # XY base set range
        (80, 106): "Flashfire",
        (107, 146): "XY",  # XY promos/special cards
        (1, 111): "Furious Fists",
        (1, 119): "Phantom Forces",
        (1, 160): "Primal Clash",
        (1, 108): "Roaring Skies",
        (1, 98): "Ancient Origins",
        (1, 162): "BREAKthrough",
        (1, 122): "BREAKpoint",
        (1, 124): "Fates Collide",
        (1, 114): "Steam Siege",
        (1, 108): "Evolutions",
    }

    # Check if we have additional context from search params
    name = search_params.get("name", "").lower()
    types = search_params.get("types", [])
    hp = search_params.get("hp", "")

    # Use number ranges with context
    for (min_num, max_num), suggested_set in xy_ranges.items():
        if min_num <= number <= max_num:
            # Add more logic here if needed based on other parameters
            return suggested_set

    return None


def extract_set_name_from_symbol(set_symbol_desc: str) -> Optional[str]:
    """
    Extract set name from set symbol description.

    Args:
        set_symbol_desc: Description of the set symbol

    Returns:
        Extracted set name or None
    """
    if not set_symbol_desc:
        return None

    symbol_lower = set_symbol_desc.lower().strip()

    # Common symbol description to set name mappings
    symbol_mappings = {
        # Base sets
        "base set": "Base Set",
        "base": "Base Set",
        "base 2": "Base Set 2",
        "base set 2": "Base Set 2",

        # Gym sets
        "gym heroes": "Gym Heroes",
        "gym challenge": "Gym Challenge",

        # Neo sets
        "neo genesis": "Neo Genesis",
        "neo discovery": "Neo Discovery",
        "neo revelation": "Neo Revelation",
        "neo destiny": "Neo Destiny",

        # Modern sets
        "xy": "XY",
        "flashfire": "Flashfire",
        "furious fists": "Furious Fists",
        "phantom forces": "Phantom Forces",
        "primal clash": "Primal Clash",
        "roaring skies": "Roaring Skies",
        "ancient origins": "Ancient Origins",
        "breakthrough": "BREAKthrough",
        "breakpoint": "BREAKpoint",
        "fates collide": "Fates Collide",
        "steam siege": "Steam Siege",
        "evolutions": "Evolutions",

        # Sun & Moon
        "sun & moon": "Sun & Moon",
        "guardians rising": "Guardians Rising",
        "burning shadows": "Burning Shadows",
        "shining legends": "Shining Legends",
        "crimson invasion": "Crimson Invasion",
        "ultra prism": "Ultra Prism",
        "forbidden light": "Forbidden Light",
        "celestial storm": "Celestial Storm",
        "dragon majesty": "Dragon Majesty",
        "lost thunder": "Lost Thunder",
        "team up": "Team Up",
        "detective pikachu": "Detective Pikachu",
        "unbroken bonds": "Unbroken Bonds",
        "unified minds": "Unified Minds",
        "hidden fates": "Hidden Fates",
        "cosmic eclipse": "Cosmic Eclipse",

        # Sword & Shield
        "sword & shield": "Sword & Shield",
        "rebel clash": "Rebel Clash",
        "darkness ablaze": "Darkness Ablaze",
        "champion's path": "Champion's Path",
        "vivid voltage": "Vivid Voltage",
        "shining fates": "Shining Fates",
        "battle styles": "Battle Styles",
        "chilling reign": "Chilling Reign",
        "evolving skies": "Evolving Skies",
        "celebrations": "Celebrations",
        "fusion strike": "Fusion Strike",
        "brilliant stars": "Brilliant Stars",
        "astral radiance": "Astral Radiance",
        "pokemon go": "Pokémon GO",
        "lost origin": "Lost Origin",
        "silver tempest": "Silver Tempest",
        "crown zenith": "Crown Zenith",

        # Scarlet & Violet
        "scarlet & violet": "Scarlet & Violet",
        "paldea evolved": "Paldea Evolved",
        "obsidian flames": "Obsidian Flames",
        "151": "151",
        "paradox rift": "Paradox Rift",
        "paldean fates": "Paldean Fates",
        "temporal forces": "Temporal Forces",
        "twilight masquerade": "Twilight Masquerade",
        "shrouded fable": "Shrouded Fable",
        "stellar crown": "Stellar Crown",
        "surging sparks": "Surging Sparks",
    }

    # Try exact match first
    if symbol_lower in symbol_mappings:
        return symbol_mappings[symbol_lower]

    # Try partial matches
    for symbol_key, set_name in symbol_mappings.items():
        if symbol_key in symbol_lower or symbol_lower in symbol_key:
            return set_name

    return None


def is_pokemon_variant_match(gemini_name: str, card_name: str) -> bool:
    """
    Check if two Pokemon names represent the same Pokemon with variants.

    Args:
        gemini_name: Pokemon name from Gemini analysis
        card_name: Pokemon name from card data

    Returns:
        True if they represent the same Pokemon (considering variants)
    """
    if not gemini_name or not card_name:
        return False

    # Normalize names for comparison
    def normalize_name(name: str) -> str:
        return re.sub(r'\s+', ' ', name.lower().strip())

    gemini_clean = normalize_name(gemini_name)
    card_clean = normalize_name(card_name)

    # Exact match
    if gemini_clean == card_clean:
        return True

    # Remove common variant suffixes and prefixes
    variant_patterns = [
        r'\s+v$',  # " V"
        r'\s+vmax$',  # " VMAX"
        r'\s+vstar$',  # " VSTAR"
        r'\s+ex$',  # " ex"
        r'\s+gx$',  # " GX"
        r'\s+break$',  # " BREAK"
        r'\s+prime$',  # " Prime"
        r'\s+lv\.?\s*x?$',  # " LV.X"
        r'\s+\d+$',  # Numbers at end like " 1", " 2"
        r'\s+delta$',  # " Delta"
        r'\s+star$',  # " ⭐" or " Star"
        r'\s+dark$',  # "Dark "
        r'^dark\s+',  # "Dark " at start
        r'\s+light$',  # "Light "
        r'^light\s+',  # "Light " at start
        r'\s+shining$',  # "Shining "
        r'^shining\s+',  # "Shining " at start
        r'\s+crystal$',  # "Crystal "
        r'^crystal\s+',  # "Crystal " at start
        r'\s+\([^)]+\)$',  # Parenthetical info like " (Team Plasma)"
        r'\s+team\s+plasma$',  # " Team Plasma"
        r'\s+plasma$',  # " Plasma"
    ]

    # Clean both names
    gemini_base = gemini_clean
    card_base = card_clean

    for pattern in variant_patterns:
        gemini_base = re.sub(pattern, '', gemini_base, flags=re.IGNORECASE)
        card_base = re.sub(pattern, '', card_base, flags=re.IGNORECASE)

    # Check if base names match
    if gemini_base.strip() == card_base.strip():
        return True

    # Handle specific Pokemon with common naming variations
    name_variations = {
        "nidoran♀": ["nidoran f", "nidoran female", "nidoran (f)"],
        "nidoran♂": ["nidoran m", "nidoran male", "nidoran (m)"],
        "mr. mime": ["mr mime", "mrmime"],
        "mime jr.": ["mime jr", "mimejr"],
        "farfetch'd": ["farfetchd", "farfetch d"],
        "ho-oh": ["ho oh", "hooh"],
        "porygon-z": ["porygon z", "porygonz"],
        "jangmo-o": ["jangmo o", "jangmoo"],
        "hakamo-o": ["hakamo o", "hakamoo"],
        "kommo-o": ["kommo o", "kommoo"],
        "tapu koko": ["tapukoko"],
        "tapu lele": ["tapulele"],
        "tapu bulu": ["tapubulu"],
        "tapu fini": ["tapufini"],
        "type: null": ["type null", "typenull"],
        "sirfetch'd": ["sirfetchd", "sirfetch d"],
        "mr. rime": ["mr rime", "mrrime"],
    }

    # Check name variations
    gemini_final = gemini_base.strip()
    card_final = card_base.strip()

    for canonical, variations in name_variations.items():
        # Check if one is canonical and other is variation
        if gemini_final == canonical and card_final in variations:
            return True
        if card_final == canonical and gemini_final in variations:
            return True
        # Check if both are variations of the same canonical name
        if gemini_final in variations and card_final in variations:
            return True

    # Handle Pokémon forms and regional variants
    form_patterns = [
        (r'(.+)\s+alola', r'\1 alolan'),
        (r'(.+)\s+galar', r'\1 galarian'),
        (r'(.+)\s+hisui', r'\1 hisuian'),
        (r'(.+)\s+paldea', r'\1 paldean'),
        (r'(.+)\s+forme?', r'\1'),
        (r'(.+)\s+form', r'\1'),
    ]

    for pattern, replacement in form_patterns:
        gemini_form = re.sub(pattern, replacement, gemini_final, flags=re.IGNORECASE)
        card_form = re.sub(pattern, replacement, card_final, flags=re.IGNORECASE)
        if gemini_form == card_form:
            return True

    return False


def calculate_match_score(card_data: Dict[str, Any], gemini_params: Dict[str, Any]) -> int:
    """
    Calculate match score for a TCG card based on Gemini parameters.

    Args:
        card_data: Card data from TCG API
        gemini_params: Parameters extracted from Gemini analysis

    Returns:
        Match score (higher is better)
    """
    score, _ = calculate_match_score_detailed(card_data, gemini_params)
    return score


def calculate_match_score_detailed(card_data: Dict[str, Any], gemini_params: Dict[str, Any]) -> tuple[int, Dict[str, int]]:
    """
    Calculate match score with detailed breakdown for transparency.
    CRITICAL: Set + Number + Name combinations get MASSIVE priority over name-only matches.

    Returns:
        Tuple of (total_score, score_breakdown_dict)
    """
    score_breakdown = {
        "set_number_name_triple": 0,
        "set_number_combo": 0,
        "name_exact": 0,
        "name_variant_match": 0,
        "name_partial": 0,
        "name_tag_team_penalty": 0,
        "number_exact": 0,
        "number_partial": 0,
        "number_mismatch_penalty": 0,
        "hp_match": 0,
        "type_matches": 0,
        "set_exact": 0,
        "set_partial": 0,
        "set_family_match": 0,
        "set_size_exact": 0,
        "set_size_close": 0,
        "shiny_vault_bonus": 0,
        "visual_series_match": 0,
        "visual_era_match": 0,
        "visual_foil_match": 0,
        "prime_card_match": 0,
        "prime_vs_regular_penalty": 0,
        "missed_prime_penalty": 0,
        "type_perfect_match": 0,
        "type_ai_complete_match": 0,
        "type_partial_match": 0,
        "type_mismatch_penalty": 0,
        "type_missing_penalty": 0,
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
            score_breakdown["set_exact"] = 2000
        elif gemini_set in card_set or card_set in gemini_set:
            # Special handling for XY family sets
            if is_xy_family_match(gemini_set, card_set):
                # Within XY family but not exact match - moderate bonus instead of penalty
                score_breakdown["set_family_match"] = 800
                logger.debug(f"      XY family match: {gemini_set} <-> {card_set}")
            else:
                score_breakdown["set_partial"] = 500

    # Card number match check
    if gemini_params.get("number") and card_data.get("number"):
        gemini_number = str(gemini_params.get("number", "")).strip()
        card_number = str(card_data.get("number", "")).strip()

        if gemini_number == card_number:
            has_number_match = True
            score_breakdown["number_exact"] = 2000
        elif gemini_number in card_number or card_number in gemini_number:
            score_breakdown["number_partial"] = 800

    # Set size matching check (for Base Set vs Base Set 2 disambiguation)
    if gemini_params.get("set_size") and card_data.get("set", {}).get("total"):
        gemini_set_size = gemini_params.get("set_size")
        card_set_size = card_data.get("set", {}).get("total")

        if gemini_set_size == card_set_size:
            score_breakdown["set_size_exact"] = 300  # Bonus for exact set size match
            logger.debug(f"      Set size exact match: {gemini_set_size} cards")
        elif abs(gemini_set_size - card_set_size) <= 5:
            score_breakdown["set_size_close"] = 100  # Small bonus for close set size
            logger.debug(f"      Set size close match: {gemini_set_size} vs {card_set_size} cards")

    # Name matching check with Pokemon variant support
    if gemini_params.get("name") and card_data.get("name"):
        gemini_name = gemini_params.get("name", "").lower().strip()
        card_name = card_data.get("name", "").lower().strip()

        # Exact name match
        if gemini_name == card_name:
            has_name_match = True
            score_breakdown["name_exact"] = 1500
        # Pokemon variant matching (V, VMax, GX, ex, etc.)
        elif is_pokemon_variant_match(gemini_name, card_name):
            has_name_match = True  # Treat as name match for combination bonuses
            score_breakdown["name_variant_match"] = 1400  # High score for variant match
            logger.debug(f"      Pokemon variant match: '{gemini_name}' <-> '{card_name}'")
        # Penalize tag team cards when searching for single Pokemon
        elif "&" in card_name and "&" not in gemini_name:
            # Card is a tag team but search is for single Pokemon
            if gemini_name in card_name:
                score_breakdown["name_partial"] = 100
                score_breakdown["name_tag_team_penalty"] = -500
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
            # For now, give small bonus for any foil detection
            if any(word in foil_pattern for word in ["holo", "foil", "crystal", "rainbow", "cosmos"]):
                score_breakdown["visual_foil_match"] = 100

    total_score = sum(score_breakdown.values())
    return total_score, score_breakdown


def select_best_match(tcg_results: List[Dict[str, Any]], gemini_params: Dict[str, Any]) -> tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Select the best match from TCG results based on Gemini parameters.

    Args:
        tcg_results: List of card data from TCG API
        gemini_params: Parameters extracted from Gemini analysis

    Returns:
        Tuple of (best_match, all_matches_with_scores)
    """
    if not tcg_results:
        return None, []

    # Calculate scores for all matches
    matches_with_scores = []
    for card in tcg_results:
        score, breakdown = calculate_match_score_detailed(card, gemini_params)

        matches_with_scores.append({
            "card": card,
            "score": score,
            "score_breakdown": breakdown,
            "confidence": "high" if score >= 1000 else "medium" if score >= 600 else "low",
            "reasoning": _generate_match_reasoning(card, gemini_params, breakdown)
        })

    # Sort by score (highest first)
    def advanced_sort_key(match):
        # Primary sort: score
        # Secondary sort: prefer cards with more complete data
        card = match["card"]
        completeness_bonus = 0

        # Bonus for having image
        if card.get("images", {}).get("small"):
            completeness_bonus += 10

        # Bonus for having market price data
        if card.get("tcgplayer", {}).get("prices"):
            completeness_bonus += 5

        # Bonus for having set data
        if card.get("set", {}).get("name"):
            completeness_bonus += 5

        return match["score"] + completeness_bonus

    matches_with_scores.sort(key=advanced_sort_key, reverse=True)

    # Return best match and all matches
    best_match = matches_with_scores[0]["card"] if matches_with_scores else None

    return best_match, matches_with_scores


def _generate_match_reasoning(card: Dict[str, Any], gemini_params: Dict[str, Any], breakdown: Dict[str, int]) -> List[str]:
    """
    Generate human-readable reasoning for why a card matches.

    Args:
        card: Card data from TCG API
        gemini_params: Parameters from Gemini analysis
        breakdown: Score breakdown

    Returns:
        List of reasoning strings
    """
    reasoning = []

    # Name reasoning
    if breakdown.get("name_match", 0) >= 400:
        reasoning.append("Exact Pokemon name match")
    elif breakdown.get("name_match", 0) >= 300:
        reasoning.append("Pokemon variant match (e.g., V, GX, ex)")
    elif breakdown.get("name_match", 0) >= 200:
        reasoning.append("Partial name match")

    # Set reasoning
    if breakdown.get("set_match", 0) >= 200:
        reasoning.append("Perfect set name match")
    elif breakdown.get("set_match", 0) >= 150:
        reasoning.append("Set family match")
    elif breakdown.get("set_match", 0) >= 100:
        reasoning.append("Partial set match")

    # Set size reasoning
    if breakdown.get("set_size_match", 0) >= 100:
        reasoning.append("Exact set size match")
    elif breakdown.get("set_size_match", 0) >= 50:
        reasoning.append("Close set size match")

    # Number reasoning
    if breakdown.get("number_match", 0) >= 300:
        reasoning.append("Perfect card number match")
    elif breakdown.get("number_match", 0) >= 250:
        reasoning.append("Card number match (ignoring suffixes)")
    elif breakdown.get("number_match", 0) >= 150:
        reasoning.append("Partial card number match")

    # Type reasoning
    if breakdown.get("type_match", 0) >= 100:
        reasoning.append("Perfect type match")
    elif breakdown.get("type_match", 0) >= 50:
        reasoning.append("Partial type match")

    # HP reasoning
    if breakdown.get("hp_match", 0) >= 100:
        reasoning.append("Exact HP match")
    elif breakdown.get("hp_match", 0) >= 60:
        reasoning.append("Close HP match")

    if not reasoning:
        reasoning.append("Low confidence match")

    return reasoning
