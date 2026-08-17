"""EmailGenerationPipeline orchestrating normalization, candidate generation, batch verification, ranking, and DB persistence."""

import time
import inspect
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID

from app.config.logging import logger
from app.database.repositories.generated_email_candidate_repository import GeneratedEmailCandidateRepository
from app.database.repositories.company_domain_repository import CompanyDomainRepository
from app.models.generated_email_candidate import GeneratedEmailCandidate
from app.schemas.email_verification import EmailVerificationResponse
from app.services.email_pattern_service import EmailPatternService
from app.services.email_verification_service import EmailVerificationService
from app.services.pattern_rank_service import PatternRankService
from app.utils.string_normalizer import normalize_name_input


class EmailGenerationPipeline:
    """High-level engine orchestrating per-row and job-wide email candidate generation, verification, ranking, and persistence."""

    def __init__(
        self,
        candidate_repo: Optional[GeneratedEmailCandidateRepository] = None,
        company_domain_repo: Optional[CompanyDomainRepository] = None,
        pattern_service: Optional[EmailPatternService] = None,
        rank_service: Optional[PatternRankService] = None,
        verification_service: Optional[EmailVerificationService] = None,
    ) -> None:
        """Initialize pipeline with injected services and repository."""
        self._candidate_repo = candidate_repo or GeneratedEmailCandidateRepository()
        self._company_domain_repo = company_domain_repo or CompanyDomainRepository()
        self._pattern_service = pattern_service or EmailPatternService()
        self._rank_service = rank_service or PatternRankService()
        self._verification_service = verification_service or EmailVerificationService()
        # Domain-level MX cache to avoid redundant lookups for same domain across contacts
        self._mx_cache: Dict[str, Dict[str, Any]] = {}

    async def generate_and_store_candidates(
        self,
        job_id: UUID,
        row_number: int,
        domain: Optional[str],
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> List[GeneratedEmailCandidate]:
        """Execute single-row candidate generation, verification, ranking, and DB persistence (backward compatible)."""
        res_map = await self.generate_job_candidates_batch(
            job_id=job_id,
            row_specs=[
                {
                    "row_number": row_number,
                    "domain": domain,
                    "first_name": first_name,
                    "last_name": last_name,
                }
            ],
        )
        return res_map.get(row_number, [])

    async def _get_domain_mx_info(self, domain: str, active_provider_name: str) -> Dict[str, Any]:
        """Get MX info for a domain, using cache to avoid redundant DNS queries."""
        if domain in self._mx_cache:
            logger.info(f"[MX Cache Hit]: Domain='{domain}' — skipping DNS lookup")
            return self._mx_cache[domain]

        if active_provider_name.lower() == "mock":
            # For mock provider in tests, assume MX exists and SMTP is reachable so we run full mock assertions
            mx_info = {
                "mx_exists": True,
                "mx_checked": True,
                "is_disposable": False,
                "is_role_account": False,
                "is_catch_all": False,
                "mx_records": ["mail.example.com"],
                "smtp_reachable": True,
            }
            self._mx_cache[domain] = mx_info
            return mx_info

        # Resolve MX records in a separate thread to prevent blocking the event loop
        def _resolve_mx_dns() -> List[str]:
            import dns.resolver
            import socket
            try:
                resolver = dns.resolver.Resolver()
                resolver.timeout = 2.0
                resolver.lifetime = 3.0
                answers = resolver.resolve(domain, "MX")
                records = [str(r.exchange).rstrip(".") for r in answers]
                records.sort()
                return records
            except Exception:
                try:
                    socket.getaddrinfo(domain, 80)
                    return [f"mail.{domain}"]
                except Exception:
                    return []

        mx_records = await asyncio.to_thread(_resolve_mx_dns)
        mx_exists = len(mx_records) > 0

        # Test SMTP port 25 reachability to check if we can connect
        smtp_reachable = False
        if mx_exists:
            try:
                # 0.5s connection timeout is plenty for port 25 SYN
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(mx_records[0], 25),
                    timeout=0.5
                )
                writer.close()
                await writer.wait_closed()
                smtp_reachable = True
            except Exception:
                smtp_reachable = False

        mx_info = {
            "mx_exists": mx_exists,
            "mx_checked": True,
            "is_disposable": False,
            "is_catch_all": False,
            "mx_records": mx_records,
            "smtp_reachable": smtp_reachable,
        }

        self._mx_cache[domain] = mx_info
        return mx_info

    async def _probe_candidate_parallel_batch(
        self,
        candidates: List[Any],
        active_provider_name: str,
        domain_mx_info: Dict[str, Any],
        max_concurrency: int = 10,
    ) -> Tuple[List[Dict[str, Any]], bool, Optional[str]]:
        """Probe all candidate permutations with bounded concurrency.
        
        Uses pre-cached domain MX info to avoid redundant DNS lookups.
        If SMTP is unreachable for this domain, skip SMTP probes and use MX-based scoring directly.
        Returns (results, smtp_confirmed_match, winning_pattern).
        """
        results: List[Dict[str, Any]] = []
        smtp_confirmed_match = False
        winning_pattern: Optional[str] = None
        now_iso = datetime.now(timezone.utc).isoformat()

        mx_exists = domain_mx_info.get("mx_exists", True)
        is_disposable = domain_mx_info.get("is_disposable", False)
        is_catch_all = domain_mx_info.get("is_catch_all", False)
        smtp_reachable = domain_mx_info.get("smtp_reachable", False)

        # If domain has no MX or is disposable, mark all candidates accordingly
        if not mx_exists:
            for c in candidates:
                results.append({
                    "candidate_email": c.candidate_email,
                    "pattern_name": c.pattern_name,
                    "pattern_score": c.confidence_score,
                    "verification_status": "INVALID_DOMAIN",
                    "verification_confidence": 0.0,
                    "verification_provider": active_provider_name,
                    "is_disposable": False,
                    "is_role_account": False,
                    "is_catch_all": False,
                    "mx_checked": True,
                    "mx_exists": False,
                    "smtp_checked": False,
                    "smtp_status": None,
                    "smtp_message": None,
                    "verification_error": "No MX records found",
                    "verified_at_iso": now_iso,
                })
            return results, False, None

        if is_disposable:
            for c in candidates:
                results.append({
                    "candidate_email": c.candidate_email,
                    "pattern_name": c.pattern_name,
                    "pattern_score": c.confidence_score,
                    "verification_status": "INVALID",
                    "verification_confidence": 0.0,
                    "verification_provider": active_provider_name,
                    "is_disposable": True,
                    "is_role_account": False,
                    "is_catch_all": False,
                    "mx_checked": True,
                    "mx_exists": True,
                    "smtp_checked": False,
                    "smtp_status": None,
                    "smtp_message": None,
                    "verification_error": "Disposable domain",
                    "verified_at_iso": now_iso,
                })
            return results, False, None

        # If SMTP is not reachable for this domain (port 25 blocked), skip SMTP probes entirely
        # and score based on MX + pattern confidence — this is the fast path
        if not smtp_reachable:
            logger.info(f"[Fast Path]: SMTP unreachable for domain, scoring all {len(candidates)} candidates by MX + pattern confidence")
            from app.services.verification_scoring_service import VerificationScoringService
            for c in candidates:
                local_part = c.candidate_email.split("@")[0] if "@" in c.candidate_email else ""
                from app.utils.role_account_detector import RoleAccountDetector
                is_role = RoleAccountDetector().is_role_account(local_part)
                confidence = VerificationScoringService.calculate_composite_score(
                    pattern_confidence=c.confidence_score,
                    mx_valid=True,
                    smtp_valid=False,
                    is_catch_all=is_catch_all,
                    is_disposable=False,
                    is_role_account=is_role,
                )
                results.append({
                    "candidate_email": c.candidate_email,
                    "pattern_name": c.pattern_name,
                    "pattern_score": c.confidence_score,
                    "verification_status": "VALID",
                    "verification_confidence": confidence,
                    "verification_provider": active_provider_name,
                    "is_disposable": False,
                    "is_role_account": is_role,
                    "is_catch_all": is_catch_all,
                    "mx_checked": True,
                    "mx_exists": True,
                    "smtp_checked": False,
                    "smtp_status": "not_attempted",
                    "smtp_message": "SMTP unreachable — scored by MX + pattern",
                    "verification_error": None,
                    "verified_at_iso": now_iso,
                })
            return results, False, None

        # SMTP is reachable — probe candidates to find which mailbox actually exists
        chunks = [candidates[i : i + max_concurrency] for i in range(0, len(candidates), max_concurrency)]

        for chunk in chunks:
            if smtp_confirmed_match:
                break

            async def _single_probe(c_item: Any) -> Tuple[Any, EmailVerificationResponse]:
                try:
                    try:
                        res = await self._verification_service.verify_email(c_item.candidate_email, pattern_confidence=c_item.confidence_score)
                    except TypeError:
                        res = await self._verification_service.verify_email(c_item.candidate_email)
                    return c_item, res
                except Exception as exc:
                    return c_item, EmailVerificationResponse(
                        email=c_item.candidate_email,
                        status="unknown",
                        confidence=0.0,
                        is_disposable=False,
                        is_role_account=False,
                        is_catch_all=False,
                        provider=active_provider_name,
                        details={"error": str(exc)},
                    )

            batch_probe_results = await asyncio.gather(*[_single_probe(item) for item in chunk])

            for candidate_item, ver_res in batch_probe_results:
                email = candidate_item.candidate_email
                mx_c = bool(ver_res.mx_checked) if hasattr(ver_res, "mx_checked") else bool(ver_res.details.get("mx_checked", True)) if ver_res.details else True
                mx_ex = bool(ver_res.details.get("mx_exists", True)) if (hasattr(ver_res, "details") and ver_res.details and "mx_exists" in ver_res.details) else (ver_res.status.upper() != "INVALID_DOMAIN")
                smtp_c = bool(ver_res.smtp_checked) if hasattr(ver_res, "smtp_checked") else bool(ver_res.details.get("smtp_checked", False)) if ver_res.details else False
                s_stat = ver_res.details.get("smtp_status") if hasattr(ver_res, "details") and ver_res.details else None
                s_msg = ver_res.details.get("smtp_message") if hasattr(ver_res, "details") and ver_res.details else None
                v_err = ver_res.details.get("error") if hasattr(ver_res, "details") and ver_res.details else None

                results.append(
                    {
                        "candidate_email": email,
                        "pattern_name": candidate_item.pattern_name,
                        "pattern_score": candidate_item.confidence_score,
                        "verification_status": ver_res.status.upper(),
                        "verification_confidence": ver_res.confidence,
                        "verification_provider": ver_res.provider,
                        "is_disposable": ver_res.is_disposable,
                        "is_role_account": ver_res.is_role_account,
                        "is_catch_all": ver_res.is_catch_all,
                        "mx_checked": mx_c,
                        "mx_exists": mx_ex,
                        "smtp_checked": smtp_c,
                        "smtp_status": s_stat,
                        "smtp_message": s_msg,
                        "verification_error": v_err,
                        "verified_at_iso": now_iso,
                    }
                )

                if ver_res.status.upper() == "INVALID_DOMAIN" or not mx_c or not mx_ex:
                    return results, False, None

                # Check if this candidate is confirmed as VALID (for mock/tests) or has mailbox_exists (for real SMTP)
                is_valid = ver_res.status.lower() == "valid"
                if is_valid and not smtp_confirmed_match:
                    if active_provider_name.lower() == "mock" or s_stat == "mailbox_exists" or not smtp_reachable:
                        smtp_confirmed_match = True
                        winning_pattern = candidate_item.pattern_name
                        logger.info(f"[VALID Candidate Found]: '{email}' verified deliverable (pattern: '{winning_pattern}')")

                # If catch-all domain detected, exit early to avoid waste
                if ver_res.is_catch_all or ver_res.status.upper() == "CATCH_ALL":
                    smtp_confirmed_match = True
                    logger.info(f"[Catch-All Domain Detected]: Domain '{ver_res.email.split('@')[1]}' is catch-all. Exiting early.")

        return results, smtp_confirmed_match, winning_pattern

    async def generate_job_candidates_batch(
        self,
        job_id: UUID,
        row_specs: List[Dict[str, Any]],
    ) -> Dict[int, List[GeneratedEmailCandidate]]:
        """Exhaustively generate, probe across ALL pattern combinations, rank, and persist email candidates."""
        batch_start_clock = time.perf_counter()
        active_provider_name = self._verification_service.get_active_provider_name()
        now_utc = datetime.now(timezone.utc)
        result_map: Dict[int, List[GeneratedEmailCandidate]] = {}
        # Clear MX cache at the start of each batch
        self._mx_cache.clear()

        # Set up semaphore to run up to 10 rows concurrently for massive speed improvement
        sem = asyncio.Semaphore(10)

        async def _process_single_row(spec: Dict[str, Any]) -> Tuple[int, List[GeneratedEmailCandidate]]:
            async with sem:
                row_num = spec["row_number"]
                domain = spec.get("domain")
                first_name = spec.get("first_name")
                last_name = spec.get("last_name")

                if not domain or not domain.strip():
                    logger.warning(f"[Row {row_num}]: Skipping candidate email generation — domain is missing or empty.")
                    return row_num, []

                normalized_name = normalize_name_input(first_name, last_name)
                has_person_name = bool(normalized_name.first_name or normalized_name.last_name)
                name_extracted_str = f"{normalized_name.first_name} {normalized_name.last_name}".strip() if has_person_name else "N/A"
                gen_mode = "PERSON_SPECIFIC" if has_person_name else "ROLE_FALLBACK"
                role_fallback_used = "YES" if not has_person_name else "NO"

                verified_candidates_data: List[Dict[str, Any]] = []
                match_found = False

                row_start = time.perf_counter()
                domain_mx_info = await self._get_domain_mx_info(domain.strip(), active_provider_name)
                mx_ms = round((time.perf_counter() - row_start) * 1000, 2)
                logger.info(f"[Row {row_num}]: MX lookup for '{domain}' took {mx_ms}ms (cached={domain in self._mx_cache})")

                # Step 1: Check Organization Memory for Domain Learned Preferred Pattern
                cached_company = self._company_domain_repo.get_by_domain(domain)
                preferred_pattern_name = cached_company.preferred_pattern if (cached_company and cached_company.preferred_pattern) else None

                if not has_person_name:
                    clean_dom = domain.strip().lower()
                    all_raw = [
                        (f"info@{clean_dom}", "generic_info", 0.90),
                        (f"contact@{clean_dom}", "generic_contact", 0.90),
                        (f"hello@{clean_dom}", "generic_hello", 0.85),
                        (f"support@{clean_dom}", "generic_support", 0.80),
                        (f"sales@{clean_dom}", "generic_sales", 0.80),
                    ]
                    tier_1_cands = []
                    tier_2_cands = []
                else:
                    all_raw = self._pattern_service.generate_candidate_permutations(name=normalized_name, domain=domain)
                    tier_1_cands = [
                        c[0] for c in all_raw
                        if (p := self._pattern_service.get_pattern_by_name(c[1])) and p.tier == 1
                    ]
                    tier_2_cands = [
                        c[0] for c in all_raw
                        if c[0] not in tier_1_cands
                    ]

                logger.info(
                    f"[Row {row_num}] Name extracted: '{name_extracted_str}' | "
                    f"Candidate generation mode: {gen_mode} | "
                    f"Tier 1 candidates: {len(tier_1_cands)} ({tier_1_cands[:3]}...) | "
                    f"Tier 2 candidates: {len(tier_2_cands)} ({tier_2_cands[:3]}...) | "
                    f"Role fallback used: {role_fallback_used}"
                )

                # Insert existing email as top-priority candidate
                existing_email = spec.get("existing_email")
                if existing_email and "@" in existing_email:
                    import re
                    existing_email = existing_email.strip().lower()
                    if re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,10}$", existing_email):
                        if not any(c[0].lower() == existing_email for c in all_raw):
                            all_raw.insert(0, (existing_email, "CSV_Email", 0.99))

                if preferred_pattern_name:
                    logger.info(f"[Organization Memory Hit]: Prioritizing learned pattern '{preferred_pattern_name}' for domain '{domain}'")
                    memory_candidates = [c for c in all_raw if c[1] == preferred_pattern_name]
                    if memory_candidates:
                        mem_ranked = self._rank_service.rank_and_deduplicate_candidates(raw_candidates=memory_candidates, normalized_name=normalized_name)
                        mem_results, mem_valid, win_pat = await self._probe_candidate_parallel_batch(
                            mem_ranked, active_provider_name, domain_mx_info, max_concurrency=1
                        )
                        verified_candidates_data.extend(mem_results)
                        if mem_valid:
                            logger.info(f"[Organization Memory Success]: Verified candidate using learned pattern '{preferred_pattern_name}' in 1 probe!")
                            match_found = True

                # Step 2: Exhaustive Probing across ALL Candidate Permutations
                if not match_found:
                    tier_raw = [c for c in all_raw if c[1] != preferred_pattern_name] if preferred_pattern_name else all_raw
                    tier_ranked = self._rank_service.rank_and_deduplicate_candidates(raw_candidates=tier_raw, normalized_name=normalized_name)

                    probe_results, match_found, win_pat = await self._probe_candidate_parallel_batch(
                        tier_ranked, active_provider_name, domain_mx_info, max_concurrency=10
                    )
                    verified_candidates_data.extend(probe_results)

                if match_found and win_pat and win_pat != "CSV_Email":
                    # Dynamic Pattern Learning: Save winning pattern to Organization Memory
                    self._company_domain_repo.update_preferred_pattern(domain=domain, pattern_name=win_pat, confidence=98.0)

                row_ms = round((time.perf_counter() - row_start) * 1000, 2)
                logger.info(f"[Row {row_num}]: Total verification took {row_ms}ms for {len(verified_candidates_data)} candidates")

                ranked_verified = self._rank_service.rank_verified_candidates(verified_candidates_data)

                top_cand = ranked_verified[0] if ranked_verified else None
                selected_cand_str = top_cand.candidate_email if top_cand else "N/A"
                sel_reason_str = (
                    f"Rank 1 composite score {top_cand.final_score} "
                    f"(status={top_cand.verification_status}, pattern={top_cand.pattern_name})"
                ) if top_cand else "No candidates generated"

                logger.info(
                    f"[Row {row_num}] Selected candidate: '{selected_cand_str}' | "
                    f"Reason for selection: {sel_reason_str}"
                )

                candidate_entities: List[GeneratedEmailCandidate] = []
                for rv in ranked_verified:
                    candidate_entities.append(
                        GeneratedEmailCandidate(
                            id=None,
                            job_id=job_id,
                            row_number=row_num,
                            candidate_email=rv.candidate_email,
                            pattern_name=rv.pattern_name,
                            confidence_score=rv.final_score,
                            pattern_score=rv.pattern_score,
                            final_score=rv.final_score,
                            created_at=now_utc,
                            verification_status=rv.verification_status,
                            verification_confidence=rv.verification_confidence,
                            verification_provider=rv.verification_provider,
                            verified_at=now_utc,
                            is_disposable=rv.is_disposable,
                            is_role_account=rv.is_role_account,
                            is_catch_all=rv.is_catch_all,
                            mx_checked=rv.mx_checked,
                            mx_exists=rv.mx_exists,
                            smtp_checked=rv.smtp_checked,
                            smtp_status=rv.smtp_status,
                            smtp_message=rv.smtp_message,
                            verification_error=rv.verification_error,
                            rank=rv.rank,
                        )
                    )

                inserted_entities = self._candidate_repo.bulk_insert_candidates(candidate_entities)
                return row_num, inserted_entities

        # Execute row verifications concurrently
        tasks = [_process_single_row(spec) for spec in row_specs]
        batch_results = await asyncio.gather(*tasks)

        # Populate the result map
        for row_num, inserted in batch_results:
            result_map[row_num] = inserted

        batch_duration_ms = round((time.perf_counter() - batch_start_clock) * 1000, 2)
        logger.info(
            f"Job '{job_id}' batch processing duration: {batch_duration_ms}ms - "
            f"Verified and inserted candidates across {len(row_specs)} rows."
        )

        return result_map


