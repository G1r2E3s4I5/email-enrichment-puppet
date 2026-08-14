"""Integration tests for CSV Upload & Job management API endpoints."""

import os
import pytest
from uuid import uuid4
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.api.dependencies.services import get_job_service
from app.core.exceptions import EntityNotFoundException

client = TestClient(app)

FIXTURES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "tests", "fixtures", "csv")
)


def _load_fixture(filename: str) -> bytes:
    """Helper to read fixture file content from tests/fixtures/csv/."""
    fixture_path = os.path.join(FIXTURES_DIR, filename)
    with open(fixture_path, "rb") as f:
        return f.read()


def test_upload_valid_csv_fixture_success() -> None:
    """Test POST /api/v1/jobs/upload with valid_companies.csv fixture."""
    file_bytes = _load_fixture("valid_companies.csv")
    files = {"file": ("valid_companies.csv", file_bytes, "text/csv")}

    response = client.post("/api/v1/jobs/upload", files=files)

    assert response.status_code == 201
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "VALIDATED"
    assert data["rows"] == 25
    assert "Company" in data["headers"]
    assert len(data["preview"]) == 10


def test_upload_missing_company_column_fixture_error() -> None:
    """Test POST /api/v1/jobs/upload with missing_company_column.csv fixture returning 400."""
    file_bytes = _load_fixture("missing_company_column.csv")
    files = {"file": ("missing_company_column.csv", file_bytes, "text/csv")}

    response = client.post("/api/v1/jobs/upload", files=files)

    assert response.status_code == 400
    data = response.json()
    assert "Required 'Company' column missing" in data["detail"]


def test_upload_empty_csv_fixture_error() -> None:
    """Test POST /api/v1/jobs/upload with empty.csv fixture returning 400."""
    file_bytes = _load_fixture("empty.csv")
    files = {"file": ("empty.csv", file_bytes, "text/csv")}

    response = client.post("/api/v1/jobs/upload", files=files)

    assert response.status_code == 400
    data = response.json()
    assert "no data rows" in data["detail"] or "empty" in data["detail"]


def test_upload_duplicate_headers_fixture_error() -> None:
    """Test POST /api/v1/jobs/upload with duplicate_headers.csv fixture returning 400."""
    file_bytes = _load_fixture("duplicate_headers.csv")
    files = {"file": ("duplicate_headers.csv", file_bytes, "text/csv")}

    response = client.post("/api/v1/jobs/upload", files=files)

    assert response.status_code == 400
    data = response.json()
    assert "duplicate column names" in data["detail"]


def test_upload_unsupported_media_type_extension() -> None:
    """Test POST /api/v1/jobs/upload with non-csv extension returning 415."""
    files = {"file": ("dataset.txt", b"Company\nStripe\n", "text/plain")}

    response = client.post("/api/v1/jobs/upload", files=files)

    assert response.status_code == 415
    data = response.json()
    assert "Unsupported file type" in data["detail"]


def test_get_job_status_not_found() -> None:
    """Test GET /api/v1/jobs/{job_id} returning 404 for unknown job ID."""
    fake_id = uuid4()

    mock_service = MagicMock()
    mock_service.get_job_detail.side_effect = EntityNotFoundException(
        message=f"Job record with ID '{fake_id}' not found"
    )

    app.dependency_overrides[get_job_service] = lambda: mock_service
    try:
        response = client.get(f"/api/v1/jobs/{fake_id}")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    finally:
        app.dependency_overrides.clear()
