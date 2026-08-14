"""Unit tests for DomainAnalyticsRepository."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from app.database.repositories.domain_analytics_repository import DomainAnalyticsRepository


@pytest.fixture
def mock_client():
    client = MagicMock()
    return client


def test_window_start_time_conversion(mock_client):
    repo = DomainAnalyticsRepository(client=mock_client)
    now = datetime.now(timezone.utc)

    # test last_hour
    dt_hour = repo._get_window_start_time("last_hour")
    assert dt_hour is not None
    assert (now - dt_hour).total_seconds() >= 3500

    # test last_24h
    dt_24h = repo._get_window_start_time("last_24h")
    assert dt_24h is not None

    # test all_time
    assert repo._get_window_start_time("all_time") is None


def test_get_logs_in_window(mock_client):
    mock_query = MagicMock()
    mock_client.table.return_value.select.return_value = mock_query
    mock_query.gte.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.execute.return_value = MagicMock(data=[{"company_name": "OpenAI", "status": "success"}])

    repo = DomainAnalyticsRepository(client=mock_client)
    logs = repo.get_logs_in_window("last_24h")

    assert len(logs) == 1
    assert logs[0]["company_name"] == "OpenAI"
