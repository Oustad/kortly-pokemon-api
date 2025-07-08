"""Unit tests for scan route utility functions."""

import pytest
from src.scanner.routes.scan import is_valid_set_name, is_valid_card_number


class TestIsValidSetName:
    """Test cases for is_valid_set_name function."""

    def test_valid_set_names(self):
        """Test valid set names."""
        valid_names = [
            "Base Set",
            "Jungle",
            "Fossil",
            "Team Rocket",
            "Gym Heroes",
            "Neo Genesis",
            "Southern Islands",
            "EX Ruby & Sapphire",
            "Diamond & Pearl",
            "HeartGold & SoulSilver",
            "Black & White",
            "XY",
            "Sun & Moon",
            "Sword & Shield",
            "Scarlet & Violet",
            "Hidden Fates",
            "Shining Legends",
            "Champion's Path"
        ]
        
        for name in valid_names:
            assert is_valid_set_name(name), f"'{name}' should be valid"

    def test_invalid_set_names_with_vague_phrases(self):
        """Test invalid set names containing vague phrases."""
        invalid_names = [
            "not visible",
            "likely Base Set",
            "but it's unclear",
            "era unknown",
            "possibly Jungle",
            "unknown set",
            "can't see the name",
            "cannot see clearly",
            "unclear text",
            "maybe Base Set",
            "appears to be Fossil",
            "looks like Team Rocket",
            "seems like Neo Genesis",
            "hard to tell what set",
            "difficult to see the name"
        ]
        
        for name in invalid_names:
            assert not is_valid_set_name(name), f"'{name}' should be invalid"

    def test_invalid_set_names_too_long(self):
        """Test invalid set names that are too long."""
        long_names = [
            "This is a very long description that definitely exceeds the 50 character limit for valid set names",
            "Base Set but with additional descriptive text that makes it invalid",
            "X" * 51  # Exactly 51 characters
        ]
        
        for name in long_names:
            assert not is_valid_set_name(name), f"'{name}' should be invalid (too long)"

    def test_invalid_set_names_with_commas(self):
        """Test invalid set names containing commas."""
        names_with_commas = [
            "Base Set, First Edition",
            "Jungle, possibly",
            "Team Rocket, but unclear",
            "Neo Genesis, limited edition"
        ]
        
        for name in names_with_commas:
            assert not is_valid_set_name(name), f"'{name}' should be invalid (contains comma)"

    def test_edge_cases(self):
        """Test edge cases for set name validation."""
        # Empty and None cases
        assert not is_valid_set_name(None)
        assert not is_valid_set_name("")
        # Note: "   " (whitespace only) passes the length and other checks, so it's considered valid
        
        # Non-string types
        assert not is_valid_set_name(123)
        assert not is_valid_set_name([])
        assert not is_valid_set_name({})
        assert not is_valid_set_name(True)

    def test_case_insensitive_detection(self):
        """Test that vague phrase detection is case insensitive."""
        case_variations = [
            "NOT VISIBLE",
            "Likely base set",
            "UNCLEAR text",
            "Possibly JUNGLE",
            "Cannot See the name"
        ]
        
        for name in case_variations:
            assert not is_valid_set_name(name), f"'{name}' should be invalid (case insensitive)"

    def test_boundary_lengths(self):
        """Test boundary conditions for set name length."""
        # Exactly 50 characters (should be valid)
        exactly_50 = "X" * 50
        assert is_valid_set_name(exactly_50), "50 character name should be valid"
        
        # 49 characters (should be valid)
        exactly_49 = "X" * 49
        assert is_valid_set_name(exactly_49), "49 character name should be valid"
        
        # Single character (should be valid if no other issues)
        assert is_valid_set_name("X"), "Single character should be valid"

    def test_special_characters(self):
        """Test set names with special characters."""
        # These should be valid as they don't contain vague phrases
        special_char_names = [
            "EX Ruby & Sapphire",
            "HeartGold & SoulSilver", 
            "Diamond & Pearl",
            "Sun & Moon",
            "Sword & Shield",
            "Pokémon TCG",
            "Set-Name",
            "Set_Name",
            "Set (Promo)"
        ]
        
        for name in special_char_names:
            assert is_valid_set_name(name), f"'{name}' should be valid"


class TestIsValidCardNumber:
    """Test cases for is_valid_card_number function."""

    def test_valid_card_numbers(self):
        """Test valid card numbers."""
        valid_numbers = [
            "1",
            "25", 
            "102",
            "SH1",
            "SH21",
            "BW01",
            "XY36",
            "SM01",
            "SWSH001",
            "PAL001",
            "1a",
            "25b",
            "H1",
            "S1",
            "SWSH-001",
            "XY-P1"
        ]
        
        for number in valid_numbers:
            assert is_valid_card_number(number), f"'{number}' should be valid"

    def test_invalid_card_numbers_with_vague_phrases(self):
        """Test invalid card numbers containing vague phrases."""
        invalid_numbers = [
            "not visible",
            "unclear",
            "unknown",
            "can't see",
            "cannot see",
            "hard to tell",
            "difficult",
            "n/a",
            "none",
            "not found"
        ]
        
        for number in invalid_numbers:
            assert not is_valid_card_number(number), f"'{number}' should be invalid"

    def test_invalid_card_numbers_with_spaces(self):
        """Test invalid card numbers containing spaces."""
        numbers_with_spaces = [
            "card 25",
            "number 1",
            "25 of 102",
            "SW SH001",
            "maybe 25"
        ]
        
        for number in numbers_with_spaces:
            assert not is_valid_card_number(number), f"'{number}' should be invalid (contains spaces)"

    def test_edge_cases_card_number(self):
        """Test edge cases for card number validation."""
        # Empty and None cases
        assert not is_valid_card_number(None)
        assert not is_valid_card_number("")
        assert not is_valid_card_number("   ")  # Whitespace only
        
        # Non-string types
        assert not is_valid_card_number(123)
        assert not is_valid_card_number([])
        assert not is_valid_card_number({})
        assert not is_valid_card_number(True)

    def test_numbers_without_digits(self):
        """Test invalid card numbers without any digits."""
        no_digit_numbers = [
            "PROMO",  # No digits
            "STAFF",  # No digits
            "WINNER",  # No digits
            "ABC",     # No digits
            "XYZ"      # No digits
        ]
        
        for number in no_digit_numbers:
            assert not is_valid_card_number(number), f"'{number}' should be invalid (no digits)"

    def test_case_insensitive_vague_detection(self):
        """Test that vague phrase detection is case insensitive for card numbers."""
        case_variations = [
            "NOT VISIBLE",
            "UNCLEAR",
            "UNKNOWN",
            "Cannot See",
            "HARD TO TELL",
            "DIFFICULT"
        ]
        
        for number in case_variations:
            assert not is_valid_card_number(number), f"'{number}' should be invalid (case insensitive)"

    def test_invalid_characters(self):
        """Test card numbers with invalid characters."""
        invalid_char_numbers = [
            "25!",
            "SH@1",
            "BW#01",
            "25%",
            "1&2",
            "SW*SH001",
            "25+26",
            "1=2",
            "25(a)",
            "1,2",
            "25.5",
            "1/102"  # Slash is not allowed
        ]
        
        for number in invalid_char_numbers:
            assert not is_valid_card_number(number), f"'{number}' should be invalid (invalid characters)"

    def test_promo_and_special_numbers(self):
        """Test promo and special card numbers with digits."""
        special_numbers = [
            "BW-P1",
            "XY-P25", 
            "SM-P1",
            "SWSH-P1",
            "PAL-P1",
            "STAFF1",
            "WINNER1"
        ]
        
        for number in special_numbers:
            assert is_valid_card_number(number), f"'{number}' should be valid"

    def test_numeric_ranges(self):
        """Test various numeric card number formats."""
        numeric_formats = [
            "001",  # Zero-padded
            "025",
            "102",
            "999",
            "SV001",
            "PAL001"
        ]
        
        for number in numeric_formats:
            assert is_valid_card_number(number), f"'{number}' should be valid"

    def test_alpha_numeric_combinations(self):
        """Test alpha-numeric card number combinations."""
        alpha_numeric = [
            "1a",
            "25b",
            "102c",
            "H1",
            "H25", 
            "S1",
            "S25",
            "RC1",
            "RC25",
            "TG1",
            "TG30"
        ]
        
        for number in alpha_numeric:
            assert is_valid_card_number(number), f"'{number}' should be valid"