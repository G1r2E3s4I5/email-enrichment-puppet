"""Unit tests for string normalizer utility."""

from app.utils.string_normalizer import (
    normalize_name_input,
    remove_accents,
    sanitize_name_token,
)


def test_remove_accents() -> None:
    """Test diacritics and accent mark stripping."""
    assert remove_accents("José María") == "Jose Maria"
    assert remove_accents("Müller") == "Muller"
    assert remove_accents("François") == "Francois"
    assert remove_accents("González") == "Gonzalez"
    assert remove_accents("Renée") == "Renee"
    assert remove_accents("") == ""


def test_sanitize_name_token() -> None:
    """Test non-alphanumeric character removal from single token."""
    assert sanitize_name_token("O'Connor") == "oconnor"
    assert sanitize_name_token("Jean-Luc") == "jeanluc"
    assert sanitize_name_token("St. John") == "stjohn"
    assert sanitize_name_token("   sam   ") == "sam"


def test_normalize_name_input_full_name() -> None:
    """Test standard first and last name normalization."""
    name = normalize_name_input("Sam", "Altman")
    assert name.first_name == "sam"
    assert name.last_name == "altman"
    assert name.first_initial == "s"
    assert name.last_initial == "a"
    assert name.middle_name is None


def test_normalize_name_input_accents_and_compound() -> None:
    """Test compound names with accents and extra spaces."""
    name = normalize_name_input("  José   María  ", "González")
    assert name.first_name == "jose"
    assert name.middle_name == "maria"
    assert name.last_name == "gonzalez"
    assert name.first_initial == "j"
    assert name.middle_initial == "m"
    assert name.last_initial == "g"


def test_normalize_name_input_hyphenated_and_apostrophe() -> None:
    """Test hyphenated and apostrophe name handling."""
    name = normalize_name_input("Mary-Jane", "O'Connor")
    assert name.first_name == "maryjane"
    assert name.last_name == "oconnor"
    assert name.first_initial == "m"
    assert name.last_initial == "o"


def test_normalize_name_input_single_full_name() -> None:
    """Test full name provided in single string input."""
    name = normalize_name_input("John Doe")
    assert name.first_name == "john"
    assert name.last_name == "doe"
    assert name.first_initial == "j"
    assert name.last_initial == "d"

