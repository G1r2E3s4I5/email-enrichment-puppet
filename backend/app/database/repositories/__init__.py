"""Database repositories package."""

from app.database.repositories.company_domain_repository import CompanyDomainRepository
from app.database.repositories.domain_resolution_log_repository import DomainResolutionLogRepository
from app.database.repositories.job_repository import JobRepository
from app.database.repositories.job_result_repository import JobResultRepository
from app.database.repositories.generated_email_candidate_repository import GeneratedEmailCandidateRepository

__all__ = [
    "CompanyDomainRepository",
    "DomainResolutionLogRepository",
    "JobRepository",
    "JobResultRepository",
    "GeneratedEmailCandidateRepository",
]
