"""JobProgressService managing progress tracking, row metrics, and estimated time remaining."""

import time
from typing import Dict, Any, Optional
from uuid import UUID

from app.config.logging import logger
from app.database.repositories.job_repository import JobRepository


class JobProgressService:
    """Service class calculating progress percentage, remaining rows, and ETA metrics."""

    def __init__(self, job_repository: Optional[JobRepository] = None) -> None:
        """Initialize progress service with injected JobRepository."""
        self._job_repository = job_repository

    def calculate_metrics(
        self,
        current_row: int,
        total_rows: int,
        current_company: str,
        job_start_time: float,
    ) -> Dict[str, Any]:
        """Calculate progress metrics dictionary including progress_percentage and estimated_time_remaining."""
        processed_rows = current_row
        remaining_rows = max(0, total_rows - current_row)
        progress_percentage = round((current_row / max(1, total_rows)) * 100, 2)

        elapsed_sec = time.perf_counter() - job_start_time
        avg_row_sec = elapsed_sec / max(1, current_row)
        eta_sec = round(avg_row_sec * remaining_rows, 2)

        return {
            "processed_rows": processed_rows,
            "remaining_rows": remaining_rows,
            "progress_percentage": progress_percentage,
            "current_company": current_company,
            "current_row": current_row,
            "estimated_time_remaining": eta_sec,
        }

    def update_job_progress(
        self,
        job_id: UUID,
        current_row: int,
        total_rows: int,
        current_company: str,
        job_start_time: float,
        successful_rows: int = 0,
        failed_rows: int = 0,
    ) -> None:
        """Update job record with progress telemetry in database/memory repository."""
        if not self._job_repository:
            return

        metrics = self.calculate_metrics(
            current_row=current_row,
            total_rows=total_rows,
            current_company=current_company,
            job_start_time=job_start_time,
        )

        updates = {
            "processed_rows": metrics["processed_rows"],
            "successful_rows": successful_rows,
            "failed_rows": failed_rows,
        }

        try:
            self._job_repository.update_job(job_id, updates)
            logger.debug(
                f"Updated progress for Job '{job_id}' [{current_row}/{total_rows}] "
                f"- {metrics['progress_percentage']}% - ETA: {metrics['estimated_time_remaining']}s"
            )
        except Exception as exc:
            logger.warning(f"Failed intermediate progress update for Job '{job_id}': {str(exc)}")
