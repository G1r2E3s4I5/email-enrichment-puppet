"""Unit tests for CompanyDomainRepository with mocked Supabase client."""

import pytest
from unittest.mock import MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from app.core.exceptions import (
    DatabaseException,
    DuplicateRecordException,
    EntityNotFoundException,
    ValidationException,
)
from app.database.repositories.company_domain_repository import CompanyDomainRepository
from app.schemas.company_domain import CompanyDomainCreate, CompanyDomainUpdate


@pytest.fixture
def mock_supabase_client() -> MagicMock:
    """Fixture providing a mocked Supabase client."""
    client = MagicMock()
    return client


@pytest.fixture
def sample_record() -> dict:
    """Fixture providing a sample database row record."""
    return {
        "id": str(uuid4()),
        "company_name": "Microsoft",
        "normalized_name": "microsoft",
        "domain": "microsoft.com",
        "provider": "brandfetch",
        "confidence": 0.95,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def test_repository_uninitialized_client_raises_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that accessing client when unconfigured raises DatabaseException."""
    monkeypatch.setattr("app.database.repositories.company_domain_repository.get_supabase_client", lambda: None)
    repo = CompanyDomainRepository(client=None)
    with pytest.raises(DatabaseException, match="not configured or uninitialized"):
        _ = repo.client




def test_get_by_normalized_name_success(mock_supabase_client: MagicMock, sample_record: dict) -> None:
    """Test retrieving domain cache entry by normalized name."""
    repo = CompanyDomainRepository(client=mock_supabase_client)
    mock_table = mock_supabase_client.table.return_value
    mock_select = mock_table.select.return_value
    mock_eq = mock_select.eq.return_value
    mock_eq.execute.return_value.data = [sample_record]

    result = repo.get_by_normalized_name(" Microsoft ")

    assert result is not None
    assert result.company_name == "Microsoft"
    assert result.normalized_name == "microsoft"
    assert result.domain == "microsoft.com"
    mock_supabase_client.table.assert_called_with("company_domains")
    mock_select.eq.assert_called_with("normalized_name", "microsoft")


def test_get_by_normalized_name_not_found(mock_supabase_client: MagicMock) -> None:
    """Test returning None when no matching normalized record exists."""
    repo = CompanyDomainRepository(client=mock_supabase_client)
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    result = repo.get_by_normalized_name("unknown_company")
    assert result is None


def test_insert_cache_success(mock_supabase_client: MagicMock, sample_record: dict) -> None:
    """Test successfully inserting a new company domain cache entry."""
    repo = CompanyDomainRepository(client=mock_supabase_client)
    # Mock lookup check returning None (not duplicated)
    repo.get_by_normalized_name = MagicMock(return_value=None)  # type: ignore[method-assign]

    mock_supabase_client.table.return_value.insert.return_value.execute.return_value.data = [sample_record]

    create_data = CompanyDomainCreate(
        company_name="Microsoft",
        domain="microsoft.com",
        provider="brandfetch",
        confidence=0.95,
    )

    result = repo.insert_cache(create_data)

    assert result is not None
    assert result.domain == "microsoft.com"
    assert result.normalized_name == "microsoft"


def test_insert_cache_duplicate_raises_exception(mock_supabase_client: MagicMock, sample_record: dict) -> None:
    """Test duplicate cache insertion raises DuplicateRecordException."""
    repo = CompanyDomainRepository(client=mock_supabase_client)
    # Mock lookup returning existing record
    existing_resp = MagicMock()
    existing_resp.normalized_name = "microsoft"
    repo.get_by_normalized_name = MagicMock(return_value=existing_resp)  # type: ignore[method-assign]

    create_data = CompanyDomainCreate(
        company_name="Microsoft",
        domain="microsoft.com",
        provider="brandfetch",
    )

    with pytest.raises(DuplicateRecordException, match="already exists"):
        repo.insert_cache(create_data)


def test_update_cache_success(mock_supabase_client: MagicMock, sample_record: dict) -> None:
    """Test successfully updating an existing domain cache record."""
    repo = CompanyDomainRepository(client=mock_supabase_client)
    sample_record["confidence"] = 0.99
    mock_supabase_client.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [sample_record]

    target_id = uuid4()
    update_data = CompanyDomainUpdate(confidence=0.99)
    result = repo.update_cache(target_id, update_data)

    assert result is not None
    assert result.confidence == 0.99


def test_update_cache_not_found_raises_exception(mock_supabase_client: MagicMock) -> None:
    """Test updating a non-existent domain cache record raises EntityNotFoundException."""
    repo = CompanyDomainRepository(client=mock_supabase_client)
    mock_supabase_client.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []

    target_id = uuid4()
    update_data = CompanyDomainUpdate(domain="newdomain.com")

    with pytest.raises(EntityNotFoundException, match="not found"):
        repo.update_cache(target_id, update_data)


def test_delete_cache_success(mock_supabase_client: MagicMock, sample_record: dict) -> None:
    """Test successfully deleting a domain cache record."""
    repo = CompanyDomainRepository(client=mock_supabase_client)
    mock_supabase_client.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = [sample_record]

    target_id = uuid4()
    result = repo.delete_cache(target_id)
    assert result is True


def test_delete_cache_not_found_raises_exception(mock_supabase_client: MagicMock) -> None:
    """Test deleting a non-existent domain cache record raises EntityNotFoundException."""
    repo = CompanyDomainRepository(client=mock_supabase_client)
    mock_supabase_client.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = []

    target_id = uuid4()
    with pytest.raises(EntityNotFoundException, match="not found"):
        repo.delete_cache(target_id)
