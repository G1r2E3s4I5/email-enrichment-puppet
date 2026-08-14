"""Unit tests for company name normalization utility."""

import pytest
from app.utils.normalization import normalize_company_name


def test_normalize_company_name_basic() -> None:
    """Test standard whitespace and lowercasing."""
    assert normalize_company_name(" Microsoft  ") == "microsoft"
    assert normalize_company_name("GOOGLE") == "google"


def test_normalize_company_name_multiple_spaces() -> None:
    """Test collapsing multiple spaces into a single space."""
    assert normalize_company_name("  Apple   Inc  ") == "apple inc"
    assert normalize_company_name("Amazon   Web    Services") == "amazon web services"


def test_normalize_company_name_punctuation() -> None:
    """Test stripping leading and trailing punctuation."""
    assert normalize_company_name("!Microsoft!") == "microsoft"
    assert normalize_company_name(",,, Meta Platforms Inc. ...") == "meta platforms inc"
    assert normalize_company_name("--- Open AI ---") == "open ai"


def test_normalize_company_name_empty_edge_cases() -> None:
    """Test empty input strings and whitespace edge cases."""
    assert normalize_company_name("") == ""
    assert normalize_company_name("   ") == ""
    assert normalize_company_name("!!!") == ""
