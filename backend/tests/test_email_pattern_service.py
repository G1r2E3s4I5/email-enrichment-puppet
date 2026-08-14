"""Unit tests for EmailPatternService (trained from Apollo real-world data)."""

from app.services.email_pattern_service import EmailPatternService
from app.utils.string_normalizer import normalize_name_input


def test_pattern_library_count() -> None:
    """Test that pattern library contains 20-30 supported corporate patterns."""
    svc = EmailPatternService()
    patterns = svc.get_supported_patterns()
    assert len(patterns) >= 20
    assert len(patterns) <= 35


def test_generate_candidate_permutations_full_name() -> None:
    """Test candidate permutation generation for John Doe at microsoft.com."""
    svc = EmailPatternService()
    name = normalize_name_input("John", "Doe")
    tier1_candidates = svc.generate_tier1_permutations(name, "microsoft.com")
    tier2_candidates = svc.generate_tier2_permutations(name, "microsoft.com")
    all_candidates = svc.generate_candidate_permutations(name, "microsoft.com")

    tier1_emails = [c[0] for c in tier1_candidates]
    tier2_emails = [c[0] for c in tier2_candidates]
    all_emails = [c[0] for c in all_candidates]

    # Verify Tier 1: High-frequency patterns from Apollo data
    assert "john.doe@microsoft.com" in tier1_emails      # first.last (56.8%)
    assert "john.d@microsoft.com" in tier1_emails         # firstname.l (16.0%)
    assert "john@microsoft.com" in tier1_emails           # first (13.6%)
    assert "jdoe@microsoft.com" in tier1_emails           # firstinitiallastname (4.9%)
    assert "johndoe@microsoft.com" in tier1_emails        # firstlast (4.9%)
    assert "j.doe@microsoft.com" in tier1_emails          # f.lastname
    assert "johnd@microsoft.com" in tier1_emails          # firstlastinitial
    assert "doe.john@microsoft.com" in tier1_emails       # last.first (2.5%)
    assert "john_doe@microsoft.com" in tier1_emails       # first_last
    assert "john-doe@microsoft.com" in tier1_emails       # first-last

    # Verify Tier 2: Less common patterns
    assert "doe.j@microsoft.com" in tier2_emails          # last.f (1.2%)
    assert "doej@microsoft.com" in tier2_emails           # lastnamefirstinitial
    assert "doe@microsoft.com" in tier2_emails            # last

    # Verify numbered patterns are still generated (now Tier 3)
    assert "john1@microsoft.com" in all_emails
    assert "john.doe1@microsoft.com" in all_emails
    assert "jdoe1@microsoft.com" in all_emails

    # Verify first.last confidence is highest
    first_last_conf = next(c[2] for c in tier1_candidates if c[0] == "john.doe@microsoft.com")
    firstname_l_conf = next(c[2] for c in tier1_candidates if c[0] == "john.d@microsoft.com")
    assert first_last_conf > firstname_l_conf > 0.85, "first.last should be highest, firstname.l second"


def test_generate_candidate_permutations_first_name_only() -> None:
    """Test candidate generation gracefully handles missing last name."""
    svc = EmailPatternService()
    name = normalize_name_input("John", "")
    candidates = svc.generate_candidate_permutations(name, "microsoft.com")

    emails = [c[0] for c in candidates]
    assert "john@microsoft.com" in emails
    # Patterns requiring last name should be skipped safely
    assert "john.doe@microsoft.com" not in emails


