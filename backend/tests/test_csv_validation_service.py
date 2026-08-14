"""Unit tests for CSVValidationService enforcing CSV formatting rules."""

import pytest
from app.core.exceptions import ValidationException
from app.services.csv_validation_service import CSVValidationService


@pytest.fixture
def validation_service() -> CSVValidationService:
    """Fixture providing CSVValidationService instance."""
    return CSVValidationService()


def test_validate_csv_valid_file(validation_service: CSVValidationService) -> None:
    """Test validating a valid CSV payload."""
    content = b"Company,First Name,Last Name\nStripe,John,Doe\nOpenAI,Sam,Altman\n"
    res = validation_service.validate_csv(content, "test.csv")

    assert res.is_valid is True
    assert res.total_rows == 2
    assert res.headers == ["Company", "First Name", "Last Name"]
    assert len(res.preview) == 2
    assert res.preview[0]["Company"] == "Stripe"


def test_validate_csv_missing_company_column(validation_service: CSVValidationService) -> None:
    """Test validation failure when Company header column is missing."""
    content = b"First Name,Last Name\nJohn,Doe\n"
    with pytest.raises(ValidationException, match="Required 'Company' column missing"):
        validation_service.validate_csv(content, "test.csv")


def test_validate_csv_empty_file(validation_service: CSVValidationService) -> None:
    """Test validation failure when file payload is completely empty."""
    with pytest.raises(ValidationException, match="completely empty"):
        validation_service.validate_csv(b"", "test.csv")


def test_validate_csv_duplicate_headers(validation_service: CSVValidationService) -> None:
    """Test validation failure when header contains duplicate column names."""
    content = b"Company,Company\nStripe,Stripe\n"
    with pytest.raises(ValidationException, match="duplicate column names"):
        validation_service.validate_csv(content, "test.csv")


def test_validate_csv_invalid_extension(validation_service: CSVValidationService) -> None:
    """Test validation failure when file extension is not .csv."""
    with pytest.raises(ValidationException, match="Invalid file extension"):
        validation_service.validate_csv(b"Company\nStripe\n", "test.txt")


def test_validate_csv_non_utf8_encoding(validation_service: CSVValidationService) -> None:
    """Test validation failure when file bytes are not valid UTF-8."""
    bad_bytes = b"\x80\x81\x82 Company\nStripe\n"
    with pytest.raises(ValidationException, match="not valid UTF-8"):
        validation_service.validate_csv(bad_bytes, "test.csv")


def test_validate_csv_exceeds_max_file_size(validation_service: CSVValidationService) -> None:
    """Test validation failure when file size exceeds 20MB limit."""
    large_payload = b"Company\n" + (b"A" * (20 * 1024 * 1024 + 100))
    with pytest.raises(ValidationException, match="exceeds maximum allowed limit of 20MB"):
        validation_service.validate_csv(large_payload, "test.csv")


def test_validate_csv_exceeds_max_data_rows(validation_service: CSVValidationService) -> None:
    """Test validation failure when row count exceeds 10,000 data rows."""
    lines = ["Company"] + [f"Company_{i}" for i in range(10001)]
    content = "\n".join(lines).encode("utf-8")
    with pytest.raises(ValidationException, match="exceeds maximum allowed limit of 10000 data rows"):
        validation_service.validate_csv(content, "test.csv")
