"""Service dependency injectors for FastAPI routes."""

from typing import Optional
from fastapi import Depends
from supabase import Client

import redis
from app.api.dependencies.database import get_db
from app.config.settings import settings
from app.database.repositories.company_domain_repository import CompanyDomainRepository
from app.database.repositories.domain_resolution_log_repository import DomainResolutionLogRepository
from app.database.repositories.domain_analytics_repository import DomainAnalyticsRepository
from app.providers.email_verification.base import EmailVerificationProvider
from app.providers.email_verification.provider_factory import ProviderFactory
from app.services.domain_resolver_service import DomainResolverService
from app.services.domain_validation_service import DomainValidationService
from app.services.confidence_recalculation_service import ConfidenceRecalculationService
from app.services.cache_validation_service import CacheValidationService
from app.services.cache_statistics_service import CacheStatisticsService
from app.services.domain_analytics_service import DomainAnalyticsService
from app.services.verification_provider_service import VerificationProviderService
from app.services.email_verification_service import EmailVerificationService
from app.services.redis_health_service import RedisHealthService
from app.services.redis_queue_service import RedisQueueService
from app.services.export_service import ExportService
from app.services.job_statistics_service import JobStatisticsService
from app.services.analytics_service import AnalyticsService


_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> Optional[redis.Redis]:
    """Dependency provider creating or returning singleton Redis client instance."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        if settings.REDIS_URL:
            _redis_client = redis.Redis.from_url(
                settings.REDIS_URL,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                decode_responses=True,
            )
        else:
            _redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD or None,
                db=settings.REDIS_DB,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                decode_responses=True,
            )
        return _redis_client
    except Exception:
        return None


def get_redis_health_service(
    client: Optional[redis.Redis] = Depends(get_redis_client),
) -> RedisHealthService:
    """Dependency provider injecting RedisHealthService."""
    return RedisHealthService(redis_client=client)


def get_redis_queue_service(
    client: Optional[redis.Redis] = Depends(get_redis_client),
) -> RedisQueueService:
    """Dependency provider injecting RedisQueueService."""
    return RedisQueueService(redis_client=client)


def get_domain_validation_service() -> DomainValidationService:
    """Dependency provider injecting DomainValidationService."""
    return DomainValidationService()


def get_confidence_recalculation_service() -> ConfidenceRecalculationService:
    """Dependency provider injecting ConfidenceRecalculationService."""
    return ConfidenceRecalculationService()


def get_cache_validation_service() -> CacheValidationService:
    """Dependency provider injecting CacheValidationService."""
    return CacheValidationService()


def get_cache_statistics_service(
    db: Optional[Client] = Depends(get_db),
) -> CacheStatisticsService:
    """Dependency provider injecting CacheStatisticsService."""
    company_repo = CompanyDomainRepository(client=db) if db else None
    return CacheStatisticsService(company_domain_repo=company_repo)


def get_domain_resolver_service(
    db: Optional[Client] = Depends(get_db),
    validation_service: DomainValidationService = Depends(get_domain_validation_service),
    confidence_service: ConfidenceRecalculationService = Depends(get_confidence_recalculation_service),
    cache_val_service: CacheValidationService = Depends(get_cache_validation_service),
    cache_stats_service: CacheStatisticsService = Depends(get_cache_statistics_service),
) -> DomainResolverService:
    """Dependency provider injecting DomainResolverService configured with database repositories and intelligence services."""
    company_repo = CompanyDomainRepository(client=db) if db else None
    audit_repo = DomainResolutionLogRepository(client=db) if db else None
    return DomainResolverService(
        company_domain_repo=company_repo,
        audit_log_repo=audit_repo,
        validation_service=validation_service,
        confidence_service=confidence_service,
        cache_validation_service=cache_val_service,
        cache_statistics_service=cache_stats_service,
    )


def get_domain_analytics_repository(
    db: Optional[Client] = Depends(get_db),
) -> DomainAnalyticsRepository:
    """Dependency provider injecting DomainAnalyticsRepository."""
    return DomainAnalyticsRepository(client=db)


def get_domain_analytics_service(
    db: Optional[Client] = Depends(get_db),
    analytics_repo: DomainAnalyticsRepository = Depends(get_domain_analytics_repository),
    cache_stats_service: CacheStatisticsService = Depends(get_cache_statistics_service),
) -> DomainAnalyticsService:
    """Dependency provider injecting DomainAnalyticsService."""
    return DomainAnalyticsService(
        analytics_repo=analytics_repo,
        cache_stats_service=cache_stats_service,
    )


def get_email_verification_provider() -> EmailVerificationProvider:
    """Dependency provider factory instantiating verification provider based on environment configuration."""
    return ProviderFactory.create()


def get_verification_provider_service(
    provider: EmailVerificationProvider = Depends(get_email_verification_provider),
) -> VerificationProviderService:
    """Dependency provider injecting VerificationProviderService."""
    return VerificationProviderService(provider=provider)


def get_email_verification_service(
    provider: EmailVerificationProvider = Depends(get_email_verification_provider),
) -> EmailVerificationService:
    """Dependency provider injecting EmailVerificationService."""
    return EmailVerificationService(provider=provider)


def get_job_service(
    db: Optional[Client] = Depends(get_db),
    redis_queue_service: RedisQueueService = Depends(get_redis_queue_service),
) -> "JobService":
    """Dependency provider injecting JobService with JobRepository and RedisQueueService."""
    from app.database.repositories.job_repository import JobRepository
    from app.services.job_service import JobService

    job_repo = JobRepository(client=db) if db else None
    return JobService(job_repository=job_repo, redis_queue_service=redis_queue_service)


def get_job_result_repository(
    db: Optional[Client] = Depends(get_db),
) -> "JobResultRepository":
    """Dependency provider injecting JobResultRepository."""
    from app.database.repositories.job_result_repository import JobResultRepository

    return JobResultRepository(client=db)


def get_worker_manager() -> "WorkerManager":
    """Dependency provider injecting WorkerManager singleton instance."""
    from app.workers.worker_manager import WorkerManager

    return WorkerManager.get_instance()


def get_worker_service(
    manager: "WorkerManager" = Depends(get_worker_manager),
) -> "WorkerService":
    """Dependency provider injecting WorkerService."""
    from app.services.worker_service import WorkerService

    return WorkerService(manager=manager)


def get_generated_candidate_repository(
    db: Optional[Client] = Depends(get_db),
) -> "GeneratedEmailCandidateRepository":
    """Dependency provider injecting GeneratedEmailCandidateRepository."""
    from app.database.repositories.generated_email_candidate_repository import GeneratedEmailCandidateRepository

    return GeneratedEmailCandidateRepository(client=db)


def get_email_pattern_service() -> "EmailPatternService":
    """Dependency provider injecting EmailPatternService."""
    from app.services.email_pattern_service import EmailPatternService

    return EmailPatternService()


def get_export_service(
    db: Optional[Client] = Depends(get_db),
) -> ExportService:
    """Dependency provider injecting ExportService."""
    from app.database.repositories.job_repository import JobRepository
    from app.database.repositories.job_result_repository import JobResultRepository
    from app.database.repositories.generated_email_candidate_repository import GeneratedEmailCandidateRepository

    job_repo = JobRepository(client=db) if db else None
    job_result_repo = JobResultRepository(client=db) if db else None
    candidate_repo = GeneratedEmailCandidateRepository(client=db) if db else None

    return ExportService(
        job_repo=job_repo,
        job_result_repo=job_result_repo,
        candidate_repo=candidate_repo,
    )


def get_job_statistics_service(
    db: Optional[Client] = Depends(get_db),
) -> JobStatisticsService:
    """Dependency provider injecting JobStatisticsService."""
    from app.database.repositories.job_repository import JobRepository
    from app.database.repositories.job_result_repository import JobResultRepository
    from app.database.repositories.generated_email_candidate_repository import GeneratedEmailCandidateRepository

    job_repo = JobRepository(client=db) if db else None
    job_result_repo = JobResultRepository(client=db) if db else None
    candidate_repo = GeneratedEmailCandidateRepository(client=db) if db else None

    return JobStatisticsService(
        job_repo=job_repo,
        job_result_repo=job_result_repo,
        candidate_repo=candidate_repo,
    )


def get_analytics_service(
    db: Optional[Client] = Depends(get_db),
) -> AnalyticsService:
    """Dependency provider injecting AnalyticsService."""
    from app.database.repositories.job_repository import JobRepository
    from app.database.repositories.job_result_repository import JobResultRepository
    from app.database.repositories.company_domain_repository import CompanyDomainRepository
    from app.database.repositories.generated_email_candidate_repository import GeneratedEmailCandidateRepository

    job_repo = JobRepository(client=db) if db else None
    job_result_repo = JobResultRepository(client=db) if db else None
    domain_repo = CompanyDomainRepository(client=db) if db else None
    candidate_repo = GeneratedEmailCandidateRepository(client=db) if db else None

    return AnalyticsService(
        job_repo=job_repo,
        job_result_repo=job_result_repo,
        domain_repo=domain_repo,
        candidate_repo=candidate_repo,
    )


def get_platform_analytics_service(
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> AnalyticsService:
    """Dependency provider alias injecting AnalyticsService for platform analytics requests."""
    return analytics_service


def get_reporting_service(
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> AnalyticsService:
    """Dependency provider alias injecting AnalyticsService for operational reporting requests."""
    return analytics_service
