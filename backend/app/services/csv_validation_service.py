"""CSV Validation Service enforcing format, encoding, header, and size limits."""

import csv
import io
from typing import Any, Dict, List, Set
from app.config.logging import logger
from app.core.exceptions import ValidationException
from app.schemas.job import CSVValidationResult


class CSVValidationService:
    """Service handling validation and parsing of CSV file uploads."""

    MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
    MAX_DATA_ROWS = 10000

    REQUIRED_COMPANY_VARIANTS: Set[str] = {
        "company",
        "company_name",
        "company name",
        "organization",
        "org",
        "firm",
        "business",
    }

    def validate_csv(self, content: bytes, filename: str) -> CSVValidationResult:
        """Validate raw CSV file payload against size, encoding, header, and row limit constraints."""
        file_size = len(content)
        warnings: List[str] = []

        # Rule 1: Check File Extension
        if not filename.lower().endswith(".csv"):
            raise ValidationException(f"Invalid file extension. Expected .csv file, got '{filename}'")

        # Rule 2: Check File Size (Max 20MB)
        if file_size > self.MAX_FILE_SIZE_BYTES:
            size_mb = round(file_size / (1024 * 1024), 2)
            raise ValidationException(f"File size exceeds maximum allowed limit of 20MB (Uploaded: {size_mb}MB)")

        # Rule 3: Check UTF-8 Encoding
        try:
            text_content = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            logger.error(f"Failed to decode CSV file '{filename}' with UTF-8 encoding: {str(exc)}")
            raise ValidationException(f"File encoding is not valid UTF-8: {str(exc)}")

        # Rule 4: Empty File Check
        if not text_content.strip():
            raise ValidationException("Uploaded CSV file is completely empty")

        # Rule 5: Parse CSV Content & Validate Headers
        stream = io.StringIO(text_content)
        try:
            reader = csv.reader(stream)
            raw_headers = next(reader, None)
        except Exception as exc:
            raise ValidationException(f"Malformed CSV file format: {str(exc)}")

        if not raw_headers or not any(h.strip() for h in raw_headers):
            raise ValidationException("CSV file contains no valid header row")

        # Trim header whitespace
        headers = [h.strip() for h in raw_headers]

        # Rule 6: Duplicate Header Check
        seen_headers: Set[str] = set()
        duplicate_headers: List[str] = []
        for h in headers:
            h_lower = h.lower()
            if h_lower in seen_headers:
                duplicate_headers.append(h)
            seen_headers.add(h_lower)

        if duplicate_headers:
            raise ValidationException(f"CSV header contains duplicate column names: {', '.join(duplicate_headers)}")

        # Rule 7: Required Company Column Check
        has_company_col = any(h.lower() in self.REQUIRED_COMPANY_VARIANTS for h in headers)
        if not has_company_col:
            raise ValidationException(
                "Required 'Company' column missing from CSV header. "
                "Supported header variations: 'Company', 'company_name', 'Organization'"
            )

        # Rule 8: Parse Data Rows & Check Row Limits
        data_rows: List[Dict[str, Any]] = []
        total_rows = 0

        for row_idx, row in enumerate(reader, start=1):
            if not any(cell.strip() for cell in row):
                continue  # Skip blank lines

            total_rows += 1
            if total_rows > self.MAX_DATA_ROWS:
                raise ValidationException(
                    f"File exceeds maximum allowed limit of {self.MAX_DATA_ROWS} data rows. "
                    f"Found at least {total_rows} rows."
                )

            # Store preview rows (up to 10)
            if len(data_rows) < 10:
                row_dict: Dict[str, Any] = {}
                for col_idx, col_name in enumerate(headers):
                    cell_val = row[col_idx].strip() if col_idx < len(row) else ""
                    row_dict[col_name] = cell_val
                data_rows.append(row_dict)

        if total_rows == 0:
            raise ValidationException("CSV file contains headers but no data rows")

        # Validation Warnings check
        has_name = any(h.lower() in ("name", "full name", "full_name", "employee name", "person name", "first name", "firstname", "first_name") for h in headers)
        if not has_name:
            warnings.append("Optional employee 'Name' or 'First Name' column not detected in CSV header")

        logger.info(f"Successfully validated CSV '{filename}' ({total_rows} rows, {len(headers)} columns)")

        return CSVValidationResult(
            is_valid=True,
            original_filename=filename,
            file_size=file_size,
            headers=headers,
            total_rows=total_rows,
            preview=data_rows,
            warnings=warnings,
            errors=[],
        )
