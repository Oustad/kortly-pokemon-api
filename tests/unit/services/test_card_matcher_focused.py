"""Focused tests for card_matcher.py utility functions that we can verify."""

import pytest
from typing import Dict, List, Optional, Any

from src.scanner.services.card_matcher import (
    get_set_family,
    is_xy_family_match,
    is_pokemon_variant_match
)


class TestGetSetFamily:
    """Test get_set_family function - testing known mappings."""
    
    def test_get_set_family_base_set(self):
        """Test base set family mapping."""
        result = get_set_family("base")
        assert result == ["Base Set", "Base", "Base Set 2"]
        
        result = get_set_family("Base Set")
        assert result == ["Base Set", "Base", "Base Set 2"]
    
    def test_get_set_family_gym_series(self):
        """Test gym series family mapping."""
        result = get_set_family("gym")
        assert result == ["Gym Heroes", "Gym Challenge"]
    
    def test_get_set_family_neo_series(self):
        """Test neo series family mapping."""
        result = get_set_family("neo")
        expected = ["Neo Genesis", "Neo Discovery", "Neo Destiny", "Neo Revelation"]
        assert result == expected
    
    def test_get_set_family_xy_series(self):
        """Test XY series family mapping."""
        result = get_set_family("xy")
        assert result == ["XY"]
    
    def test_get_set_family_black_white(self):
        """Test Black & White series family mapping."""
        result = get_set_family("black")
        assert result == ["Black & White"]
        
        result = get_set_family("white")
        assert result == ["Black & White"]
        
        result = get_set_family("black & white")
        assert result == ["Black & White"]
    
    def test_get_set_family_diamond_pearl(self):
        """Test Diamond & Pearl series family mapping."""
        result = get_set_family("diamond")
        assert result == ["Diamond & Pearl"]
        
        result = get_set_family("pearl")
        assert result == ["Diamond & Pearl"]
    
    def test_get_set_family_case_insensitive(self):
        """Test case insensitive matching."""
        result = get_set_family("BASE")
        assert result == ["Base Set", "Base", "Base Set 2"]
        
        result = get_set_family("GYM")
        assert result == ["Gym Heroes", "Gym Challenge"]
    
    def test_get_set_family_none_input(self):
        """Test get_set_family with None input."""
        result = get_set_family(None)
        assert result is None
    
    def test_get_set_family_empty_string(self):
        """Test get_set_family with empty string."""
        result = get_set_family("")
        assert result is None
    
    def test_get_set_family_unknown_set(self):
        """Test get_set_family with unknown set name."""
        result = get_set_family("unknown set")
        assert result is None
        
        result = get_set_family("random name")
        assert result is None


class TestIsXYFamilyMatch:
    """Test is_xy_family_match function - tests if both sets are in XY family."""
    
    def test_is_xy_family_match_both_xy_sets(self):
        """Test when both sets are in XY family."""
        # Both are XY family sets
        assert is_xy_family_match("xy", "flashfire") is True
        assert is_xy_family_match("flashfire", "furious fists") is True
        assert is_xy_family_match("phantom forces", "primal clash") is True
        assert is_xy_family_match("roaring skies", "ancient origins") is True
        assert is_xy_family_match("breakthrough", "breakpoint") is True
        assert is_xy_family_match("generations", "fates collide") is True
        assert is_xy_family_match("steam siege", "evolutions") is True
    
    def test_is_xy_family_match_same_set(self):
        """Test when both sets are the same XY set."""
        assert is_xy_family_match("xy", "xy") is True
        assert is_xy_family_match("flashfire", "flashfire") is True
        assert is_xy_family_match("generations", "generations") is True
    
    def test_is_xy_family_match_one_non_xy(self):
        """Test when one set is not in XY family."""
        assert is_xy_family_match("xy", "Base Set") is False
        assert is_xy_family_match("Base Set", "flashfire") is False
        assert is_xy_family_match("Team Rocket", "furious fists") is False
        assert is_xy_family_match("phantom forces", "Neo Genesis") is False
    
    def test_is_xy_family_match_both_non_xy(self):
        """Test when both sets are not in XY family."""
        assert is_xy_family_match("Base Set", "Team Rocket") is False
        assert is_xy_family_match("Neo Genesis", "Jungle") is False
        assert is_xy_family_match("Diamond & Pearl", "Platinum") is False
    
    def test_is_xy_family_match_case_insensitive(self):
        """Test case insensitive matching."""
        assert is_xy_family_match("XY", "FLASHFIRE") is True
        assert is_xy_family_match("flashfire", "FURIOUS FISTS") is True
        assert is_xy_family_match("Phantom Forces", "primal clash") is True
    
    def test_is_xy_family_match_none_inputs(self):
        """Test with None inputs."""
        assert is_xy_family_match(None, "xy") is False
        assert is_xy_family_match("xy", None) is False
        assert is_xy_family_match(None, None) is False
    
    def test_is_xy_family_match_empty_strings(self):
        """Test with empty string inputs."""
        assert is_xy_family_match("", "xy") is False
        assert is_xy_family_match("xy", "") is False
        assert is_xy_family_match("", "") is False
    
    def test_is_xy_family_match_whitespace_handling(self):
        """Test whitespace handling."""
        assert is_xy_family_match("  xy  ", "flashfire") is True
        assert is_xy_family_match("furious fists", "  phantom forces  ") is True


class TestIsPokemonVariantMatch:
    """Test is_pokemon_variant_match function."""
    
    def test_is_pokemon_variant_match_exact_match(self):
        """Test exact Pokemon name matches."""
        assert is_pokemon_variant_match("Pikachu", "Pikachu") is True
        assert is_pokemon_variant_match("Charizard", "Charizard") is True
        assert is_pokemon_variant_match("Blastoise", "Blastoise") is True
    
    def test_is_pokemon_variant_match_case_insensitive(self):
        """Test case insensitive matches."""
        assert is_pokemon_variant_match("pikachu", "Pikachu") is True
        assert is_pokemon_variant_match("PIKACHU", "Pikachu") is True
        assert is_pokemon_variant_match("Pikachu", "PIKACHU") is True
        assert is_pokemon_variant_match("ChArIzArD", "charizard") is True
    
    def test_is_pokemon_variant_match_gx_variants(self):
        """Test GX variant matches."""
        # The function treats GX variants as the same Pokemon
        assert is_pokemon_variant_match("Pikachu GX", "Pikachu") is True
        assert is_pokemon_variant_match("Charizard GX", "Charizard") is True
        assert is_pokemon_variant_match("Pikachu", "Pikachu GX") is True
        assert is_pokemon_variant_match("Blastoise GX", "Blastoise") is True
    
    def test_is_pokemon_variant_match_ex_variants(self):
        """Test EX variant matches."""
        # The function treats EX variants as the same Pokemon
        assert is_pokemon_variant_match("Pikachu EX", "Pikachu") is True
        assert is_pokemon_variant_match("Charizard EX", "Charizard") is True
        assert is_pokemon_variant_match("Pikachu", "Pikachu EX") is True
        assert is_pokemon_variant_match("Mewtwo EX", "Mewtwo") is True
    
    def test_is_pokemon_variant_match_v_variants(self):
        """Test V variant matches."""
        assert is_pokemon_variant_match("Pikachu V", "Pikachu V") is True
        assert is_pokemon_variant_match("Charizard V", "Charizard V") is True
        assert is_pokemon_variant_match("Eternatus V", "Eternatus V") is True
    
    def test_is_pokemon_variant_match_vmax_variants(self):
        """Test VMAX variant matches."""
        assert is_pokemon_variant_match("Pikachu VMAX", "Pikachu VMAX") is True
        assert is_pokemon_variant_match("Charizard VMAX", "Charizard VMAX") is True
        assert is_pokemon_variant_match("Eternatus VMAX", "Eternatus VMAX") is True
    
    def test_is_pokemon_variant_match_break_variants(self):
        """Test BREAK variant matches."""
        assert is_pokemon_variant_match("Greninja BREAK", "Greninja BREAK") is True
        assert is_pokemon_variant_match("Trevenant BREAK", "Trevenant BREAK") is True
    
    def test_is_pokemon_variant_match_prime_variants(self):
        """Test Prime variant matches."""
        assert is_pokemon_variant_match("Houndoom Prime", "Houndoom Prime") is True
        assert is_pokemon_variant_match("Typhlosion Prime", "Typhlosion Prime") is True
    
    def test_is_pokemon_variant_match_level_x_variants(self):
        """Test Level X variant matches."""
        assert is_pokemon_variant_match("Dialga LV.X", "Dialga LV.X") is True
        assert is_pokemon_variant_match("Palkia LV.X", "Palkia LV.X") is True
        assert is_pokemon_variant_match("Garchomp LV.X", "Garchomp LV.X") is True
    
    def test_is_pokemon_variant_match_star_variants(self):
        """Test Star variant matches."""
        assert is_pokemon_variant_match("Pikachu ★", "Pikachu ★") is True
        assert is_pokemon_variant_match("Charizard ★", "Charizard ★") is True
    
    def test_is_pokemon_variant_match_delta_species(self):
        """Test Delta Species variant matches."""
        assert is_pokemon_variant_match("Pikachu δ", "Pikachu δ") is True
        assert is_pokemon_variant_match("Charizard δ", "Charizard δ") is True
    
    def test_is_pokemon_variant_match_different_pokemon(self):
        """Test different Pokemon names don't match."""
        assert is_pokemon_variant_match("Pikachu", "Charizard") is False
        assert is_pokemon_variant_match("Blastoise", "Venusaur") is False
        assert is_pokemon_variant_match("Mewtwo", "Mew") is False
        assert is_pokemon_variant_match("Lucario", "Riolu") is False
    
    def test_is_pokemon_variant_match_partial_names(self):
        """Test partial name matches."""
        assert is_pokemon_variant_match("Pika", "Pikachu") is False
        assert is_pokemon_variant_match("Charizard", "Char") is False
        assert is_pokemon_variant_match("Blast", "Blastoise") is False
    
    def test_is_pokemon_variant_match_none_inputs(self):
        """Test None inputs."""
        assert is_pokemon_variant_match(None, "Pikachu") is False
        assert is_pokemon_variant_match("Pikachu", None) is False
        assert is_pokemon_variant_match(None, None) is False
    
    def test_is_pokemon_variant_match_empty_inputs(self):
        """Test empty inputs."""
        assert is_pokemon_variant_match("", "Pikachu") is False
        assert is_pokemon_variant_match("Pikachu", "") is False
        assert is_pokemon_variant_match("", "") is False
    
    def test_is_pokemon_variant_match_whitespace_handling(self):
        """Test whitespace handling."""
        assert is_pokemon_variant_match("  Pikachu  ", "Pikachu") is True
        assert is_pokemon_variant_match("Pikachu", "  Pikachu  ") is True
        assert is_pokemon_variant_match("  Pikachu GX  ", "Pikachu") is True
    
    def test_is_pokemon_variant_match_mixed_variants(self):
        """Test mixed variant types."""
        # Different variants of the same Pokemon should still match
        assert is_pokemon_variant_match("Pikachu EX", "Pikachu GX") is True
        assert is_pokemon_variant_match("Charizard V", "Charizard VMAX") is True
        assert is_pokemon_variant_match("Greninja BREAK", "Greninja GX") is True
    
    def test_is_pokemon_variant_match_base_vs_variant(self):
        """Test base Pokemon vs variant."""
        # Base Pokemon should match variants
        assert is_pokemon_variant_match("Pikachu", "Pikachu GX") is True
        assert is_pokemon_variant_match("Charizard", "Charizard EX") is True
        assert is_pokemon_variant_match("Blastoise", "Blastoise V") is True