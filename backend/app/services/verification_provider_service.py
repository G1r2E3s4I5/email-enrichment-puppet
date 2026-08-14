"""VerificationProviderService executing provider verification, batch processing, parallel verification engine, and telemetry logging."""

import time
from typing import Dict, List, Any, Optional
from app.config.logging import logger
from app.config.settings import settings
from app.providers.email_verification.base import EmailVerificationProvider
from app.providers.email_verification.provider_factory import ProviderFactory
from app.providers.email_verification.provider_registry import ProviderRegistry
from app.schemas.email_verification import EmailVerificationResponse
from app.services.parallel_verification_engine import ParallelVerificationEngine


class VerificationProviderService:
    """Service layer delegating verification to configured provider and normalizing responses."""

    def __init__(
        self,
        provider: Optional[Any] = None,
        parallel_engine: Optional[ParallelVerificationEngine] = None,
    ) -> None:
        """Initialize service with injected provider instance or factory default and parallel execution engine."""
        self._provider = provider
        self._parallel_engine = parallel_engine or ParallelVerificationEngine()

    def get_provider(self) -> Any:
        """Retrieve active provider instance (reused across requests)."""
        if self._provider is not None:
            return self._provider
        # Instantiate provider once and cache on instance
        self._provider = ProviderFactory.create()
        return self._provider

    def get_active_provider_name(self) -> str:
        """Return name of active provider."""
        provider = self.get_provider()
        if hasattr(provider, "get_provider_name"):
            return provider.get_provider_name()
        return "Mock"

    async def verify_email(self, email: str, pattern_confidence: Optional[float] = None) -> EmailVerificationResponse:
        """Execute single email verification against active provider, log telemetry, and return normalized response object."""
        provider = self.get_provider()
        provider_name = self.get_active_provider_name()

        logger.info(f"Provider selected: '{provider_name}'")
        logger.info(f"Verification provider: '{provider_name}'")

        start_clock = time.perf_counter()

        try:
            if hasattr(provider, "verify_email") and callable(getattr(provider, "verify_email")):
                try:
                    legacy_res = await provider.verify_email(email, pattern_confidence=pattern_confidence) if pattern_confidence is not None else await provider.verify_email(email)
                except TypeError:
                    legacy_res = await provider.verify_email(email)
                duration_ms = round((time.perf_counter() - start_clock) * 1000, 2)
                logger.info(f"Verification duration: {duration_ms}ms")
                if isinstance(legacy_res, EmailVerificationResponse):
                    return legacy_res
                raw_res = legacy_res if isinstance(legacy_res, dict) else {}
            elif hasattr(provider, "verify") and callable(getattr(provider, "verify")):
                if pattern_confidence is not None:
                    try:
                        raw_res = await provider.verify(email, pattern_confidence=pattern_confidence)
                    except TypeError:
                        raw_res = await provider.verify(email)
                else:
                    raw_res = await provider.verify(email)
                duration_ms = round((time.perf_counter() - start_clock) * 1000, 2)
                logger.info(f"Verification duration: {duration_ms}ms")
            else:
                raise AttributeError(f"Provider '{provider_name}' does not implement verify() or verify_email()")

            logger.info(f"Provider response: {raw_res}")

            status_val = str(raw_res.get("status", "unknown")).lower()
            confidence_val = float(raw_res.get("confidence", 0.0))
            is_disp = bool(raw_res.get("is_disposable", False))
            is_role = bool(raw_res.get("is_role_account", False))
            is_catch = bool(raw_res.get("is_catch_all", False))
            mx_chk = bool(raw_res.get("mx_checked", raw_res.get("mx_exists", True)))
            smtp_chk = bool(raw_res.get("smtp_checked", raw_res.get("smtp_code", 0) > 0 or raw_res.get("smtp_status") not in (None, "", "not_attempted")))
            err_msg = raw_res.get("error")

            logger.info(
                f"[AUDIT VERIFICATION]: Candidate='{email}' | Selected Provider='{provider_name}' | "
                f"MX Result={raw_res.get('mx_exists', False)} (Checked={mx_chk}) | "
                f"SMTP Result='{raw_res.get('smtp_status', 'N/A')}' (Checked={smtp_chk}) | "
                f"Confidence Score={confidence_val}%"
            )

            return EmailVerificationResponse(
                email=email,
                status=status_val,
                confidence=confidence_val,
                is_disposable=is_disp,
                is_role_account=is_role,
                is_catch_all=is_catch,
                mx_checked=mx_chk,
                smtp_checked=smtp_chk,
                provider=provider_name,
                details={
                    "duration_ms": duration_ms,
                    "mx_exists": raw_res.get("mx_exists", False),
                    "smtp_status": raw_res.get("smtp_status", "unknown"),
                    "mx_checked": mx_chk,
                    "smtp_checked": smtp_chk,
                    "error": err_msg,
                },
            )
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_clock) * 1000, 2)
            logger.error(f"Provider failure: '{provider_name}' raised exception for '{email}': {str(exc)}")

            return EmailVerificationResponse(
                email=email,
                status="unknown",
                confidence=0.0,
                is_disposable=False,
                is_role_account=False,
                is_catch_all=False,
                mx_checked=False,
                smtp_checked=False,
                provider=provider_name,
                details={
                    "duration_ms": duration_ms,
                    "error": str(exc),
                },
            )

    async def verify_emails_batch(
        self,
        emails: List[str],
        batch_size: Optional[int] = None,
        max_concurrency: Optional[int] = None,
    ) -> List[EmailVerificationResponse]:
        """Batch verify candidate email addresses in parallel using ParallelVerificationEngine."""
        if not emails:
            return []

        provider = self.get_provider()
        provider_name = self.get_active_provider_name()
        chunk_size = batch_size or getattr(settings, "EMAIL_VERIFICATION_BATCH_SIZE", 50)

        total_emails = len(emails)
        logger.info(f"Provider selected: '{provider_name}'")
        logger.info(f"Provider used: '{provider_name}'")

        # Chunk candidate email list
        chunks = [emails[i : i + chunk_size] for i in range(0, total_emails, chunk_size)]
        logger.info(f"Batch started: Total emails={total_emails}, Total chunks={len(chunks)}, Batch size={chunk_size}")

        if max_concurrency is not None and max_concurrency != self._parallel_engine.max_concurrency:
            engine = ParallelVerificationEngine(
                max_concurrency=max_concurrency,
                retry_count=self._parallel_engine.retry_count,
                timeout=self._parallel_engine.timeout,
                requests_per_second=self._parallel_engine.requests_per_second,
                backoff_base=self._parallel_engine.backoff_base,
            )
        else:
            engine = self._parallel_engine

        batch_raw_results, metrics = await engine.execute_parallel_verification(
            provider=provider,
            chunks=chunks,
            provider_name=provider_name,
        )

        all_responses: List[EmailVerificationResponse] = []
        failed_verifications = 0

        for email_addr, item_res in zip(emails, batch_raw_results):
            if isinstance(item_res, EmailVerificationResponse):
                all_responses.append(item_res)
                if item_res.status == "unknown":
                    failed_verifications += 1
            elif isinstance(item_res, dict):
                status_val = str(item_res.get("status", "unknown")).lower()
                confidence_val = float(item_res.get("confidence", 0.0))
                is_disp = bool(item_res.get("is_disposable", False))
                is_role = bool(item_res.get("is_role_account", False))
                is_catch = bool(item_res.get("is_catch_all", False))
                mx_chk = bool(item_res.get("mx_checked", item_res.get("mx_exists", True)))
                smtp_chk = bool(item_res.get("smtp_checked", item_res.get("smtp_code", 0) > 0 or item_res.get("smtp_status") not in (None, "", "not_attempted")))
                err_msg = item_res.get("error")

                if status_val == "unknown" or err_msg is not None:
                    failed_verifications += 1

                all_responses.append(
                    EmailVerificationResponse(
                        email=email_addr,
                        status=status_val,
                        confidence=confidence_val,
                        is_disposable=is_disp,
                        is_role_account=is_role,
                        is_catch_all=is_catch,
                        mx_checked=mx_chk,
                        smtp_checked=smtp_chk,
                        provider=provider_name,
                        details={
                            "duration_ms": metrics.get("total_duration_ms", 0.0),
                            "mx_exists": item_res.get("mx_exists", False),
                            "smtp_status": item_res.get("smtp_status", "unknown"),
                            "error": err_msg,
                        },
                    )
                )
            else:
                failed_verifications += 1
                all_responses.append(
                    EmailVerificationResponse(
                        email=email_addr,
                        status="unknown",
                        confidence=0.0,
                        is_disposable=False,
                        is_role_account=False,
                        is_catch_all=False,
                        provider=provider_name,
                        details={"error": "Invalid result payload format"},
                    )
                )

        logger.info(
            f"Batch completed: Processed {total_emails} emails in {metrics.get('total_duration_ms', 0.0)}ms "
            f"(Throughput: {metrics.get('throughput_eps', 0.0)} emails/sec) via provider '{provider_name}'"
        )
        logger.info(f"Failed verifications: {failed_verifications}/{total_emails}")
        logger.info(f"Total batch throughput: {metrics.get('throughput_eps', 0.0)} emails/sec")

        return all_responses

    async def get_providers_metadata(self) -> Dict[str, Any]:
        """Return active provider name, available provider list, and health status."""
        active_p = self.get_provider()
        health = await active_p.health_check() if hasattr(active_p, "health_check") else {"healthy": True}
        return {
            "active_provider": self.get_active_provider_name(),
            "available_providers": ProviderRegistry.list_providers(),
            "provider_status": health,
        }
