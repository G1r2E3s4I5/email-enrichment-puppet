"""Unit tests validating newly created CSV fixture files."""

import os
from app.services.csv_validation_service import CSVValidationService

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROOT_FIXTURES = os.path.join(BASE_DIR, "..", "tests", "fixtures", "csv")
BACKEND_FIXTURES = os.path.join(BASE_DIR, "fixtures", "csv")


def _read_fixture(filename: str) -> bytes:
    """Read fixture content bytes searching both fixture directories."""
    path1 = os.path.join(ROOT_FIXTURES, filename)
    path2 = os.path.join(BACKEND_FIXTURES, filename)

    if os.path.exists(path1):
        target = path1
    elif os.path.exists(path2):
        target = path2
    else:
        raise FileNotFoundError(f"Fixture file '{filename}' not found at '{path1}' or '{path2}'")

    with open(target, "rb") as f:
        return f.read()


def test_same_company_multiple_people_fixture() -> None:
    """Validate same_company_multiple_people.csv has 30 rows of OpenAI."""
    content = _read_fixture("same_company_multiple_people.csv")
    validator = CSVValidationService()
    result = validator.validate_csv(content, "same_company_multiple_people.csv")

    assert result.total_rows == 30
    assert result.headers == ["Company", "First Name", "Last Name"]
    for row in result.preview:
        assert row["Company"] == "OpenAI"


def test_multi_word_names_fixture() -> None:
    """Validate multi_word_names.csv has 25 rows."""
    content = _read_fixture("multi_word_names.csv")
    validator = CSVValidationService()
    result = validator.validate_csv(content, "multi_word_names.csv")

    assert result.total_rows == 25
    assert result.headers == ["Company", "First Name", "Last Name"]


def test_hyphenated_names_fixture() -> None:
    """Validate hyphenated_names.csv has 25 rows."""
    content = _read_fixture("hyphenated_names.csv")
    validator = CSVValidationService()
    result = validator.validate_csv(content, "hyphenated_names.csv")

    assert result.total_rows == 25
    assert result.headers == ["Company", "First Name", "Last Name"]


def test_apostrophe_names_fixture() -> None:
    """Validate apostrophe_names.csv has 25 rows."""
    content = _read_fixture("apostrophe_names.csv")
    validator = CSVValidationService()
    result = validator.validate_csv(content, "apostrophe_names.csv")

    assert result.total_rows == 25
    assert result.headers == ["Company", "First Name", "Last Name"]


def test_unicode_names_fixture() -> None:
    """Validate unicode_names.csv has 30 rows."""
    content = _read_fixture("unicode_names.csv")
    validator = CSVValidationService()
    result = validator.validate_csv(content, "unicode_names.csv")

    assert result.total_rows == 30
    assert result.headers == ["Company", "First Name", "Last Name"]


def test_hundred_rows_fixture() -> None:
    """Validate hundred_rows.csv has exactly 100 rows."""
    content = _read_fixture("hundred_rows.csv")
    validator = CSVValidationService()
    result = validator.validate_csv(content, "hundred_rows.csv")

    assert result.total_rows == 100
    assert result.headers == ["Company", "First Name", "Last Name"]
