"""ExportService for generating CSV, Excel (.xlsx), and JSON export files with streaming and path traversal security controls."""

import csv
import io
import json
import os
import re
from typing import Dict, List, Any, Optional, Tuple, AsyncGenerator
from uuid import UUID

import openpyxl

from app.config.logging import logger
from app.config.settings import settings
from app.core.exceptions import EntityNotFoundException, ValidationException
from app.database.repositories.job_result_repository import JobResultRepository
from app.database.repositories.generated_email_candidate_repository import GeneratedEmailCandidateRepository
from app.database.repositories.job_repository import JobRepository


def sanitize_export_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks and header injection."""
    if not filename:
        return "export_job.csv"

    clean_base = os.path.basename(filename)
    clean_base = clean_base.replace("..", "").replace("/", "").replace("\\", "")
    clean_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", clean_base)

    if not clean_name:
        return "export_job"

    return clean_name


class ExportService:
    """Production export engine converting job results into streaming CSV, XLSX, and JSON downloads."""

    def __init__(
        self,
        job_repo: Optional[JobRepository] = None,
        job_result_repo: Optional[JobResultRepository] = None,
        candidate_repo: Optional[GeneratedEmailCandidateRepository] = None,
    ) -> None:
        """Initialize service with injected repositories."""
        self._job_repo = job_repo or JobRepository()
        self._job_result_repo = job_result_repo or JobResultRepository()
        self._candidate_repo = candidate_repo or GeneratedEmailCandidateRepository()

    def get_export_records(
        self,
        job_id: UUID,
        export_filter: str = "full",
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Fetch job metadata and build structured export records filtered by mode."""
        job = self._job_repo.get_by_id(job_id)
        if not job:
            raise EntityNotFoundException("ProcessingJob", str(job_id))

        results = self._job_result_repo.get_by_job_id(job_id)
        candidates = self._candidate_repo.get_by_job_id(job_id)

        # Apply row-level filters
        clean_filter = (export_filter or "full").strip().lower()
        if clean_filter == "successful_only":
            results = [r for r in results if r.success]
        elif clean_filter == "failed_only":
            results = [r for r in results if not r.success]

        # Group candidates by row_number
        candidates_by_row: Dict[int, List[Any]] = {}
        for c in candidates:
            candidates_by_row.setdefault(c.row_number, []).append(c)

        export_records: List[Dict[str, Any]] = []

        for r in results:
            row_cands = candidates_by_row.get(r.row_number, [])
            row_cands.sort(key=lambda x: x.rank if x.rank is not None else 999)

            if clean_filter == "top_ranked_only":
                row_cands = row_cands[:1]

            top_cand = row_cands[0] if row_cands else None

            # Deduplicate candidate emails preserving order
            unique_cand_emails = list(dict.fromkeys([c.candidate_email for c in row_cands if c.candidate_email]))

            # Filter and deduplicate successfully verified candidate emails preserving order
            smtp_verified_emails = [
                c.candidate_email for c in row_cands
                if c.candidate_email and c.verification_status in ("VALID", "CATCH_ALL")
            ]
            unique_verified_emails = list(dict.fromkeys(smtp_verified_emails))

            # Determine MX/SMTP detailed status
            mx_checked_str = "Yes" if top_cand and getattr(top_cand, "mx_checked", True) else "No"
            mx_exists_bool = getattr(top_cand, "mx_exists", True if top_cand and top_cand.verification_status != "INVALID_DOMAIN" else False) if top_cand else False
            mx_exists_str = "Yes" if mx_exists_bool else "No"

            smtp_checked_str = "Yes" if top_cand and getattr(top_cand, "smtp_checked", False) else "No"

            if top_cand and top_cand.smtp_checked:
                smtp_resp_str = getattr(top_cand, "smtp_message", None) or getattr(top_cand, "smtp_status", None) or "250 OK"
            elif top_cand and not mx_exists_bool:
                smtp_resp_str = "Skipped (No MX)"
            else:
                smtp_resp_str = "Skipped"

            # Determine human-readable verification reason
            if not top_cand:
                reason_str = "N/A"
            elif top_cand.verification_status == "INVALID_DOMAIN" or not mx_exists_bool:
                reason_str = "No MX Records Found"
            elif getattr(top_cand, "is_disposable", False):
                reason_str = "Disposable Email Service"
            elif top_cand.verification_status == "VALID":
                reason_str = "250 OK - Valid Mailbox"
            elif top_cand.verification_status == "CATCH_ALL":
                reason_str = "Catch-All Server Detected"
            elif getattr(top_cand, "verification_error", None):
                reason_str = str(top_cand.verification_error)
            else:
                reason_str = top_cand.verification_status or "N/A"

            # Build top 3 verified emails with probability for ranked display
            top_3_verified_parts: List[str] = []
            verified_cands_sorted = [
                c for c in row_cands
                if c.candidate_email and c.verification_status in ("VALID", "CATCH_ALL")
            ]
            # Already sorted by rank from row_cands.sort above; take top 3 unique
            seen_top3: set = set()
            for vc in verified_cands_sorted:
                if vc.candidate_email not in seen_top3 and len(seen_top3) < 3:
                    seen_top3.add(vc.candidate_email)
                    conf_pct = round(vc.verification_confidence, 1) if vc.verification_confidence else 0.0
                    top_3_verified_parts.append(f"{len(seen_top3)}. {vc.candidate_email} ({conf_pct}%)")

            top_verified_ranked_str = " | ".join(top_3_verified_parts) if top_3_verified_parts else "N/A"

            export_records.append(
                {
                    "Job ID": str(job_id),
                    "Row Number": r.row_number,
                    "Company Name": r.company,
                    "Resolved Domain": r.resolved_domain or "N/A",
                    "Domain Provider": r.provider or "N/A",
                    "Domain Cached": "Yes" if r.cached else "No",
                    "Top Email Candidate": top_cand.candidate_email if top_cand else "N/A",
                    "Top Verified Emails (Ranked)": top_verified_ranked_str,
                    "Verification Status": top_cand.verification_status if top_cand else "N/A",
                    "Verification Reason": reason_str,
                    "Verification Confidence": top_cand.verification_confidence if top_cand else 0.0,
                    "Verification Provider": top_cand.verification_provider if top_cand else "N/A",
                    "MX Lookup Performed": mx_checked_str,
                    "MX Records Found": mx_exists_str,
                    "SMTP Attempted": smtp_checked_str,
                    "SMTP Response": smtp_resp_str,
                    "MX Checked": mx_checked_str,
                    "SMTP Checked": smtp_checked_str,
                    "Is Disposable": "Yes" if top_cand and getattr(top_cand, "is_disposable", False) else "No",
                    "Is Role Account": "Yes" if top_cand and getattr(top_cand, "is_role_account", False) else "No",
                    "Is Catch All": "Yes" if top_cand and getattr(top_cand, "is_catch_all", False) else "No",
                    "Final Score": top_cand.final_score if top_cand else 0.0,
                    "Rank": top_cand.rank if top_cand else "N/A",
                    "Total Candidates": len(unique_cand_emails),
                    "All Candidate Emails": ", ".join(unique_cand_emails),
                    "All SMTP Verified Emails": ", ".join(unique_verified_emails),
                    "Processed At": r.processed_at.isoformat() if r.processed_at else "",
                }
            )

        sanitized_filename = sanitize_export_filename(job.original_filename)
        return sanitized_filename, export_records

    def generate_export(
        self,
        job_id: UUID,
        export_format: str = "csv",
        export_filter: str = "full",
    ) -> Tuple[str, str, bytes]:
        """Generate exported payload in requested format (csv, xlsx, json)."""
        fmt = (export_format or "csv").strip().lower()
        if fmt not in ("csv", "xlsx", "excel", "json"):
            raise ValidationException(f"Unsupported export format '{export_format}'. Choose from 'csv', 'xlsx', or 'json'.")

        base_filename, records = self.get_export_records(job_id, export_filter=export_filter)
        name_root = base_filename.rsplit(".", 1)[0] if "." in base_filename else base_filename

        if fmt == "json":
            out_filename = f"{name_root}_export.json"
            media_type = "application/json"
            content_bytes = json.dumps(records, indent=2).encode("utf-8")
        elif fmt in ("xlsx", "excel"):
            out_filename = f"{name_root}_export.xlsx"
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Enrichment Results"

            if records:
                headers = list(records[0].keys())
                ws.append(headers)
                for rec in records:
                    ws.append(list(rec.values()))

            output = io.BytesIO()
            wb.save(output)
            content_bytes = output.getvalue()
        else:
            out_filename = f"{name_root}_export.csv"
            media_type = "text/csv"

            output_str = io.StringIO()
            if records:
                writer = csv.DictWriter(output_str, fieldnames=list(records[0].keys()))
                writer.writeheader()
                writer.writerows(records)
            content_bytes = output_str.getvalue().encode("utf-8")

        logger.info(f"Export completed: Job ID='{job_id}', Format='{fmt}', Filter='{export_filter}', Rows={len(records)}")
        return out_filename, media_type, content_bytes

    async def stream_export_csv(
        self,
        job_id: UUID,
        export_filter: str = "full",
        batch_size: int = 1000,
    ) -> AsyncGenerator[bytes, None]:
        """Stream CSV export response in chunks for large job datasets."""
        _, records = self.get_export_records(job_id, export_filter=export_filter)
        if not records:
            yield b""
            return

        fieldnames = list(records[0].keys())
        out_buf = io.StringIO()
        writer = csv.DictWriter(out_buf, fieldnames=fieldnames)
        writer.writeheader()
        yield out_buf.getvalue().encode("utf-8")

        for i in range(0, len(records), batch_size):
            out_buf = io.StringIO()
            writer = csv.DictWriter(out_buf, fieldnames=fieldnames)
            batch = records[i : i + batch_size]
            writer.writerows(batch)
            yield out_buf.getvalue().encode("utf-8")

    async def stream_export_json(
        self,
        job_id: UUID,
        export_filter: str = "full",
        batch_size: int = 1000,
    ) -> AsyncGenerator[bytes, None]:
        """Stream JSON export response array elements in chunks."""
        _, records = self.get_export_records(job_id, export_filter=export_filter)
        yield b"[\n"
        total = len(records)

        for i, rec in enumerate(records):
            item_json = json.dumps(rec, indent=2)
            if i < total - 1:
                item_json += ",\n"
            yield item_json.encode("utf-8")

        yield b"\n]"
