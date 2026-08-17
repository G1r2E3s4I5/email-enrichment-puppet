"""Regression tests for person-specific email candidate generation, single full-name field parsing, role-fallback isolation, and candidate ranking priority."""

import pytest
from app.utils.string_normalizer import normalize_name_input
from app.services.email_pattern_service import EmailPatternService
from app.services.email_generation_pipeline import EmailGenerationPipeline
from app.services.pattern_rank_service import PatternRankService


def test_named_person_generates_person_specific_candidates_without_role_emails():
    """Requirement 9A: John Doe + Stripe must generate person-specific candidates; contact@stripe.com MUST NOT be included."""
    norm = normalize_name_input("John", "Doe")
    pattern_service = EmailPatternService()

    candidates = pattern_service.generate_candidate_permutations(name=norm, domain="stripe.com")
    cand_emails = [c[0] for c in candidates]

    # Verify person-specific candidates are generated
    assert "john.doe@stripe.com" in cand_emails
    assert "jdoe@stripe.com" in cand_emails
    assert "john@stripe.com" in cand_emails
    assert "j.doe@stripe.com" in cand_emails
    assert "johndoe@stripe.com" in cand_emails

    # Verify generic role emails are NOT present
    assert "contact@stripe.com" not in cand_emails
    assert "info@stripe.com" not in cand_emails
    assert "hello@stripe.com" not in cand_emails
    assert "sales@stripe.com" not in cand_emails
    assert "support@stripe.com" not in cand_emails


def test_single_full_name_field_parsing():
    """Requirement 9B: Single full-name string 'John Doe' must be correctly split into first_name and last_name."""
    norm = normalize_name_input("John Doe", None)
    assert norm.first_name == "john"
    assert norm.last_name == "doe"
    assert norm.first_initial == "j"
    assert norm.last_initial == "d"

    norm_multi = normalize_name_input("John Michael Doe", "")
    assert norm_multi.first_name == "john"
    assert norm_multi.last_name == "doe"
    assert norm_multi.middle_name == "michael"


@pytest.mark.asyncio
async def test_no_person_name_generates_role_fallback_candidates():
    """Requirement 9C: Company-only row (no person name) generates generic role fallback candidates."""
    pipeline = EmailGenerationPipeline()
    res_map = await pipeline.generate_job_candidates_batch(
        job_id="00000000-0000-0000-0000-000000000001",
        row_specs=[
            {
                "row_number": 1,
                "domain": "stripe.com",
                "first_name": "",
                "last_name": "",
            }
        ],
    )
    row_cands = res_map.get(1, [])
    cand_emails = [c.candidate_email for c in row_cands]

    assert len(cand_emails) > 0
    assert any("info@stripe.com" in e for e in cand_emails)
    assert any("contact@stripe.com" in e for e in cand_emails)


def test_ranking_does_not_prefer_role_account_for_named_person():
    """Requirement 9D: Candidate ranking does not prefer contact@ or info@ over a named person's email."""
    norm = normalize_name_input("John", "Doe")
    pattern_service = EmailPatternService()
    cands = pattern_service.generate_candidate_permutations(name=norm, domain="stripe.com")
    cand_emails = [c[0] for c in cands]

    # Role accounts are completely excluded for named person
    for role_prefix in ["contact@", "info@", "admin@", "support@", "sales@"]:
        assert not any(role_prefix in email for email in cand_emails)

    rank_service = PatternRankService()
    ranked = rank_service.rank_and_deduplicate_candidates(raw_candidates=cands, normalized_name=norm)

    # Top ranked candidate must be Tier 1 person-specific email
    top_email = ranked[0].candidate_email
    assert top_email in ["john.doe@stripe.com", "johndoe@stripe.com", "jdoe@stripe.com", "john@stripe.com"]
