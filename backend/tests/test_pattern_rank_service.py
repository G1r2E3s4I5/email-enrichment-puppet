"""Unit tests for PatternRankService."""

from app.services.email_pattern_service import EmailPatternService
from app.services.pattern_rank_service import PatternRankService
from app.utils.string_normalizer import normalize_name_input


def test_pattern_ranking_ordering_and_deduplication() -> None:
    """Test candidate confidence ordering and duplicate elimination."""
    pattern_svc = EmailPatternService()
    rank_svc = PatternRankService()

    name = normalize_name_input("Sam", "Altman")
    raw_candidates = pattern_svc.generate_candidate_permutations(name, "openai.com")
    ranked = rank_svc.rank_and_deduplicate_candidates(raw_candidates, name)

    assert len(ranked) > 0

    # Ensure list is strictly ordered descending by confidence score
    scores = [r.confidence_score for r in ranked]
    assert scores == sorted(scores, reverse=True)

    # Highest ranked candidate should be first.last@domain (sam.altman@openai.com)
    top_candidate = ranked[0]
    assert top_candidate.candidate_email == "sam.altman@openai.com"
    assert top_candidate.confidence_score >= 0.95

    # Verify no duplicate candidate emails exist in output
    emails = [r.candidate_email for r in ranked]
    assert len(emails) == len(set(emails))
