"""Domain models package."""

from app.models.company_domain import CompanyDomain
from app.models.domain_resolution_log import DomainResolutionLog
from app.models.job import ProcessingJob
from app.models.job_result import JobResult
from app.models.generated_email_candidate import GeneratedEmailCandidate

__all__ = [
    "CompanyDomain",
    "DomainResolutionLog",
    "ProcessingJob",
    "JobResult",
    "GeneratedEmailCandidate",
]
