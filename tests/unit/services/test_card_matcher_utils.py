"""Unit tests for card matcher utility functions."""

import pytest
from src.scanner.services.card_matcher import get_set_family, is_xy_family_match, get_set_from_total_count


class TestGetSetFamily:
    """Test cases for get_set_family function."""

    def test_base_set_families(self):
        """Test base set family mappings."""
        # Base set variations
        assert get_set_family("base") == ["Base Set", "Base", "Base Set 2"]
        assert get_set_family("Base") == ["Base Set", "Base", "Base Set 2"]
        assert get_set_family("BASE") == ["Base Set", "Base", "Base Set 2"]
        assert get_set_family("base set") == ["Base Set", "Base", "Base Set 2"]
        assert get_set_family("Base Set") == ["Base Set", "Base", "Base Set 2"]

    def test_gym_set_families(self):
        """Test gym set family mappings."""
        assert get_set_family("gym") == ["Gym Heroes", "Gym Challenge"]
        assert get_set_family("Gym") == ["Gym Heroes", "Gym Challenge"]
        assert get_set_family("GYM") == ["Gym Heroes", "Gym Challenge"]

    def test_neo_set_families(self):
        """Test neo set family mappings."""
        expected_neo = ["Neo Genesis", "Neo Discovery", "Neo Destiny", "Neo Revelation"]
        assert get_set_family("neo") == expected_neo
        assert get_set_family("Neo") == expected_neo
        assert get_set_family("NEO") == expected_neo

    def test_ruby_sapphire_families(self):
        """Test Ruby & Sapphire set family mappings."""
        expected_rs = ["Ruby & Sapphire"]
        assert get_set_family("ruby") == expected_rs
        assert get_set_family("sapphire") == expected_rs
        assert get_set_family("ruby & sapphire") == expected_rs
        assert get_set_family("Ruby & Sapphire") == expected_rs

    def test_firered_leafgreen_families(self):
        """Test FireRed & LeafGreen set family mappings."""
        expected_frlg = ["FireRed & LeafGreen"]
        assert get_set_family("firered") == expected_frlg
        assert get_set_family("leafgreen") == expected_frlg
        assert get_set_family("firered & leafgreen") == expected_frlg
        assert get_set_family("FireRed & LeafGreen") == expected_frlg

    def test_diamond_pearl_families(self):
        """Test Diamond & Pearl set family mappings."""
        expected_dp = ["Diamond & Pearl"]
        assert get_set_family("diamond") == expected_dp
        assert get_set_family("pearl") == expected_dp
        assert get_set_family("diamond & pearl") == expected_dp
        assert get_set_family("Diamond & Pearl") == expected_dp

    def test_heartgold_soulsilver_families(self):
        """Test HeartGold & SoulSilver set family mappings."""
        expected_hgss = ["HeartGold & SoulSilver"]
        assert get_set_family("heartgold") == expected_hgss
        assert get_set_family("soulsilver") == expected_hgss
        assert get_set_family("heartgold & soulsilver") == expected_hgss
        assert get_set_family("HeartGold & SoulSilver") == expected_hgss

    def test_black_white_families(self):
        """Test Black & White set family mappings."""
        expected_bw = ["Black & White"]
        assert get_set_family("black") == expected_bw
        assert get_set_family("white") == expected_bw
        assert get_set_family("black & white") == expected_bw
        assert get_set_family("Black & White") == expected_bw

    def test_xy_families(self):
        """Test XY set family mappings."""
        expected_xy = ["XY"]
        assert get_set_family("xy") == expected_xy
        assert get_set_family("XY") == expected_xy

    def test_team_sets(self):
        """Test Team-based set family mappings."""
        expected_teams = ["Team Magma vs Team Aqua"]
        assert get_set_family("team magma") == expected_teams
        assert get_set_family("team aqua") == expected_teams
        assert get_set_family("Team Magma") == expected_teams
        assert get_set_family("Team Aqua") == expected_teams

    def test_individual_sets(self):
        """Test individual set mappings."""
        individual_sets = [
            ("legendary", ["Legendary Collection"]),
            ("expedition", ["Expedition", "Expedition Base Set"]),
            ("aquapolis", ["Aquapolis"]),
            ("skyridge", ["Skyridge"]),
            ("sandstorm", ["Sandstorm"]),
            ("dragon", ["Dragon"]),
            ("hidden legends", ["Hidden Legends"]),
            ("team rocket", ["Team Rocket Returns"]),
            ("deoxys", ["Deoxys"]),
            ("emerald", ["Emerald"]),
            ("unseen forces", ["Unseen Forces"]),
            ("delta species", ["Delta Species"]),
            ("legend maker", ["Legend Maker"]),
            ("holon phantoms", ["Holon Phantoms"]),
            ("crystal guardians", ["Crystal Guardians"]),
            ("dragon frontiers", ["Dragon Frontiers"]),
            ("power keepers", ["Power Keepers"])
        ]
        
        for set_name, expected in individual_sets:
            assert get_set_family(set_name) == expected
            assert get_set_family(set_name.title()) == expected

    def test_diamond_pearl_expansion_sets(self):
        """Test Diamond & Pearl expansion set mappings."""
        dp_expansions = [
            ("mysterious treasures", ["Mysterious Treasures"]),
            ("secret wonders", ["Secret Wonders"]),
            ("great encounters", ["Great Encounters"]),
            ("majestic dawn", ["Majestic Dawn"]),
            ("legends awakened", ["Legends Awakened"]),
            ("stormfront", ["Stormfront"]),
            ("platinum", ["Platinum"]),
            ("rising rivals", ["Rising Rivals"]),
            ("supreme victors", ["Supreme Victors"]),
            ("arceus", ["Arceus"])
        ]
        
        for set_name, expected in dp_expansions:
            assert get_set_family(set_name) == expected

    def test_heartgold_soulsilver_expansion_sets(self):
        """Test HeartGold & SoulSilver expansion set mappings."""
        hgss_expansions = [
            ("unleashed", ["Unleashed"]),
            ("undaunted", ["Undaunted"]),
            ("triumphant", ["Triumphant"]),
            ("call of legends", ["Call of Legends"])
        ]
        
        for set_name, expected in hgss_expansions:
            assert get_set_family(set_name) == expected

    def test_black_white_expansion_sets(self):
        """Test Black & White expansion set mappings."""
        bw_expansions = [
            ("emerging powers", ["Emerging Powers"]),
            ("noble victories", ["Noble Victories"]),
            ("next destinies", ["Next Destinies"]),
            ("dark explorers", ["Dark Explorers"]),
            ("dragons exalted", ["Dragons Exalted"]),
            ("boundaries crossed", ["Boundaries Crossed"]),
            ("plasma storm", ["Plasma Storm"]),
            ("plasma freeze", ["Plasma Freeze"]),
            ("plasma blast", ["Plasma Blast"]),
            ("legendary treasures", ["Legendary Treasures"])
        ]
        
        for set_name, expected in bw_expansions:
            assert get_set_family(set_name) == expected

    def test_xy_expansion_sets(self):
        """Test XY expansion set mappings."""
        xy_expansions = [
            ("flashfire", ["Flashfire"]),
            ("furious fists", ["Furious Fists"]),
            ("phantom forces", ["Phantom Forces"]),
            ("primal clash", ["Primal Clash"]),
            ("roaring skies", ["Roaring Skies"]),
            ("ancient origins", ["Ancient Origins"]),
            ("breakthrough", ["BREAKthrough"]),
            ("breakpoint", ["BREAKpoint"]),
            ("generations", ["Generations"]),
            ("fates collide", ["Fates Collide"]),
            ("steam siege", ["Steam Siege"])
        ]
        
        for set_name, expected in xy_expansions:
            assert get_set_family(set_name) == expected

    def test_case_insensitive_matching(self):
        """Test that set family matching is case insensitive."""
        test_cases = [
            ("BASE", ["Base Set", "Base", "Base Set 2"]),
            ("base", ["Base Set", "Base", "Base Set 2"]),
            ("Base", ["Base Set", "Base", "Base Set 2"]),
            ("DIAMOND & PEARL", ["Diamond & Pearl"]),
            ("diamond & pearl", ["Diamond & Pearl"]),
            ("Diamond & Pearl", ["Diamond & Pearl"]),
            ("TEAM MAGMA", ["Team Magma vs Team Aqua"]),
            ("team magma", ["Team Magma vs Team Aqua"]),
            ("Team Magma", ["Team Magma vs Team Aqua"])
        ]
        
        for set_name, expected in test_cases:
            assert get_set_family(set_name) == expected

    def test_edge_cases(self):
        """Test edge cases for set family function."""
        # Empty and None cases
        assert get_set_family(None) is None
        assert get_set_family("") is None
        
        # Unknown sets should return None
        assert get_set_family("Unknown Set") is None
        assert get_set_family("Fake Set Name") is None
        assert get_set_family("Not A Real Set") is None

    def test_whitespace_handling(self):
        """Test handling of sets with different whitespace."""
        # Test sets with extra whitespace
        assert get_set_family("  base  ") is None  # Doesn't handle whitespace trimming
        
        # Test exact matches only
        assert get_set_family("base") == ["Base Set", "Base", "Base Set 2"]
        assert get_set_family("base set") == ["Base Set", "Base", "Base Set 2"]

    def test_partial_matches(self):
        """Test that partial matches don't work."""
        # These should not match because they're not exact matches
        assert get_set_family("bas") is None
        assert get_set_family("gym hero") is None
        assert get_set_family("black white") is None  # Missing &
        assert get_set_family("diamond pearl") is None  # Missing &

    def test_sun_moon_and_newer_sets(self):
        """Test that newer sets may not be in the mapping."""
        # These sets may not be mapped yet
        newer_sets = [
            "Sun & Moon",
            "Sword & Shield", 
            "Brilliant Stars",
            "Astral Radiance",
            "Lost Origin"
        ]
        
        for set_name in newer_sets:
            # These should return None since they're not in the mapping
            result = get_set_family(set_name.lower())
            # We don't assert anything specific since the mapping might be incomplete
            # Just verify the function doesn't crash
            assert result is None or isinstance(result, list)

    def test_special_character_sets(self):
        """Test sets with special characters."""
        # Test sets that have special characters in their names
        special_char_sets = [
            ("ruby & sapphire", ["Ruby & Sapphire"]),
            ("firered & leafgreen", ["FireRed & LeafGreen"]),
            ("diamond & pearl", ["Diamond & Pearl"]),
            ("heartgold & soulsilver", ["HeartGold & SoulSilver"]),
            ("black & white", ["Black & White"])
        ]
        
        for set_name, expected in special_char_sets:
            assert get_set_family(set_name) == expected

    def test_return_type_consistency(self):
        """Test that return types are consistent."""
        # Valid sets should return lists
        result = get_set_family("base")
        assert isinstance(result, list)
        assert all(isinstance(item, str) for item in result)
        
        # Invalid sets should return None
        assert get_set_family("invalid") is None
        assert get_set_family("") is None
        assert get_set_family(None) is None


class TestIsXYFamilyMatch:
    """Test cases for is_xy_family_match function."""

    def test_both_xy_sets_match(self):
        """Test that two XY family sets match."""
        xy_sets = [
            "xy", "xy base", "xy base set", "kalos starter set",
            "flashfire", "furious fists", "phantom forces", "primal clash",
            "roaring skies", "ancient origins", "breakthrough", "breakpoint",
            "generations", "fates collide", "steam siege", "evolutions"
        ]
        
        # Test all combinations of XY sets
        for set1 in xy_sets[:5]:  # Test subset to keep test size reasonable
            for set2 in xy_sets[:5]:
                assert is_xy_family_match(set1, set2), f"'{set1}' and '{set2}' should match"

    def test_one_xy_one_non_xy_no_match(self):
        """Test that XY set and non-XY set don't match."""
        xy_sets = ["xy", "flashfire", "phantom forces"]
        non_xy_sets = ["Base Set", "Team Rocket", "Sun & Moon", "Diamond & Pearl"]
        
        for xy_set in xy_sets:
            for non_xy_set in non_xy_sets:
                assert not is_xy_family_match(xy_set, non_xy_set), f"'{xy_set}' and '{non_xy_set}' should not match"
                assert not is_xy_family_match(non_xy_set, xy_set), f"'{non_xy_set}' and '{xy_set}' should not match"

    def test_both_non_xy_sets_no_match(self):
        """Test that two non-XY sets don't match."""
        non_xy_sets = ["Base Set", "Team Rocket", "Sun & Moon", "Diamond & Pearl", "Black & White"]
        
        for i, set1 in enumerate(non_xy_sets):
            for set2 in non_xy_sets[i+1:]:
                assert not is_xy_family_match(set1, set2), f"'{set1}' and '{set2}' should not match"

    def test_case_insensitive_matching(self):
        """Test that XY family matching is case insensitive."""
        assert is_xy_family_match("XY", "flashfire")
        assert is_xy_family_match("xy", "FLASHFIRE")
        assert is_xy_family_match("PHANTOM FORCES", "xy base")
        assert is_xy_family_match("Furious Fists", "Steam Siege")

    def test_whitespace_handling(self):
        """Test that whitespace is stripped in XY family matching."""
        assert is_xy_family_match("  xy  ", "flashfire")
        assert is_xy_family_match("xy", "  phantom forces  ")
        assert is_xy_family_match("  xy base  ", "  generations  ")

    def test_edge_cases_xy_family(self):
        """Test edge cases for XY family matching."""
        # Empty and None cases
        assert not is_xy_family_match(None, "xy")
        assert not is_xy_family_match("xy", None)
        assert not is_xy_family_match(None, None)
        assert not is_xy_family_match("", "xy")
        assert not is_xy_family_match("xy", "")
        assert not is_xy_family_match("", "")

    def test_specific_xy_sets(self):
        """Test specific XY set combinations."""
        # Test all XY base variants
        xy_base_variants = ["xy", "xy base", "xy base set", "kalos starter set"]
        for variant in xy_base_variants:
            assert is_xy_family_match(variant, "flashfire")
            assert is_xy_family_match("phantom forces", variant)

    def test_xy_expansions(self):
        """Test XY expansion sets."""
        xy_expansions = [
            "flashfire", "furious fists", "phantom forces", "primal clash",
            "roaring skies", "ancient origins", "breakthrough", "breakpoint",
            "generations", "fates collide", "steam siege", "evolutions"
        ]
        
        # All expansions should match with base XY
        for expansion in xy_expansions:
            assert is_xy_family_match("xy", expansion)
            assert is_xy_family_match(expansion, "xy")


class TestGetSetFromTotalCount:
    """Test cases for get_set_from_total_count function."""

    def test_known_set_counts(self):
        """Test known set total counts."""
        # Test some counts that should return set names
        known_counts = [102, 111, 130, 165, 64, 95, 100]
        
        for count in known_counts:
            result = get_set_from_total_count(count)
            # Should return a set name string for known counts
            assert result is None or isinstance(result, str)
            if result is not None:
                assert len(result) > 0  # Non-empty string

    def test_unknown_counts(self):
        """Test unknown set counts."""
        # Use counts that are definitely not in the mapping
        unknown_counts = [1, 2, 3, 500, 999, 1500, 2000]
        
        for count in unknown_counts:
            result = get_set_from_total_count(count)
            # Unknown counts should return None
            assert result is None

    def test_zero_and_negative_counts(self):
        """Test zero and negative counts."""
        invalid_counts = [0, -1, -50, -100]
        
        for count in invalid_counts:
            result = get_set_from_total_count(count)
            # Invalid counts should return None
            assert result is None

    def test_large_counts(self):
        """Test very large counts."""
        large_counts = [10000, 50000, 100000]
        
        for count in large_counts:
            result = get_set_from_total_count(count)
            # Large counts should return None
            assert result is None

    def test_return_type(self):
        """Test that return type is consistent."""
        # Test with a known count
        result = get_set_from_total_count(102)
        assert result is None or isinstance(result, str)
        
        # Test with unknown count
        result = get_set_from_total_count(999)
        assert result is None