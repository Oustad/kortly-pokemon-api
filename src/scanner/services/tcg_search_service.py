"""TCG search service for finding Pokemon cards in the TCG database."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..models.schemas import PokemonCard
from .card_matcher import get_set_family

logger = logging.getLogger(__name__)


class TCGSearchService:
    """Service for searching Pokemon cards in the TCG database with multiple strategies."""

    def __init__(self):
        """Initialize the TCG search service."""
        self.search_attempts = []
        self.all_search_results = []

    async def search_for_card(
        self,
        parsed_data: Dict[str, Any],
        tcg_client: Any
    ) -> Tuple[List[Dict], List[Dict], List[PokemonCard]]:
        """
        Search for a Pokemon card using multiple strategies.

        Args:
            parsed_data: Parsed card data from Gemini analysis
            tcg_client: Pokemon TCG client instance

        Returns:
            Tuple of (all_search_results, search_attempts, tcg_matches)
        """
        self.search_attempts = []
        self.all_search_results = []
        tcg_matches = []

        if not parsed_data.get("name"):
            logger.info("⚠️ TCG search skipped - no Pokemon name identified")
            return [], [], []

        logger.info(f"🔍 Search parameters: name='{parsed_data.get('name')}', set='{parsed_data.get('set_name')}', number='{parsed_data.get('number')}', hp='{parsed_data.get('hp')}'")

        # Execute search strategies in priority order
        await self._strategy_1_exact_match(parsed_data, tcg_client)
        await self._strategy_1_25_cross_set_number(parsed_data, tcg_client)
        await self._strategy_1_5_set_family(parsed_data, tcg_client)
        await self._strategy_2_set_name_only(parsed_data, tcg_client)
        await self._strategy_3_name_hp(parsed_data, tcg_client)
        await self._strategy_4_hidden_fates_special(parsed_data, tcg_client)
        await self._strategy_5_fuzzy_fallback(parsed_data, tcg_client)

        # Log search strategy results
        strategy_summary = ', '.join([f"{attempt['strategy']}: {attempt['results']}" for attempt in self.search_attempts])
        logger.debug(f"📊 Search Strategy Summary: {strategy_summary}")
        logger.info(f"🎯 Total combined search results: {len(self.all_search_results)} cards found")

        # Convert to PokemonCard objects
        for card_data in self.all_search_results:
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

        return self.all_search_results, self.search_attempts, tcg_matches

    async def _strategy_1_exact_match(self, parsed_data: Dict[str, Any], tcg_client: Any) -> None:
        """Strategy 1: HIGHEST PRIORITY - Set + Number + Name (exact match)."""
        if not (parsed_data.get("set_name") and parsed_data.get("number")):
            return

        set_valid = self._is_valid_set_name(parsed_data.get("set_name"))
        number_valid = self._is_valid_card_number(parsed_data.get("number"))

        if not (set_valid and number_valid):
            logger.debug(f"   ⚠️ Strategy 1 skipped: Invalid parameters - Set valid: {set_valid}, Number valid: {number_valid}")
            if not set_valid:
                logger.info(f"      Invalid set: '{parsed_data.get('set_name')}'")
            if not number_valid:
                logger.info(f"      Invalid number: '{parsed_data.get('number')}'")
            return

        logger.debug("🎯 Strategy 1: Set + Number + Name (PRIORITY)")
        logger.info(f"   🔍 Searching for: name='{parsed_data['name']}', set='{parsed_data.get('set_name')}', number='{parsed_data.get('number')}'")

        import time
        api_start = time.time()
        results = await tcg_client.search_cards(
            name=parsed_data["name"],
            set_name=parsed_data.get("set_name"),
            number=parsed_data.get("number"),
            page_size=5,
            fuzzy=False,
        )
        api_time = (time.time() - api_start) * 1000
        logger.debug(f"   ⏱️ Strategy 1 API call took {api_time:.1f}ms")

        if results.get("data"):
            self.all_search_results.extend(results["data"])
            logger.debug(f"✅ Strategy 1 found {len(results['data'])} exact matches")
            logger.debug(f"   📄 First match: {results['data'][0].get('name')} #{results['data'][0].get('number')} from {results['data'][0].get('set', {}).get('name')}")
        else:
            logger.debug("   ❌ Strategy 1: No exact matches found")

        self.search_attempts.append({
            "strategy": "set_number_name_exact",
            "query": {
                "name": parsed_data["name"],
                "set_name": parsed_data.get("set_name"),
                "number": parsed_data.get("number"),
            },
            "results": len(results.get("data", [])),
        })

    async def _strategy_1_25_cross_set_number(self, parsed_data: Dict[str, Any], tcg_client: Any) -> None:
        """Strategy 1.25: Cross-set Number + Name (when Gemini gets set wrong but number right)."""
        if len(self.all_search_results) > 0 or not (parsed_data.get("number") and parsed_data.get("name")):
            return

        if not self._is_valid_card_number(parsed_data.get("number")):
            logger.debug(f"   ⚠️ Strategy 1.25 skipped: Invalid number '{parsed_data.get('number')}'")
            return

        logger.debug("🔄 Strategy 1.25: Cross-set Number + Name (ignore potentially wrong set)")
        logger.info(f"   🔍 Searching for: name='{parsed_data['name']}', number='{parsed_data.get('number')}'")

        results = await tcg_client.search_cards(
            name=parsed_data["name"],
            number=parsed_data.get("number"),
            page_size=10,
            fuzzy=False,
        )

        if results.get("data"):
            new_results = self._filter_duplicates(results["data"])
            self.all_search_results.extend(new_results)
            logger.debug(f"✅ Strategy 1.25 found {len(new_results)} cross-set matches")

            # Log which set we actually found the card in
            if new_results:
                found_set = new_results[0].get("set", {}).get("name", "Unknown")
                original_set = parsed_data.get("set_name", "Unknown")
                if found_set != original_set:
                    logger.info(f"   🎯 Set correction: '{original_set}' → '{found_set}'")
        else:
            logger.debug("   ❌ Strategy 1.25: No cross-set matches found")

        self.search_attempts.append({
            "strategy": "cross_set_number_name",
            "query": {
                "name": parsed_data["name"],
                "number": parsed_data.get("number"),
            },
            "results": len(results.get("data", [])),
        })

    async def _strategy_1_5_set_family(self, parsed_data: Dict[str, Any], tcg_client: Any) -> None:
        """Strategy 1.5: Set Family + Number + Name (for cases like "XY" -> "XY BREAKpoint")."""
        if len(self.all_search_results) > 0 or not (parsed_data.get("set_name") and parsed_data.get("number")):
            return

        if not self._is_valid_card_number(parsed_data.get("number")):
            logger.debug(f"   ⚠️ Strategy 1.5 skipped: Invalid number '{parsed_data.get('number')}'")
            return

        set_family = get_set_family(parsed_data.get("set_name"))
        if not set_family:
            return

        logger.debug(f"🔄 Strategy 1.5: Set Family expansion for '{parsed_data.get('set_name')}'")
        logger.info(f"   📚 Set family contains: {set_family}")

        family_results_count = 0
        for family_set in set_family:
            logger.info(f"   🔍 Searching in family set: '{family_set}'")
            results = await tcg_client.search_cards(
                name=parsed_data["name"],
                set_name=family_set,
                number=parsed_data.get("number"),
                page_size=3,
                fuzzy=False,
            )

            if results.get("data"):
                new_results = self._filter_duplicates(results["data"])
                self.all_search_results.extend(new_results)
                family_results_count += len(new_results)
                logger.debug(f"✅ Strategy 1.5 found {len(new_results)} matches in {family_set}")
                for result in new_results[:2]:  # Log first 2 matches
                    logger.info(f"   📄 Found: {result.get('name')} #{result.get('number')} from {result.get('set', {}).get('name')}")
            else:
                logger.info(f"   ❌ No matches in '{family_set}'")

        self.search_attempts.append({
            "strategy": "set_family_number_name",
            "query": {
                "name": parsed_data["name"],
                "set_family": set_family,
                "number": parsed_data.get("number"),
            },
            "results": family_results_count,
        })

    async def _strategy_2_set_name_only(self, parsed_data: Dict[str, Any], tcg_client: Any) -> None:
        """Strategy 2: Set + Name (without number constraint)."""
        if not parsed_data.get("set_name"):
            return

        if not self._is_valid_set_name(parsed_data.get("set_name")):
            logger.debug(f"   ⚠️ Strategy 2 skipped: Invalid set name '{parsed_data.get('set_name')}'")
            return

        logger.debug("🔄 Strategy 2: Set + Name (no number)")
        logger.info(f"   🔍 Searching for: name='{parsed_data['name']}', set='{parsed_data.get('set_name')}'")

        results = await tcg_client.search_cards(
            name=parsed_data["name"],
            set_name=parsed_data.get("set_name"),
            page_size=10,
            fuzzy=False,
        )

        if results.get("data"):
            new_results = self._filter_duplicates(results["data"])
            self.all_search_results.extend(new_results)
            logger.debug(f"✅ Strategy 2 found {len(new_results)} additional matches")
            for result in new_results[:3]:  # Log first 3 new matches
                logger.info(f"   📄 Found: {result.get('name')} #{result.get('number')} from {result.get('set', {}).get('name')}")
        else:
            logger.debug("   ❌ Strategy 2: No set+name matches found")

        self.search_attempts.append({
            "strategy": "set_name_only",
            "query": {
                "name": parsed_data["name"],
                "set_name": parsed_data.get("set_name"),
            },
            "results": len(results.get("data", [])),
        })

    async def _strategy_3_name_hp(self, parsed_data: Dict[str, Any], tcg_client: Any) -> None:
        """Strategy 3: Name + HP (cross-set search with HP validation)."""
        if not parsed_data.get("hp") or len(self.all_search_results) >= 5:
            return

        logger.debug("🔄 Strategy 3: Name + HP (cross-set)")
        results = await tcg_client.search_cards(
            name=parsed_data["name"],
            hp=parsed_data.get("hp"),
            page_size=10,
            fuzzy=False,
        )

        if results.get("data"):
            new_results = self._filter_duplicates(results["data"])
            self.all_search_results.extend(new_results)
            logger.debug(f"✅ Strategy 3 found {len(new_results)} HP-matching cards")

        self.search_attempts.append({
            "strategy": "name_hp_cross_set",
            "query": {
                "name": parsed_data["name"],
                "hp": parsed_data.get("hp"),
            },
            "results": len(results.get("data", [])),
        })

    async def _strategy_4_hidden_fates_special(self, parsed_data: Dict[str, Any], tcg_client: Any) -> None:
        """Strategy 4: Special case for Hidden Fates Shiny Vault numbers."""
        if (parsed_data.get("set_name") != "Hidden Fates" or 
            not parsed_data.get("number") or 
            len(self.all_search_results) >= 3):
            return

        logger.debug("🔄 Strategy 4: Hidden Fates with SV prefix")
        sv_number = f"SV{parsed_data['number']}"

        results = await tcg_client.search_cards(
            name=parsed_data["name"],
            set_name=parsed_data.get("set_name"),
            number=sv_number,
            page_size=5,
            fuzzy=False,
        )

        if results.get("data"):
            new_results = self._filter_duplicates(results["data"])
            self.all_search_results.extend(new_results)
            logger.debug(f"✅ Strategy 4 found {len(new_results)} SV-prefixed cards")

        self.search_attempts.append({
            "strategy": "hidden_fates_sv_prefix",
            "query": {
                "name": parsed_data["name"],
                "set_name": parsed_data.get("set_name"),
                "number": sv_number,
            },
            "results": len(results.get("data", [])),
        })

    async def _strategy_5_fuzzy_fallback(self, parsed_data: Dict[str, Any], tcg_client: Any) -> None:
        """Strategy 5: Fallback - Name only (fuzzy search)."""
        if len(self.all_search_results) >= 5:
            return

        logger.debug("🔄 Strategy 5: Fallback name-only (fuzzy)")
        results = await tcg_client.search_cards(
            name=parsed_data["name"],
            page_size=15,
            fuzzy=True,
        )

        if results.get("data"):
            new_results = self._filter_duplicates(results["data"])
            # Limit fallback results to prevent too many fuzzy matches
            self.all_search_results.extend(new_results[:10])
            logger.debug(f"✅ Strategy 5 found {len(new_results[:10])} fallback matches")

        self.search_attempts.append({
            "strategy": "fuzzy_name_only_fallback",
            "query": {
                "name": parsed_data["name"],
            },
            "results": len(results.get("data", [])),
        })

    def _filter_duplicates(self, new_results: List[Dict]) -> List[Dict]:
        """Filter out cards that are already in search results."""
        return [
            card for card in new_results
            if not any(existing["id"] == card["id"] for existing in self.all_search_results)
        ]

    def _is_valid_set_name(self, set_name: Optional[str]) -> bool:
        """Check if set name is valid for TCG API query."""
        if not set_name or not isinstance(set_name, str):
            return False

        # Invalid phrases that indicate Gemini couldn't identify the set
        invalid_phrases = [
            "not visible", "likely", "but", "era", "possibly", "unknown",
            "can't see", "cannot see", "unclear", "maybe", "appears to be",
            "looks like", "seems like", "hard to tell", "difficult to see"
        ]

        set_lower = set_name.lower()

        # Check for invalid phrases
        if any(phrase in set_lower for phrase in invalid_phrases):
            return False

        # Check for overly long descriptions (real set names are typically < 50 chars)
        if len(set_name) > 50:
            return False

        # Check for commas (indicates descriptive text)
        if "," in set_name:
            return False

        return True

    def _is_valid_card_number(self, number: Optional[str]) -> bool:
        """Check if card number is valid for TCG API query."""
        import re
        
        if not number or not isinstance(number, str):
            return False

        # Remove whitespace
        number = number.strip()

        # Invalid phrases that indicate Gemini couldn't identify the number
        invalid_phrases = [
            "not visible", "unknown", "unclear", "can't see", "cannot see",
            "hard to tell", "difficult", "n/a", "none", "not found"
        ]

        number_lower = number.lower()

        # Check for invalid phrases
        if any(phrase in number_lower for phrase in invalid_phrases):
            return False

        # Check for spaces in the middle (indicates descriptive text)
        if " " in number:
            return False

        # Allow alphanumeric with optional letters (e.g., "123", "SV001", "177a", "TG12")
        # Also allow hyphens for promos (e.g., "SWSH001", "XY-P001")
        if not re.match(r'^[A-Za-z0-9\-]+$', number):
            return False

        # Must have at least one digit
        if not any(c.isdigit() for c in number):
            return False

        return True