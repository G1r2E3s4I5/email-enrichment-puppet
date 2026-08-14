"""Unit tests for ConfidenceRecalculationService."""

import pytest
from datetime import datetime, timezone, timedelta
from app.services.confidence_recalculation_service import ConfidenceRecalculationService


@pytest.fixture
def confidence_service() -> ConfidenceRecalculationService:
    return ConfidenceRecalculationService()


def test_confidence_known_enterprise_brand(confidence_service: ConfidenceRecalculationService):
    score = confidence_service.calculate_confidence("IBM", "ibm.com", provider="Brandfetch")
    # Brandfetch (30) + Similarity (30) + Enterprise match (25) + Valid (15) = 100
    assert score == 100.0


def test_confidence_provider_weights(confidence_service: ConfidenceRecalculationService):
    score_bf = confidence_service.calculate_confidence("OpenAI", "openai.com", provider="Brandfetch")
    score_serp = confidence_service.calculate_confidence("OpenAI", "openai.com", provider="SerpAPI")

    assert score_bf > score_serp


def test_confidence_cache_age_decay(confidence_service: ConfidenceRecalculationService):
    now = datetime.now(timezone.utc)
    fresh_date = now - timedelta(days=5)
    old_date = now - timedelta(days=60)

    fresh_score = confidence_service.calculate_confidence(
        "OpenAI", "openai.com", provider="Cache", created_at=fresh_date
    )
    old_score = confidence_service.calculate_confidence(
        "OpenAI", "openai.com", provider="Cache", created_at=old_date
    )

    assert fresh_score > old_score
