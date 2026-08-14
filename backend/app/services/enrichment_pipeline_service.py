"""EnrichmentPipelineService executing parallel company domain resolution and production email candidate verification."""

import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4

from app.config.logging import logger
from app.config.settings import settings
from app.database.repositories.job_result_repository import JobResultRepository
from app.database.repositories.generated_email_candidate_repository import GeneratedEmailCandidateRepository
from app.models.job_result import JobResult
from app.models.generated_email_candidate import GeneratedEmailCandidate
from app.services.domain_resolver_service import DomainResolverService
from app.services.email_generation_pipeline import EmailGenerationPipeline
from app.services.email_verification_service import EmailVerificationService
from app.utils.normalization import normalize_company_name
from app.schemas.domain_resolver import ResolverDomainResult
import re


class EnrichmentPipelineService:
    """Production service layer executing domain resolution and email candidate verification pipeline."""

    def __init__(
        self,
        job_result_repository: Optional[JobResultRepository] = None,
        candidate_repository: Optional[GeneratedEmailCandidateRepository] = None,
        domain_resolver_service: Optional[DomainResolverService] = None,
        verification_service: Optional[EmailVerificationService] = None,
        email_generation_pipeline: Optional[EmailGenerationPipeline] = None,
    ) -> None:
        """Initialize pipeline service with injected repositories and domain/candidate/verification engines."""
        self._job_result_repository = job_result_repository or JobResultRepository()
        self._candidate_repository = candidate_repository or GeneratedEmailCandidateRepository()
        self._domain_resolver_service = domain_resolver_service or DomainResolverService()
        self._verification_service = verification_service or EmailVerificationService()
        self._email_generation_pipeline = email_generation_pipeline or EmailGenerationPipeline(
            candidate_repo=self._candidate_repository,
            verification_service=self._verification_service,
        )

    def extract_domain_from_url(self, url: str) -> Optional[str]:
        """Clean and extract domain name from raw URL string."""
        if not url or not isinstance(url, str):
            return None
        url = url.strip().lower()
        # Remove protocol
        url = re.sub(r"^https?://", "", url)
        # Remove www.
        url = re.sub(r"^www\d*\.", "", url)
        # Split by path/query separator and take host part
        host = url.split("/")[0].split("?")[0].split("#")[0]
        # Simple regex validation for domain
        if re.match(r"^[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,10}$", host):
            return host
        return None

    def is_generic_or_social_domain(self, domain: str) -> bool:
        """Check if domain is a generic social media or jobs platform."""
        social_platforms = {
            "linkedin.com", "facebook.com", "twitter.com", "instagram.com", 
            "youtube.com", "breezy.hr", "github.com", "medium.com", "xing.com"
        }
        return domain in social_platforms or any(domain.endswith("." + sp) for sp in social_platforms)

    def generate_placeholder_domain(self, company_name: str) -> str:
        """Generate placeholder domain from company name (e.g. 'OpenAI' -> 'openai.com')."""
        normalized = normalize_company_name(company_name or "")
        clean_name = "".join(c for c in normalized if c.isalnum())
        if not clean_name:
            clean_name = "company"
        return f"{clean_name}.com"

    def generate_candidate_emails(
        self,
        domain: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> List[str]:
        """Generate email candidate permutations (legacy helper compatibility)."""
        fn = (first_name or "").strip().lower()
        ln = (last_name or "").strip().lower()

        if fn and ln:
            f_initial = fn[0]
            candidates = [
                f"{fn}@{domain}",
                f"{f_initial}.{ln}@{domain}",
                f"{f_initial}{ln}@{domain}",
                f"{fn}.{ln}@{domain}",
            ]
        elif fn:
            candidates = [f"{fn}@{domain}", f"{fn}.contact@{domain}"]
        else:
            candidates = [f"contact@{domain}", f"info@{domain}", f"hello@{domain}"]

        return list(dict.fromkeys(candidates))

    async def process_row(
        self,
        job_id: UUID,
        row_number: int,
        row_data: Dict[str, Any],
        company_column: str,
    ) -> JobResult:
        """Execute single CSV row enrichment pipeline (backward compatibility)."""
        results = await self.process_job_batch(
            job_id=job_id,
            rows=[row_data],
            company_column=company_column,
            start_row_number=row_number,
        )
        return results[0]

    async def process_job_batch(
        self,
        job_id: UUID,
        rows: List[Dict[str, Any]],
        company_column: str,
        start_row_number: int = 1,
    ) -> List[JobResult]:
        """Execute job-wide enrichment pipeline with deduplicated domain resolution:

        Pipeline sequence:
        CSV Rows -> Deduplicated Company Domain Resolution -> Store JobResults -> Accumulate Candidates across all rows -> Job-Wide Batch Verification -> Per-Row Rank & Store Candidates
        """
        job_results: List[JobResult] = []
        row_specs: List[Dict[str, Any]] = []

        if not rows:
            return []

        # Prepare company names list preserving CSV row order
        company_names = [(row_data.get(company_column) or "").strip() for row_data in rows]

        # Step 0: Try to pre-resolve domain from Website/Domain columns in the CSV row
        companies_to_resolve = []
        pre_resolved_domains: Dict[int, ResolverDomainResult] = {}

        for idx_offset, row_data in enumerate(rows):
            row_number = start_row_number + idx_offset
            company_val = (row_data.get(company_column) or "").strip()
            
            website_val = None
            for col in ["Website", "website", "Company Website", "Domain", "domain", "Company Domain"]:
                if col in row_data and row_data[col]:
                    extracted = self.extract_domain_from_url(row_data[col])
                    if extracted and not self.is_generic_or_social_domain(extracted):
                        website_val = extracted
                        break
            
            if website_val:
                pre_resolved_domains[row_number] = ResolverDomainResult(
                    success=True,
                    company=company_val,
                    domain=website_val,
                    provider="CSV_Website",
                    cached=True,
                    confidence=100.0,
                    error=None,
                )
            else:
                companies_to_resolve.append(company_val)

        # Step 1: Execute Parallel Domain Resolution for remaining company names
        resolver_results = []
        if companies_to_resolve:
            concurrency = getattr(settings, "DOMAIN_RESOLUTION_CONCURRENCY", 20)
            resolver_results = await self._domain_resolver_service.resolve_domains_batch(
                companies=companies_to_resolve,
                concurrency=concurrency,
            )

        resolver_iter = iter(resolver_results)

        for idx_offset, row_data in enumerate(rows):
            row_number = start_row_number + idx_offset
            company_val = company_names[idx_offset]
            
            # Support combined Name columns or separate First/Last Name columns
            full_name_val = (
                row_data.get("Name")
                or row_data.get("name")
                or row_data.get("Full Name")
                or row_data.get("full_name")
                or row_data.get("Employee Name")
                or row_data.get("Person Name")
                or ""
            )
            first_name_val = row_data.get("First Name") or row_data.get("first_name") or row_data.get("FirstName") or full_name_val
            last_name_val = row_data.get("Last Name") or row_data.get("last_name") or row_data.get("LastName") or ""

            # Extract existing email if present
            existing_email_val = (
                row_data.get("Email")
                or row_data.get("email")
                or row_data.get("Primary Email")
                or row_data.get("email_address")
                or row_data.get("Email Address")
                or ""
            ).strip()

            if not company_val:
                job_result = JobResult(
                    id=uuid4(),
                    job_id=job_id,
                    row_number=row_number,
                    company="N/A",
                    success=False,
                    error_message="Empty company name in CSV row",
                    processed_at=datetime.now(timezone.utc),
                )
                self._job_result_repository.insert_result(job_result)
                job_results.append(job_result)
                continue

            if row_number in pre_resolved_domains:
                resolver_res = pre_resolved_domains[row_number]
            else:
                try:
                    resolver_res = next(resolver_iter)
                except StopIteration:
                    resolver_res = ResolverDomainResult(
                        success=False,
                        company=company_val,
                        domain=None,
                        provider=None,
                        cached=False,
                        confidence=0.0,
                        error="No resolution attempted",
                    )

            if resolver_res.success and resolver_res.domain:
                resolved_domain = resolver_res.domain
                provider = resolver_res.provider
                cached = resolver_res.cached
                success = True
                error_msg = None
            else:
                resolved_domain = self.generate_placeholder_domain(company_val)
                provider = "PlaceholderFallback"
                cached = False
                success = True
                error_msg = resolver_res.error or "Fallback placeholder domain"

            job_result = JobResult(
                id=uuid4(),
                job_id=job_id,
                row_number=row_number,
                company=company_val,
                resolved_domain=resolved_domain,
                provider=provider,
                cached=cached,
                success=success,
                error_message=error_msg,
                processed_at=datetime.now(timezone.utc),
            )

            logger.debug(
                f"Domain resolved for '{company_val}': '{resolved_domain}' "
                f"(Provider: {provider}, Cached: {cached})"
            )

            self._job_result_repository.insert_result(job_result)
            job_results.append(job_result)

            if resolved_domain:
                row_specs.append(
                    {
                        "row_number": row_number,
                        "domain": resolved_domain,
                        "first_name": first_name_val,
                        "last_name": last_name_val,
                        "existing_email": existing_email_val,
                    }
                )

        # Step 2: Job-Wide Candidate Permutations Generation, Batch Verification, Per-Row Ranking & Persistence
        if row_specs:
            try:
                await self._email_generation_pipeline.generate_job_candidates_batch(
                    job_id=job_id,
                    row_specs=row_specs,
                )
                logger.info(
                    f"Job '{job_id}' candidate generation, batch verification, ranking, and persistence complete across {len(row_specs)} rows."
                )
            except Exception as gen_exc:
                logger.error(
                    f"Candidate verification batch pipeline exception for Job '{job_id}': {str(gen_exc)}",
                    exc_info=True,
                )

        return job_results
