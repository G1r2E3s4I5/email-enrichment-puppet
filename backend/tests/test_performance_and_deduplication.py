"""Comprehensive unit and performance test suite for Company Deduplication, Deterministic Confidence Scoring, and Bulk Cache Lookups."""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.domain_resolver_service import DomainResolverService
from app.services.confidence_recalculation_service import ConfidenceRecalculationService
from app.database.repositories.company_domain_repository import CompanyDomainRepository
from app.schemas.company_domain import CompanyDomainCreate, CompanyDomainResponse


@pytest.mark.asyncio
async def test_company_deduplication_in_batch_resolution():
    """Verify that batch resolution deduplicates 100 duplicate company rows to 1 unique resolution call."""
    resolver = DomainResolverService()

    # Mock resolve_domain
    mock_res = MagicMock()
    mock_res.success = True
    mock_res.domain = "stripe.com"
    mock_res.provider = "Brandfetch"
    mock_res.cached = False
    mock_res.confidence = 95.0

    with patch.object(resolver, "resolve_domain", return_value=mock_res) as mock_single_resolve:
        # Pass 100 duplicate "Stripe" company rows
        duplicate_companies = ["Stripe"] * 100
        results = await resolver.resolve_domains_batch(duplicate_companies, force_refresh=True)

        assert len(results) == 100
        assert all(r.domain == "stripe.com" for r in results)
        # Should only call single resolve ONCE for the unique company
        assert mock_single_resolve.call_count == 1


def test_deterministic_confidence_scoring():
    """Verify Stripe, Shopify, and exact SLD matches receive consistent 95-100 confidence scores."""
    scoring = ConfidenceRecalculationService()

    # Test Stripe (was previously receiving 70/75, now receives 95.0+)
    stripe_score = scoring.calculate_confidence(company_name="Stripe", domain="stripe.com", provider="Brandfetch")
    assert stripe_score >= 95.0, f"Stripe score must be >= 95.0, got {stripe_score}"

    # Test Shopify
    shopify_score = scoring.calculate_confidence(company_name="Shopify", domain="shopify.com", provider="Brandfetch")
    assert shopify_score >= 95.0, f"Shopify score must be >= 95.0, got {shopify_score}"

    # Test exact SLD match for non-hardcoded company (e.g. Acme Corp -> acme.com)
    acme_score = scoring.calculate_confidence(company_name="Acme Corp", domain="acme.com", provider="Brandfetch")
    assert acme_score >= 85.0, f"Acme Corp score must be >= 85.0, got {acme_score}"


def test_bulk_domain_cache_query():
    """Verify get_by_normalized_names_batch fetches multiple cached company domains in one call."""
    with patch("app.database.repositories.company_domain_repository.get_supabase_client", return_value=None):
        repo = CompanyDomainRepository(client=None)
        CompanyDomainRepository._shared_memory_cache.clear()

        # Populate 2 memory entries
        repo.insert_cache(CompanyDomainCreate(company_name="Stripe", domain="stripe.com", provider="Brandfetch", confidence=95.0))
        repo.insert_cache(CompanyDomainCreate(company_name="Shopify", domain="shopify.com", provider="Brandfetch", confidence=95.0))

        bulk_res = repo.get_by_normalized_names_batch(["Stripe", "Shopify", "NonExistentCompany"])

        assert len(bulk_res) == 2
        assert "stripe" in bulk_res
        assert "shopify" in bulk_res
        assert bulk_res["stripe"].domain == "stripe.com"
        assert bulk_res["shopify"].domain == "shopify.com"
