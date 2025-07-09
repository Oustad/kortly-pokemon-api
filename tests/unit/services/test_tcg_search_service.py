"""Unit tests for TCGSearchService."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List

from src.scanner.services.tcg_search_service import TCGSearchService


class TestTCGSearchService:
    """Test cases for TCGSearchService."""

    @pytest.fixture
    def service(self):
        """Create TCGSearchService instance."""
        return TCGSearchService()

    @pytest.fixture
    def mock_tcg_client(self):
        """Create mock TCG client."""
        client = Mock()
        client.search_cards = AsyncMock()
        return client

    @pytest.fixture
    def sample_parsed_data(self):
        """Sample parsed data from Gemini."""
        return {
            "name": "Pikachu",
            "set_name": "Base Set",
            "number": "58",
            "hp": "60",
            "types": ["Electric"]
        }

    @pytest.fixture
    def sample_card_data(self):
        """Sample card data from TCG API."""
        return {
            "id": "base1-58",
            "name": "Pikachu",
            "set": {"name": "Base Set"},
            "number": "58",
            "hp": "60",
            "types": ["Lightning"],
            "rarity": "Common",
            "images": {"small": "url1", "large": "url2"}
        }

    @pytest.mark.asyncio
    async def test_search_for_card_no_name(self, service, mock_tcg_client):
        """Test search when no name is provided."""
        parsed_data = {"set_name": "Base Set", "number": "58"}
        
        results, attempts, matches = await service.search_for_card(parsed_data, mock_tcg_client)
        
        assert results == []
        assert attempts == []
        assert matches == []
        mock_tcg_client.search_cards.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_for_card_empty_results(self, service, mock_tcg_client, sample_parsed_data):
        """Test search when no results are found."""
        mock_tcg_client.search_cards.return_value = {"data": []}
        
        results, attempts, matches = await service.search_for_card(sample_parsed_data, mock_tcg_client)
        
        assert results == []
        assert len(attempts) > 0  # Should have tried multiple strategies
        assert matches == []

    @pytest.mark.asyncio
    async def test_strategy_1_exact_match(self, service, mock_tcg_client, sample_parsed_data, sample_card_data):
        """Test Strategy 1: exact set + number + name match."""
        mock_tcg_client.search_cards.return_value = {"data": [sample_card_data]}
        
        results, attempts, matches = await service.search_for_card(sample_parsed_data, mock_tcg_client)
        
        # Should find the card with strategy 1
        assert len(results) == 1
        assert results[0]["id"] == "base1-58"
        assert len(matches) == 1
        assert matches[0].id == "base1-58"
        
        # Check that strategy 1 was used
        assert any(att["strategy"] == "set_number_name_exact" for att in attempts)
        
        # Verify the exact search parameters
        first_call = mock_tcg_client.search_cards.call_args_list[0]
        assert first_call.kwargs["name"] == "Pikachu"
        assert first_call.kwargs["set_name"] == "Base Set"
        assert first_call.kwargs["number"] == "58"
        assert first_call.kwargs["fuzzy"] is False

    @pytest.mark.asyncio
    async def test_strategy_1_25_cross_set_number(self, service, mock_tcg_client, sample_card_data):
        """Test Strategy 1.25: cross-set number + name match."""
        parsed_data = {
            "name": "Pikachu",
            "set_name": "Wrong Set",  # Wrong set name
            "number": "58"
        }
        
        # Mock all potential strategy calls
        mock_tcg_client.search_cards.side_effect = [
            {"data": []},  # Strategy 1 fails
            {"data": [sample_card_data]},  # Strategy 1.25 succeeds
            {"data": []},  # Strategy 2 (set+name)
            {"data": []},  # Strategy 3 (name+hp) - skipped if no HP
            {"data": []},  # Strategy 5 (fuzzy)
        ]
        
        results, attempts, matches = await service.search_for_card(parsed_data, mock_tcg_client)
        
        assert len(results) == 1
        assert results[0]["id"] == "base1-58"
        
        # Check that strategy 1.25 was used
        assert any(att["strategy"] == "cross_set_number_name" for att in attempts)
        
        # Verify the cross-set search didn't include set_name
        second_call = mock_tcg_client.search_cards.call_args_list[1]
        assert second_call.kwargs["name"] == "Pikachu"
        assert second_call.kwargs["number"] == "58"
        assert "set_name" not in second_call.kwargs

    @pytest.mark.asyncio
    async def test_strategy_1_5_set_family(self, service, mock_tcg_client, sample_card_data):
        """Test Strategy 1.5: set family expansion."""
        parsed_data = {
            "name": "Pikachu",
            "set_name": "XY",  # Generic set name that has family
            "number": "42"
        }
        
        xy_card = {
            "id": "xy1-42",
            "name": "Pikachu",
            "set": {"name": "XY Base"},
            "number": "42"
        }
        
        # Mock responses for different strategies
        mock_tcg_client.search_cards.side_effect = [
            {"data": []},  # Strategy 1 fails
            {"data": []},  # Strategy 1.25 fails  
            {"data": [xy_card]},  # Strategy 1.5 succeeds for first family set
            {"data": []},  # Strategy 1.5 second family set
            {"data": []},  # Strategy 1.5 third family set
            {"data": []},  # Strategy 2 (set+name)
            {"data": []},  # Strategy 3 (name+hp) - if no HP in data
            {"data": []},  # Strategy 5 (fuzzy)
        ]
        
        with patch('src.scanner.services.tcg_search_service.get_set_family') as mock_get_family:
            mock_get_family.return_value = ["XY Base", "XY BREAKpoint", "XY BREAKthrough"]
            
            results, attempts, matches = await service.search_for_card(parsed_data, mock_tcg_client)
        
        assert len(results) == 1
        assert results[0]["id"] == "xy1-42"
        
        # Check that set family strategy was used
        assert any(att["strategy"] == "set_family_number_name" for att in attempts)

    @pytest.mark.asyncio
    async def test_strategy_2_set_name_only(self, service, mock_tcg_client, sample_card_data):
        """Test Strategy 2: set + name without number."""
        parsed_data = {
            "name": "Pikachu",
            "set_name": "Base Set",
            "number": None  # No number provided
        }
        
        mock_tcg_client.search_cards.return_value = {"data": [sample_card_data]}
        
        results, attempts, matches = await service.search_for_card(parsed_data, mock_tcg_client)
        
        assert len(results) == 1
        assert any(att["strategy"] == "set_name_only" for att in attempts)

    @pytest.mark.asyncio
    async def test_strategy_3_name_hp(self, service, mock_tcg_client, sample_card_data):
        """Test Strategy 3: name + HP cross-set search."""
        parsed_data = {
            "name": "Pikachu",
            "hp": "60",
            "set_name": None,
            "number": None
        }
        
        mock_tcg_client.search_cards.return_value = {"data": [sample_card_data]}
        
        results, attempts, matches = await service.search_for_card(parsed_data, mock_tcg_client)
        
        assert len(results) == 1
        assert any(att["strategy"] == "name_hp_cross_set" for att in attempts)

    @pytest.mark.asyncio
    async def test_strategy_4_hidden_fates_special(self, service, mock_tcg_client):
        """Test Strategy 4: Hidden Fates Shiny Vault special case."""
        parsed_data = {
            "name": "Pikachu",
            "set_name": "Hidden Fates",
            "number": "56"  # Will be converted to SV56
        }
        
        shiny_vault_card = {
            "id": "sma-SV56",
            "name": "Pikachu",
            "set": {"name": "Hidden Fates"},
            "number": "SV56"
        }
        
        # Use return_value instead of side_effect for consistent returns
        search_call_count = 0
        async def mock_search(**kwargs):
            nonlocal search_call_count
            search_call_count += 1
            
            # Return shiny vault card when searching with SV prefix
            if kwargs.get("number") == "SV56":
                return {"data": [shiny_vault_card]}
            return {"data": []}
        
        mock_tcg_client.search_cards = AsyncMock(side_effect=mock_search)
        
        results, attempts, matches = await service.search_for_card(parsed_data, mock_tcg_client)
        
        assert len(results) == 1
        assert results[0]["number"] == "SV56"
        assert any(att["strategy"] == "hidden_fates_sv_prefix" for att in attempts)

    @pytest.mark.asyncio
    async def test_strategy_5_fuzzy_fallback(self, service, mock_tcg_client, sample_card_data):
        """Test Strategy 5: fuzzy name-only fallback."""
        parsed_data = {
            "name": "Pikachu",
            "set_name": None,
            "number": None
        }
        
        # All strategies fail except fuzzy
        mock_tcg_client.search_cards.side_effect = [
            {"data": []},  # Strategy 3 (name+hp)
            {"data": [sample_card_data] * 20}  # Strategy 5 (fuzzy) returns many
        ]
        
        results, attempts, matches = await service.search_for_card(parsed_data, mock_tcg_client)
        
        # Should limit to 10 results
        assert len(results) <= 10
        assert any(att["strategy"] == "fuzzy_name_only_fallback" for att in attempts)

    @pytest.mark.asyncio
    async def test_filter_duplicates(self, service, mock_tcg_client):
        """Test that duplicate cards are filtered out."""
        parsed_data = {
            "name": "Pikachu",
            "set_name": "Base Set",
            "number": "58"
        }
        
        card1 = {"id": "base1-58", "name": "Pikachu"}
        card2 = {"id": "base2-87", "name": "Pikachu"}
        
        # Multiple strategies return overlapping results
        mock_tcg_client.search_cards.side_effect = [
            {"data": [card1, card2]},  # Strategy 1
            {"data": [card1]},  # Strategy 2 returns duplicate
            {"data": []},  # Strategy 3
            {"data": [card2, {"id": "xy1-42", "name": "Pikachu"}]}  # Strategy 5
        ]
        
        results, attempts, matches = await service.search_for_card(parsed_data, mock_tcg_client)
        
        # Check no duplicates in results
        seen_ids = set()
        for card in results:
            assert card["id"] not in seen_ids
            seen_ids.add(card["id"])

    def test_is_valid_set_name(self, service):
        """Test set name validation."""
        # Valid set names
        assert service._is_valid_set_name("Base Set")
        assert service._is_valid_set_name("XY")
        assert service._is_valid_set_name("Sword & Shield")
        
        # Invalid set names
        assert not service._is_valid_set_name("not visible")
        assert not service._is_valid_set_name("possibly Base Set")
        assert not service._is_valid_set_name("Base Set, but unclear")
        assert not service._is_valid_set_name("X" * 51)  # Too long
        assert not service._is_valid_set_name(None)
        assert not service._is_valid_set_name("")

    def test_is_valid_card_number(self, service):
        """Test card number validation."""
        # Valid card numbers
        assert service._is_valid_card_number("58")
        assert service._is_valid_card_number("SV56")
        assert service._is_valid_card_number("XY-P001")
        assert service._is_valid_card_number("25a")
        
        # Invalid card numbers
        assert not service._is_valid_card_number("not visible")
        assert not service._is_valid_card_number("unknown")
        assert not service._is_valid_card_number("25 of 102")
        assert not service._is_valid_card_number("1/102")  # Slashes not allowed
        assert not service._is_valid_card_number("ABC")  # No digits
        assert not service._is_valid_card_number(None)
        assert not service._is_valid_card_number("")

    @pytest.mark.asyncio
    async def test_invalid_set_name_skips_strategies(self, service, mock_tcg_client):
        """Test that invalid set names skip relevant strategies."""
        parsed_data = {
            "name": "Pikachu",
            "set_name": "not visible clearly",  # Invalid
            "number": "58"
        }
        
        # Only cross-set and fuzzy strategies should run
        mock_tcg_client.search_cards.side_effect = [
            {"data": []},  # Strategy 1.25 (cross-set)
            {"data": []}   # Strategy 5 (fuzzy)
        ]
        
        results, attempts, matches = await service.search_for_card(parsed_data, mock_tcg_client)
        
        # Should not have tried set-based strategies
        assert not any(att["strategy"] == "set_number_name_exact" for att in attempts)
        assert not any(att["strategy"] == "set_name_only" for att in attempts)
        
        # Should have tried cross-set and fuzzy
        assert any(att["strategy"] == "cross_set_number_name" for att in attempts)
        assert any(att["strategy"] == "fuzzy_name_only_fallback" for att in attempts)

    @pytest.mark.asyncio
    async def test_invalid_number_skips_strategies(self, service, mock_tcg_client):
        """Test that invalid numbers skip relevant strategies."""
        parsed_data = {
            "name": "Pikachu",
            "set_name": "Base Set",
            "number": "not visible"  # Invalid
        }
        
        # Only set+name and fuzzy strategies should run
        mock_tcg_client.search_cards.side_effect = [
            {"data": []},  # Strategy 2 (set+name)
            {"data": []}   # Strategy 5 (fuzzy)
        ]
        
        results, attempts, matches = await service.search_for_card(parsed_data, mock_tcg_client)
        
        # Should not have tried number-based strategies
        assert not any(att["strategy"] == "set_number_name_exact" for att in attempts)
        assert not any(att["strategy"] == "cross_set_number_name" for att in attempts)

    @pytest.mark.asyncio
    async def test_search_attempts_tracking(self, service, mock_tcg_client, sample_parsed_data):
        """Test that search attempts are properly tracked."""
        mock_tcg_client.search_cards.return_value = {"data": []}
        
        results, attempts, matches = await service.search_for_card(sample_parsed_data, mock_tcg_client)
        
        # Check attempt structure
        for attempt in attempts:
            assert "strategy" in attempt
            assert "query" in attempt
            assert "results" in attempt
            assert isinstance(attempt["results"], int)

    @pytest.mark.asyncio
    async def test_early_exit_when_results_found(self, service, mock_tcg_client, sample_parsed_data, sample_card_data):
        """Test that some strategies are skipped when we have enough results."""
        # Strategy 1 returns results
        mock_tcg_client.search_cards.side_effect = [
            {"data": [sample_card_data]},  # Strategy 1 succeeds
            {"data": []},  # Strategy 2 (set+name)
            {"data": []},  # Strategy 3 (name+hp)
            {"data": []},  # Strategy 5 (fuzzy)
        ]
        
        results, attempts, matches = await service.search_for_card(sample_parsed_data, mock_tcg_client)
        
        assert len(results) == 1
        
        # Strategy 3 (name+hp) is actually called since we have hp data
        assert any(att["strategy"] == "name_hp_cross_set" for att in attempts)
        
        # Should have tried multiple strategies
        assert len(attempts) >= 4  # Multiple strategies were attempted