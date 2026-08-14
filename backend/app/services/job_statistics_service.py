"""JobStatisticsService computing in-depth statistics and diagnostic error reports per job."""

from typing import Dict, List, Any, Optional
from uuid import UUID

from app.core.exceptions import EntityNotFoundException
from app.database.repositories.job_repository import JobRepository
from app.database.repositories.job_result_repository import JobResultRepository
from app.database.repositories.generated_email_candidate_repository import GeneratedEmailCandidateRepository
from app.schemas.reporting import JobStatisticsResponse, JobErrorReportResponse


class JobStatisticsService:
    """Service computing granular processing metrics, cache rates, confidence scores, and error reports."""

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

    def get_job_statistics(self, job_id: UUID) -> JobStatisticsResponse:
        """Compute detailed performance and accuracy statistics for target job."""
        job = self._job_repo.get_by_id(job_id)
        if not job:
            raise EntityNotFoundException("ProcessingJob", str(job_id))

        results = self._job_result_repo.get_by_job_id(job_id)
        candidates = self._candidate_repo.get_by_job_id(job_id)

        rows_processed = len(results)
        successful_rows = sum(1 for r in results if r.success)
        failed_rows = rows_processed - successful_rows

        companies_resolved = sum(1 for r in results if r.resolved_domain)
        cache_hit_count = sum(1 for r in results if r.cached)
        cache_hit_rate = round((cache_hit_count / companies_resolved) * 100, 2) if companies_resolved > 0 else 0.0

        total_candidates = len(candidates)
        valid_candidates = sum(1 for c in candidates if str(c.verification_status).upper() == "VALID")
        ver_success_rate = round((valid_candidates / total_candidates) * 100, 2) if total_candidates > 0 else 0.0

        conf_scores = [c.verification_confidence for c in candidates if c.verification_confidence is not None]
        avg_confidence = round(sum(conf_scores) / len(conf_scores), 2) if conf_scores else 0.0

        rank_scores = [c.final_score for c in candidates if c.final_score is not None]
        avg_ranking_score = round(sum(rank_scores) / len(rank_scores), 2) if rank_scores else 0.0

        # Provider usage distribution
        provider_usage: Dict[str, int] = {}
        for r in results:
            p_name = r.provider or "Unknown"
            provider_usage[p_name] = provider_usage.get(p_name, 0) + 1

        for c in candidates:
            p_name = c.verification_provider or "Unknown"
            provider_usage[p_name] = provider_usage.get(p_name, 0) + 1

        return JobStatisticsResponse(
            job_id=job.id,
            status=job.status,
            original_filename=job.original_filename,
            created_at=job.created_at,
            completed_at=job.completed_at,
            duration_sec=job.duration_sec,
            row_count=job.row_count,
            processed_rows=job.processed_rows,
            successful_rows=job.successful_rows,
            failed_rows=job.failed_rows,
            companies_resolved=companies_resolved,
            cache_hit_count=cache_hit_count,
            cache_hit_rate=cache_hit_rate,
            verification_success_rate=ver_success_rate,
            average_confidence=avg_confidence,
            average_ranking_score=avg_ranking_score,
            total_candidates_generated=total_candidates,
            provider_usage=provider_usage,
        )

    def get_job_error_report(self, job_id: UUID) -> JobErrorReportResponse:
        """Fetch granular error details, failing rows, and provider errors for job."""
        job = self._job_repo.get_by_id(job_id)
        if not job:
            raise EntityNotFoundException("ProcessingJob", str(job_id))

        results = self._job_result_repo.get_by_job_id(job_id)
        candidates = self._candidate_repo.get_by_job_id(job_id)

        failed_rows_list: List[Dict[str, Any]] = []
        failed_companies_list: List[str] = []

        for r in results:
            if not r.success or r.error_message:
                failed_rows_list.append(
                    {
                        "row_number": r.row_number,
                        "company": r.company,
                        "error_message": r.error_message,
                    }
                )
                failed_companies_list.append(r.company)

        ver_failures_list: List[Dict[str, Any]] = []
        provider_failures_list: List[Dict[str, Any]] = []

        for c in candidates:
            if str(c.verification_status).upper() in ("INVALID", "UNKNOWN") or c.verification_error:
                ver_failures_list.append(
                    {
                        "row_number": c.row_number,
                        "email": c.candidate_email,
                        "status": c.verification_status,
                        "provider": c.verification_provider,
                        "error": c.verification_error,
                    }
                )
                if c.verification_error:
                    provider_failures_list.append(
                        {
                            "email": c.candidate_email,
                            "provider": c.verification_provider,
                            "error": c.verification_error,
                        }
                    )

        retry_stats = {
            "total_verifications": len(candidates),
            "failed_verifications": len(ver_failures_list),
            "failed_rows_count": len(failed_rows_list),
        }

        return JobErrorReportResponse(
            job_id=job.id,
            status=job.status,
            error_message=job.error_message,
            failed_rows=failed_rows_list,
            failed_companies=failed_companies_list,
            verification_failures=ver_failures_list,
            provider_failures=provider_failures_list,
            retry_statistics=retry_stats,
        )
