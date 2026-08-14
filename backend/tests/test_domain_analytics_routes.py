"""Integration tests for Domain Analytics REST API endpoints."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api.dependencies.services import get_domain_analytics_service
from app.schemas.domain_analytics import (
    DomainAnalyticsOverviewResponse,
    DomainCacheAnalyticsResponse,
    DomainProviderAnalyticsResponse,
    DomainQualityAnalyticsResponse,
    ProviderStatisticItem,
    QualityDistribution,
)
from unittest.mock import MagicMock


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def mock_analytics_service():
    service = MagicMock()
    service.get_overview_analytics.return_value = DomainAnalyticsOverviewResponse(
        time_window="last_24h",
        total_resolutions=10,
        successful_resolutions=8,
        failed_resolutions=2,
        success_rate=80.0,
        failure_rate=20.0,
        cache_hit_rate=50.0,
        average_response_time_ms=125.5,
        average_confidence=88.5,
    )
    service.get_provider_analytics.return_value = DomainProviderAnalyticsResponse(
        time_window="last_24h",
        providers=[
            ProviderStatisticItem(
                provider="Brandfetch",
                total_requests=5,
                successful_requests=5,
                failed_requests=0,
                average_response_time_ms=210.0,
                fastest_response_ms=150.0,
                slowest_response_ms=300.0,
                average_confidence=90.0,
            )
        ],
    )
    service.get_cache_analytics.return_value = DomainCacheAnalyticsResponse(
        time_window="last_24h",
        cache_hits=5,
        cache_misses=5,
        hit_rate=50.0,
        miss_rate=50.0,
        cache_refresh_count=1,
        expired_records_count=0,
        total_cached_companies=12,
    )
    service.get_quality_analytics.return_value = DomainQualityAnalyticsResponse(
        time_window="last_24h",
        average_confidence=88.5,
        median_confidence=90.0,
        confidence_distribution=QualityDistribution(
            score_90_to_100=5,
            score_80_to_89=3,
            score_70_to_79=1,
            below_70=1,
        ),
        duplicate_domains_count=0,
        suspicious_domains_rejected=1,
        invalid_domains_rejected=1,
    )
    return service


def test_overview_analytics_endpoint(test_client: TestClient, mock_analytics_service):
    app.dependency_overrides[get_domain_analytics_service] = lambda: mock_analytics_service
    try:
        response = test_client.get("/api/v1/domain/analytics/overview?time_window=last_24h")
        assert response.status_code == 200
        data = response.json()
        assert data["total_resolutions"] == 10
        assert data["success_rate"] == 80.0
    finally:
        app.dependency_overrides.clear()


def test_provider_analytics_endpoint(test_client: TestClient, mock_analytics_service):
    app.dependency_overrides[get_domain_analytics_service] = lambda: mock_analytics_service
    try:
        response = test_client.get("/api/v1/domain/analytics/providers?time_window=last_24h")
        assert response.status_code == 200
        data = response.json()
        assert len(data["providers"]) == 1
        assert data["providers"][0]["provider"] == "Brandfetch"
    finally:
        app.dependency_overrides.clear()


def test_cache_analytics_endpoint(test_client: TestClient, mock_analytics_service):
    app.dependency_overrides[get_domain_analytics_service] = lambda: mock_analytics_service
    try:
        response = test_client.get("/api/v1/domain/analytics/cache?time_window=last_24h")
        assert response.status_code == 200
        data = response.json()
        assert data["cache_hits"] == 5
        assert data["hit_rate"] == 50.0
    finally:
        app.dependency_overrides.clear()


def test_quality_analytics_endpoint(test_client: TestClient, mock_analytics_service):
    app.dependency_overrides[get_domain_analytics_service] = lambda: mock_analytics_service
    try:
        response = test_client.get("/api/v1/domain/analytics/quality?time_window=last_24h")
        assert response.status_code == 200
        data = response.json()
        assert data["average_confidence"] == 88.5
        assert data["confidence_distribution"]["score_90_to_100"] == 5
    finally:
        app.dependency_overrides.clear()


def test_invalid_time_window_validation(test_client: TestClient, mock_analytics_service):
    app.dependency_overrides[get_domain_analytics_service] = lambda: mock_analytics_service
    try:
        response = test_client.get("/api/v1/domain/analytics/overview?time_window=invalid_window")
        assert response.status_code == 400
        assert "Invalid time_window" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
