"""Pytest configuration and shared fixtures."""

import pytest
from typing import Generator
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    """Provide a TestClient instance for API integration tests."""
    with TestClient(app) as test_client:
        yield test_client
