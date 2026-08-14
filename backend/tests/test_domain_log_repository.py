"""Unit tests for DomainResolutionLogRepository with mocked Supabase client."""

import pytest
from unittest.mock import MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from app.core.exceptions import DatabaseException, ValidationException
from app.database.repositories.domain_resolution_log_repository import DomainResolutionLogRepository
from app.schemas.domain_resolution_log import DomainLogCreate


@pytest.fixture(autouse=True)
def clear_memory_logs():
    """Clear memory logs store before each test."""
    DomainResolutionLogRepository._shared_memory_logs.clear()
    yield
    DomainResolutionLogRepository._shared_memory_logs.clear()


@pytest.fixture
def mock_supabase_client() -> MagicMock:
    """Fixture providing a mocked Supabase client."""
    return MagicMock()


@pytest.fixture
def sample_log_record() -> dict:
    """Fixture providing a sample audit log database row record."""
    return {
        "id": str(uuid4()),
        "company_name": "Google",
        "normalized_name": "google",
        "resolved_domain": "google.com",
        "provider": "brandfetch",
        "cached": False,
        "response_time_ms": 142,
        "status": "success",
        "error_message": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def test_insert_log_success(mock_supabase_client: MagicMock, sample_log_record: dict) -> None:
    """Test inserting a resolution audit log entry."""
    repo = DomainResolutionLogRepository(client=mock_supabase_client)
    mock_supabase_client.table.return_value.insert.return_value.execute.return_value.data = [sample_log_record]

    log_data = DomainLogCreate(
        company_name="Google",
        resolved_domain="google.com",
        provider="brandfetch",
        cached=False,
        response_time_ms=142,
        status="success",
    )

    result = repo.insert_log(log_data)

    assert result is not None
    assert result.company_name == "Google"
    assert result.normalized_name == "google"
    assert result.status == "success"
    mock_supabase_client.table.assert_called_with("domain_resolution_logs")


def test_get_logs_pagination_and_filtering(mock_supabase_client: MagicMock, sample_log_record: dict) -> None:
    """Test querying audit log records with status filter and pagination."""
    repo = DomainResolutionLogRepository(client=mock_supabase_client)
    query_chain = mock_supabase_client.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value
    query_chain.execute.return_value.data = [sample_log_record]

    logs = repo.get_logs(limit=10, offset=0, status_filter="success")

    assert len(logs) == 1
    assert logs[0].company_name == "Google"
    assert logs[0].status == "success"


def test_get_logs_invalid_pagination_params(mock_supabase_client: MagicMock) -> None:
    """Test validation errors for out-of-range pagination limits."""
    repo = DomainResolutionLogRepository(client=mock_supabase_client)

    with pytest.raises(ValidationException, match="Limit must be"):
        repo.get_logs(limit=0)

    with pytest.raises(ValidationException, match="Offset cannot be negative"):
        repo.get_logs(limit=10, offset=-1)


def test_get_by_id_found(mock_supabase_client: MagicMock, sample_log_record: dict) -> None:
    """Test querying a specific audit log record by ID."""
    repo = DomainResolutionLogRepository(client=mock_supabase_client)
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [sample_log_record]

    target_id = uuid4()
    result = repo.get_by_id(target_id)

    assert result is not None
    assert result.resolved_domain == "google.com"


def test_get_by_id_not_found(mock_supabase_client: MagicMock) -> None:
    """Test returning None when query by ID finds no match."""
    repo = DomainResolutionLogRepository(client=mock_supabase_client)
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    target_id = uuid4()
    result = repo.get_by_id(target_id)

    assert result is None
