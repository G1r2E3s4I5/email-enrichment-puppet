"""Unit tests for DomainAnalyticsService."""

import pytest
from unittest.mock import MagicMock

from app.services.domain_analytics_service import DomainAnalyticsService


@pytest.fixture
def mock_analytics_repo():
    repo = MagicMock()
    repo.get_logs_in_window.return_value = [
        {"company_name": "Stripe", "provider": "Brandfetch", "cached": False, "response_time_ms": 120.0, "status": "success"},
        {"company_name": "OpenAI", "provider": "Cache", "cached": True, "response_time_ms": 5.0, "status": "success"},
        {"company_name": "UnknownCo", "provider": "SerpAPI", "cached": False, "response_time_ms": 450.0, "status": "not_found", "error_message": "Invalid syntax"},
    ]
    repo.get_cached_domains_in_window.return_value = [
        {"company_name": "Stripe", "confidence": 95.0},
        {"company_name": "OpenAI", "confidence": 85.0},
    ]
    repo.get_total_cached_companies_count.return_value = 2
    repo.get_expired_cached_count.return_value = 0
    return repo


def test_overview_analytics_computation(mock_analytics_repo):
    service = DomainAnalyticsService(analytics_repo=mock_analytics_repo)
    overview = service.get_overview_analytics("last_24h")

    assert overview.total_resolutions == 3
    assert overview.successful_resolutions == 2
    assert overview.failed_resolutions == 1
    assert overview.success_rate == 66.67
    assert overview.failure_rate == 33.33
    assert overview.cache_hit_rate == 33.33
    assert overview.average_confidence == 90.0


def test_provider_analytics_computation(mock_analytics_repo):
    service = DomainAnalyticsService(analytics_repo=mock_analytics_repo)
    provider_res = service.get_provider_analytics("last_24h")

    assert len(provider_res.providers) == 3
    providers = {p.provider: p for p in provider_res.providers}

    assert "Brandfetch" in providers
    assert providers["Brandfetch"].total_requests == 1
    assert providers["Brandfetch"].successful_requests == 1

    assert "Cache" in providers
    assert providers["Cache"].total_requests == 1

    assert "SerpAPI" in providers
    assert providers["SerpAPI"].failed_requests == 1


def test_quality_analytics_computation(mock_analytics_repo):
    service = DomainAnalyticsService(analytics_repo=mock_analytics_repo)
    quality_res = service.get_quality_analytics("last_24h")

    assert quality_res.average_confidence == 90.0
    assert quality_res.median_confidence == 90.0
    assert quality_res.confidence_distribution.score_90_to_100 == 1
    assert quality_res.confidence_distribution.score_80_to_89 == 1
    assert quality_res.invalid_domains_rejected == 1


def test_empty_dataset_graceful_handling():
    empty_repo = MagicMock()
    empty_repo.get_logs_in_window.return_value = []
    empty_repo.get_cached_domains_in_window.return_value = []
    empty_repo.get_total_cached_companies_count.return_value = 0
    empty_repo.get_expired_cached_count.return_value = 0

    service = DomainAnalyticsService(analytics_repo=empty_repo)
    overview = service.get_overview_analytics("all_time")

    assert overview.total_resolutions == 0
    assert overview.success_rate == 0.0
    assert overview.failure_rate == 0.0
    assert overview.average_confidence == 0.0

    providers = service.get_provider_analytics("all_time")
    assert len(providers.providers) > 0
    assert providers.providers[0].total_requests == 0
