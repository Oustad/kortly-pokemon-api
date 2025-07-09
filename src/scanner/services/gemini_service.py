"""Service for interacting with Google Gemini API for Pokemon card identification."""

import io
import logging
import os
from typing import Any, Dict, Optional

import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError
from PIL import Image

from ..config import get_config

logger = logging.getLogger(__name__)
config = get_config()


class GeminiService:
    """Service for using Google Gemini to analyze Pokemon cards."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Gemini service with API key."""
        self._model = None
        # Clean the API key to remove any potential issues
        if api_key:
            # Remove any whitespace, newlines, or hidden characters
            self._api_key = api_key.strip()
        else:
            self._api_key = api_key

    @property
    def model(self):
        """Lazy load the Gemini model."""
        if self._model is None:
            if self._api_key:
                try:
                    # Set API key in environment as a workaround for metadata issues
                    os.environ["GOOGLE_API_KEY"] = self._api_key
                    # Configure with cleaned API key
                    genai.configure(api_key=self._api_key)
                    logger.info(f"Configured Gemini with API key (length: {len(self._api_key)})")
                except Exception as e:
                    logger.error(f"Failed to configure Gemini API: {e}")
                    # Try to log more details without exposing the key
                    logger.error(f"API key format check - starts with: {self._api_key[:8]}..., ends with: ...{self._api_key[-4:]}")
                    raise
            else:
                logger.warning(
                    "No Gemini API key provided. Set GOOGLE_API_KEY environment variable."
                )
            self._model = genai.GenerativeModel(config.gemini_model)
        return self._model

    async def identify_pokemon_card(
        self,
        image_bytes: bytes,
        optimize_for_speed: bool = True,
        retry_unlimited: bool = False,
    ) -> Dict[str, Any]:
        """
        Use Gemini to identify a Pokemon card from an image with comprehensive analysis and authenticity detection.

        Args:
            image_bytes: The image data as bytes
            optimize_for_speed: If True, use optimizations to reduce processing time
            retry_unlimited: If True, retry with unlimited tokens if MAX_TOKENS error

        Returns:
            Dictionary containing Gemini's response and metadata
        """
        try:
            logger.info("🤖 Calling Gemini API for Pokemon card identification...")

            pil_image = Image.open(io.BytesIO(image_bytes))

            if optimize_for_speed:
                # Resize image to reduce processing time while maintaining quality
                max_dimension = min(800, config.image_max_dimension)  # Use smaller of the two for speed
                if max(pil_image.size) > max_dimension:
                    ratio = max_dimension / max(pil_image.size)
                    new_size = tuple(int(dim * ratio) for dim in pil_image.size)
                    pil_image = pil_image.resize(new_size, Image.Resampling.LANCZOS)
                    logger.info(f"Resized image to {new_size} for faster processing")

            prompt = self._get_optimized_prompt()
            generation_config = self._get_generation_config(retry_unlimited)

            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE",
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE",
                },
            ]

            response = self.model.generate_content(
                [prompt, pil_image],
                generation_config=generation_config,
                safety_settings=safety_settings,
            )

            # Extract the text response with proper error handling
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                finish_reason = (
                    candidate.finish_reason.name if candidate.finish_reason else "UNKNOWN"
                )

                # Check if response was blocked by safety filters
                if finish_reason == "SAFETY":
                    safety_issues = []
                    if candidate.safety_ratings:
                        for rating in candidate.safety_ratings:
                            if rating.probability.name in ["MEDIUM", "HIGH"]:
                                safety_issues.append(
                                    f"{rating.category.name}: {rating.probability.name}"
                                )

                    logger.warning(
                        f"⚠️ Gemini response blocked by safety filters: {safety_issues}"
                    )
                    return {
                        "success": False,
                        "error": f"Response blocked by safety filters: {', '.join(safety_issues)}",
                        "finish_reason": finish_reason,
                    }

                # Handle MAX_TOKENS specially - retry with unlimited tokens
                if finish_reason == "MAX_TOKENS" and not retry_unlimited:
                    logger.warning("⚠️ MAX_TOKENS hit, retrying with unlimited tokens...")
                    return await self.identify_pokemon_card(
                        image_bytes=image_bytes,
                        optimize_for_speed=optimize_for_speed,
                        retry_unlimited=True,
                        processing_tier=processing_tier,
                    )

                # Check if we have valid content
                if (
                    hasattr(candidate, "content")
                    and candidate.content
                    and candidate.content.parts
                ):
                    response_text = "".join(
                        [
                            part.text
                            for part in candidate.content.parts
                            if hasattr(part, "text")
                        ]
                    )

                    if response_text:
                        # Handle truncated responses
                        is_truncated = finish_reason == "MAX_TOKENS"
                        if is_truncated:
                            response_text += "\n\n[Response truncated due to length limit]"
                            logger.warning(
                                f"⚠️ Gemini response truncated ({len(response_text)} chars)"
                            )

                        result = {
                            "success": True,
                            "response": response_text,
                            "prompt_tokens": (
                                response.usage_metadata.prompt_token_count
                                if hasattr(response, "usage_metadata")
                                else None
                            ),
                            "response_tokens": (
                                response.usage_metadata.candidates_token_count
                                if hasattr(response, "usage_metadata")
                                else None
                            ),
                            "finish_reason": finish_reason,
                            "truncated": is_truncated,
                        }

                        logger.info(
                            f"✅ Gemini response received ({len(response_text)} characters)"
                        )
                        return result

                logger.warning(
                    f"⚠️ Gemini returned no valid content. Finish reason: {finish_reason}"
                )
                return {
                    "success": False,
                    "error": f"No valid content returned. Finish reason: {finish_reason}",
                    "finish_reason": finish_reason,
                }
            else:
                logger.warning("⚠️ Gemini returned no candidates")
                return {
                    "success": False,
                    "error": "No candidates returned from Gemini",
                }

        except GoogleAPIError as e:
            logger.error(f"❌ Gemini API error: {str(e)}")
            return {
                "success": False,
                "error": f"Gemini API error: {str(e)}",
            }
        except Exception as e:
            logger.error(f"❌ Unexpected error calling Gemini: {str(e)}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
            }

    def _get_optimized_prompt(self) -> str:
        """Get the comprehensive Pokemon card analysis prompt with authenticity detection."""
        return """Analyze this image comprehensively. First determine what type of card this is, then identify visual distinguishing features.

CARD TYPE DETECTION:
- pokemon_front: Pokemon card showing the front (Pokemon, attacks, abilities)
- pokemon_back: Pokemon card showing the back (Pokeball design, no specific Pokemon)
- non_pokemon: Not a Pokemon card (Magic, Yu-Gi-Oh, sports card, etc.)
- unknown: Cannot determine card type due to image quality

VISUAL ANALYSIS - CRITICAL FOR CARD DIFFERENTIATION:
Look for these distinguishing features:
- Set symbols/logos (e-Card logo, XY symbol, Sword & Shield logo, etc.)
- Card series/era (e-Card, EX, Diamond & Pearl, XY, Sun & Moon, Sword & Shield, etc.)
- XY-era specific sets: Look for "BREAKpoint", "BREAKthrough", "Fates Collide", "Steam Siege", "Evolutions", etc.
- Card frame design (vintage yellow border, modern silver, black border, etc.)
- Foil patterns (rainbow foil, cosmos holo, texture, crystal pattern, etc.)
- Energy symbol style (classic flat, modern 3D, stylized)
- Layout differences (attack cost placement, text formatting)

IMPORTANT for Set Name Extraction:
- Extract the actual set NAME, not just symbol description
- Examples: "Plasma Freeze" (not "Plasma Freeze set symbol"), "Battle Styles" (not "Battle Styles logo")
- HeartGold/SoulSilver era: "HS—Undaunted", "HS—Unleashed", "HS—Triumphant", "HeartGold & SoulSilver"
- XY-era CRITICAL: Never just say "XY" - look for the FULL set name:
  * "XY" (base set only - has Xerneas/Yveltal on packs)
  * "XY BREAKpoint" (has Gyarados on pack, BREAK evolution cards)
  * "XY BREAKthrough" (has Mewtwo on pack)
  * "XY Fates Collide" (has Zygarde on pack)
  * "XY Steam Siege" (has Volcanion on pack)
  * "XY Evolutions" (nostalgia set with classic designs)
  * "XY Flashfire", "XY Furious Fists", "XY Phantom Forces", "XY Primal Clash", "XY Roaring Skies", "XY Ancient Origins"
- Black & White era: "Plasma Freeze", "Plasma Storm", "Plasma Blast", "Emerging Powers", "Noble Victories"
- BREAK evolution cards are specifically from BREAKpoint/BREAKthrough sets
- HIDDEN FATES SHINY VAULT DETECTION (CRITICAL):
  * Card numbers starting with "SV" (like SV1, SV8, SV22, etc.) are from "Hidden Fates Shiny Vault"
  * These cards have distinctive rainbow/cosmos foil patterns covering the entire card
  * Despite "SV" prefix, these are NOT "Scarlet & Violet" cards - they are "Hidden Fates Shiny Vault"
  * Set name should be "Hidden Fates Shiny Vault" (NOT "Scarlet & Violet")
  * SV numbers range from SV1 to SV94 in Hidden Fates Shiny Vault
  * Visual cues: Shiny/rainbow foil + SV number = Hidden Fates Shiny Vault set
- Note any promo markings or special set indicators

BREAK CARD DETECTION (XY BREAKpoint/BREAKthrough era):
- BREAK evolution cards have UNIQUE sideways/horizontal orientation
- Gold/yellow textured foil pattern covering entire card
- "BREAK" text appears after Pokemon name (e.g., "Greninja BREAK")
- If you see a sideways card with gold foil, it's likely from BREAKpoint or BREAKthrough
- Regular cards in these sets have standard vertical orientation

PRIME CARD DETECTION (HeartGold/SoulSilver era):
- Look for "Prime" text on the card (usually near the Pokemon name)
- Prime cards have distinctive horizontal layout and special border
- Prime cards are from HGSS era sets: Undaunted, Unleashed, Triumphant
- Include "Prime" in the name if detected (e.g., "Houndoom Prime")

IMPORTANT: Detect the card language and preserve original names.

CARD NUMBER READING (CRITICAL - MOST IMPORTANT):
- Card numbers are THE MOST CRITICAL field for accurate identification
- Read numbers very carefully, character by character, looking in multiple locations
- FOIL/HOLO INTERFERENCE: Shiny/holographic patterns can obscure numbers - look past reflections

CARD NUMBER LOCATION AND FORMAT:
- VINTAGE CARDS (Base, Jungle, Fossil): Simple numbers like "22", "16", "43" in bottom-right or bottom-center
- MODERN CARDS: "X/Y" format like "50/189", "144/185" in bottom-right corner
- e-Card era: Numbers often start with H (e.g., H11/H32, H25/H32)
- Recent sets: Look for prefixes like "PAL" (Paldea), etc.
- SHINY VAULT "SV" NUMBERS: "SV" prefix indicates Hidden Fates Shiny Vault (SV1, SV8, SV22, etc.) - NOT Scarlet & Violet

WHAT TO IGNORE (DO NOT use as card numbers):
- Attack damage numbers (usually larger, in attack text like "Thunder deals 30 damage")
- HP numbers (top-right with HP symbol, like "HP 70")
- Energy cost numbers (small symbols next to attacks)
- Copyright/legal text numbers (© 1998, etc.)
- Pokedex numbers (#144 in flavor text)
- Numbers in attack names or descriptions

WHERE TO LOOK FOR REAL CARD NUMBERS:
- Bottom-right corner (most common)
- Bottom-center of card (vintage cards)
- Always ISOLATED from other text - not part of sentences
- Usually smaller text, separate from game mechanics
- On card border or margin, not in main text blocks

VERIFICATION STEPS:
- If you see multiple possible numbers, specify the EXACT LOCATION of each
- Card numbers are standalone, not part of attack descriptions or flavor text
- Common mistakes: H11 vs H1, 011 vs 01, 104 vs 10, SV16 vs other numbers
- SHINY VAULT NUMBERS: Be extra careful with SV numbers - foil can make SV8 look like complex patterns
- SV numbers should be simple: SV1, SV8, SV22, etc. (NOT SV3/SV94 or other complex formats)
- If numbers are unclear due to foil/damage, indicate uncertainty in your analysis
- Double and triple-check the number - getting this wrong ruins the entire identification

AUTHENTICITY ASSESSMENT:
Rate the authenticity of this Pokemon card from 0-100, considering:
- Print quality, typography, and card layout
- Official Pokemon logos and set symbols
- Content authenticity (check for parody names, jokes, or fake text)
- CRITICAL TCG AUTHENTICITY MARKERS (must be present for high scores):
  * Standard TCG card format with proper text boxes and layout
  * Official TCG fonts and typography (clean, professional printing)
  * Legitimate set symbols (not amateur or custom designs)
  * Proper copyright notices and legal text formatting
  * Standard TCG card dimensions and border styling
- RED FLAGS FOR NON-TCG CARDS (should result in scores ≤ 50):
  * Sticker-like appearance or glossy finish inconsistent with TCG cards
  * Amateur/home-printed quality or blurry text
  * Non-standard layouts or unusual card designs
  * Missing or incorrect copyright information
  * Pokedex numbers instead of TCG card numbers (e.g., "#204" instead of "63/111")
  * Collectible cards, stickers, or promotional items that aren't TCG cards
  * Fan-made or custom cards with unofficial designs
- SCORING GUIDELINES:
  * 90-100: Clearly authentic official TCG card with all proper elements
  * 70-89: Likely authentic but minor quality or clarity issues
  * 50-69: Questionable authenticity, possible bootleg or unofficial card
  * 30-49: Likely non-TCG Pokemon product (sticker, collectible, etc.)
  * 0-29: Clearly fake, parody, or non-Pokemon content

READABILITY ASSESSMENT:
Rate the text readability of this Pokemon card from 0-100, with SPECIAL EMPHASIS on numbers:
- Card number clarity (MOST IMPORTANT - if numbers are unclear, score should be low)
- Pokemon name legibility
- Set information visibility
- Physical damage assessment: scratches, wear, creases, stains affect readability
- Overall text sharpness, especially considering foil/holo interference
- 100 = all text perfectly readable including numbers, 0 = critical text illegible
- IMPORTANT: If card numbers are hard to read due to foil/shine, significantly lower the score
- CRITICAL: Physical damage like scratches, heavy wear, or surface damage should result in scores ≤ 70
- DAMAGED CARDS: If you see scratches, scuffs, or wear that impairs text clarity, be harsh in scoring

UNCERTAINTY AND CONFIDENCE HANDLING:
- If text is blurry or unclear, indicate uncertainty in your analysis
- Use phrases like "appears to be", "likely", "unclear due to image quality" when uncertain
- CRITICAL: If card numbers are unclear due to foil/holo interference, say so explicitly
- If you cannot clearly read set symbols or text, say so explicitly
- Provide multiple possibilities when identification is ambiguous
- Lower your confidence level when visual features are unclear or contradictory
- For shiny/foil cards: be extra cautious about number reading accuracy

Required format:
TCG_SEARCH_START
{
  "card_type": "pokemon_front/pokemon_back/non_pokemon/unknown",
  "is_pokemon_card": true/false,
  "card_side": "front/back/unknown",
  "name": "exact pokemon name from card",
  "original_name": "pokemon name exactly as written on the card", 
  "language": "card language code (en=English, fr=French, ja=Japanese, de=German, es=Spanish, it=Italian, pt=Portuguese, ko=Korean, zh=Chinese)",
  "set_name": "exact set name (extract from set symbol: 'Plasma Freeze', 'Battle Styles', etc.)",
  "number": "card number if visible (read carefully, e.g., H11 not H1, double-check digits)", 
  "hp": "HP value if visible",
  "types": ["pokemon type(s) like Fire, Water, Grass etc"],
  "supertype": "Pokemon",
  "set_symbol": "describe visible set symbol or logo",
  "card_series": "e-Card/EX/Diamond Pearl/XY/Sun Moon/Sword Shield/Scarlet Violet/etc",
  "visual_era": "vintage/classic/modern based on design style",
  "foil_pattern": "describe foil/holo pattern if present",
  "border_color": "yellow/silver/black/gold/other border color",
  "energy_symbol_style": "classic/modern/3D energy symbol style",
  "authenticity_score": 85,
  "readability_score": 75
}
TCG_SEARCH_END"""

    def _get_generation_config(self, retry_unlimited: bool) -> genai.types.GenerationConfig:
        """Get optimized generation configuration for comprehensive analysis."""
        
        if retry_unlimited:
            # No token limit on retry
            return genai.types.GenerationConfig(
                temperature=config.gemini_temperature,
            )
        
        # Optimized configuration for comprehensive analysis with authenticity detection
        return genai.types.GenerationConfig(
            max_output_tokens=min(400, config.gemini_max_tokens),  # Optimized response length
            temperature=config.gemini_temperature,
            top_p=0.95,       # More creative sampling for challenging images
        )

    def count_tokens(self, text: str) -> int:
        """Count tokens in a text string."""
        try:
            return self.model.count_tokens(text).total_tokens
        except Exception as e:
            logger.warning(f"Failed to count tokens: {e}")
            return 0
    
    def get_prompt_optimization_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics about prompt optimization across tiers."""
        stats = {}
        
        for tier in ["fast", "standard", "enhanced"]:
            prompt = self._get_optimized_prompt(tier)
            config_obj = self._get_generation_config(tier, retry_unlimited=False)
            
            stats[tier] = {
                "prompt_length": len(prompt),
                "estimated_prompt_tokens": len(prompt.split()) * 1.3,  # Rough estimate
                "max_output_tokens": getattr(config_obj, 'max_output_tokens', 'unlimited'),
                "temperature": getattr(config_obj, 'temperature', 'default'),
                "optimization_focus": {
                    "fast": "Speed (minimal tokens, low temperature)",
                    "standard": "Balance (standard tokens, normal temperature)", 
                    "enhanced": "Quality (max tokens, higher creativity)"
                }[tier]
            }
        
        return stats