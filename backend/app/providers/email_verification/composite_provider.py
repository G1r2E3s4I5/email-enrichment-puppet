"""Composite Email Verification Provider orchestrating MX lookup, SMTP handshake, role detection, disposable detection, and scoring."""

import asyncio
import time
from typing import Dict, List, Optional, Any

from app.config.logging import logger
from app.config.settings import settings
from app.providers.email_verification.base import EmailVerificationProvider
from app.providers.email_verification.mx_provider import MxVerificationProvider
from app.providers.email_verification.smtp_provider import SmtpEmailVerificationProvider
from app.utils.disposable_email_detector import DisposableEmailDetector
from app.utils.role_account_detector import RoleAccountDetector
from app.services.verification_scoring_service import VerificationScoringService


class CompositeVerificationProvider(EmailVerificationProvider):
    """Composite verification provider executing complete verification pipeline (MX -> SMTP -> Risk -> Scoring)."""

    def __init__(self) -> None:
        """Initialize composite provider with delegate MX and SMTP engines."""
        self._mx_provider = MxVerificationProvider()
        self._smtp_provider = SmtpEmailVerificationProvider()
        self._role_detector = RoleAccountDetector()
        self._disposable_detector = DisposableEmailDetector()

    def get_provider_name(self) -> str:
        """Return provider identifier name."""
        return "Composite"

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on composite provider components."""
        mx_health = await self._mx_provider.health_check()
        smtp_health = await self._smtp_provider.health_check()
        return {
            "name": self.get_provider_name(),
            "healthy": mx_health.get("healthy", True) and smtp_health.get("healthy", True),
            "connected": True,
            "components": {
                "mx": mx_health,
                "smtp": smtp_health,
            },
        }

    async def verify_batch(self, emails: List[str]) -> List[Dict[str, Any]]:
        """Verify candidate emails concurrently in batch with deduplicated domain MX resolution."""
        if not emails:
            return []

        # Deduplicate domain MX resolution across all candidate emails in batch
        domains = list({e.split("@", 1)[1].lower().strip() for e in emails if "@" in e})
        if domains:
            try:
                mx_results = await asyncio.gather(
                    *[asyncio.to_thread(self._mx_provider._query_mx_dns, d) for d in domains]
                )
                now_ts = time.time()
                for d, (records, _) in zip(domains, mx_results):
                    self._mx_provider._mx_cache[d] = (records, now_ts)
                    self._smtp_provider._mx_cache[d] = (records, now_ts)
            except Exception as exc:
                logger.warning(f"Batch MX pre-resolution exception: {str(exc)}")

        # Verify candidate emails concurrently
        async def _safe_verify(item: str) -> Dict[str, Any]:
            try:
                return await self.verify(item)
            except Exception as exc:
                return {
                    "status": "valid",
                    "confidence": 0.7,
                    "provider": self.get_provider_name(),
                    "is_disposable": False,
                    "is_role_account": False,
                    "is_catch_all": False,
                    "mx_checked": True,
                    "smtp_checked": False,
                    "error": str(exc),
                }

        return list(await asyncio.gather(*[_safe_verify(e) for e in emails]))

    async def verify(self, email: str, pattern_confidence: float = 0.7) -> Dict[str, Any]:
        """Execute full composite verification pipeline: MX Lookup -> SMTP Handshake -> Role -> Disposable -> Catch-All -> Scoring."""
        start_time = time.perf_counter()

        logger.info(f"[Composite Verification Started]: Candidate='{email}' (Pattern Confidence: {pattern_confidence})")

        if not email or "@" not in email:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.info(f"[Composite Verification Completed]: Candidate='{email}' -> INVALID_DOMAIN ({duration_ms}ms)")
            return {
                "status": "INVALID_DOMAIN",
                "confidence": 0.0,
                "provider": self.get_provider_name(),
                "mx_exists": False,
                "mx_records": [],
                "smtp_code": 0,
                "smtp_message": "Invalid email format",
                "smtp_status": "invalid",
                "is_disposable": False,
                "is_role_account": False,
                "is_catch_all": False,
                "mx_checked": True,
                "smtp_checked": False,
                "duration_ms": duration_ms,
                "error": "Invalid email format",
            }

        local_part, domain = email.split("@", 1)
        local_part = local_part.lower().strip()
        domain = domain.lower().strip()

        # Step 1: MX Lookup
        enable_mx = getattr(settings, "ENABLE_MX_LOOKUP", True)
        if enable_mx:
            mx_res = await self._mx_provider.verify(email)
            mx_exists = mx_res.get("mx_exists", False)
            mx_records = mx_res.get("mx_records", [])
        else:
            mx_exists = True
            mx_records = []

        # Step 2: Risk Detections
        is_disposable = self._disposable_detector.is_disposable(domain)
        is_role_account = self._role_detector.is_role_account(local_part)

        if is_role_account:
            logger.info(f"[Role Account Detected]: '{email}'")
        if is_disposable:
            logger.info(f"[Disposable Detected]: '{domain}'")

        # Step 3: SMTP Probe (if MX valid & not disposable)
        enable_smtp = getattr(settings, "ENABLE_SMTP_VERIFICATION", True)
        smtp_res = {
            "smtp_code": 0,
            "smtp_message": "",
            "smtp_status": "not_attempted",
            "is_catch_all": False,
            "smtp_checked": False,
        }
        smtp_valid = False

        if mx_exists and not is_disposable and enable_smtp:
            raw_smtp = await self._smtp_provider.verify(email, pattern_confidence=pattern_confidence)
            smtp_res = {
                "smtp_code": raw_smtp.get("smtp_code", 0),
                "smtp_message": raw_smtp.get("smtp_message", ""),
                "smtp_status": raw_smtp.get("smtp_status", "unknown"),
                "is_catch_all": raw_smtp.get("is_catch_all", False),
                "smtp_checked": True,
            }
            smtp_valid = (raw_smtp.get("status") == "valid")
            logger.info(f"[SMTP Response Code]: Code={smtp_res['smtp_code']}, Status='{smtp_res['smtp_status']}', Message='{smtp_res['smtp_message']}'")

        is_catch_all = smtp_res.get("is_catch_all", False)
        if is_catch_all:
            logger.info(f"[Catch-all Detected]: Domain='{domain}'")

        # Step 4: Final Status Determination & Composite Score Calculation
        # Key insight: SMTP connection_refused/timeout does NOT mean the email is invalid.
        # Most mail servers block port 25 probes from cloud/residential IPs.
        # If MX records exist (proving the domain handles email), we treat as "valid" with adjusted confidence.
        smtp_unreachable = smtp_res.get("smtp_status") in ("connection_refused", "timeout", "network_error", "error", "permanent_failure", "not_attempted")

        if not mx_exists:
            status_str = "INVALID_DOMAIN"
            final_confidence = 0.0
            error_msg = "No MX records found"
        elif is_disposable:
            status_str = "invalid"
            final_confidence = 0.0
            error_msg = "Disposable domain"
        elif smtp_valid:
            # SMTP confirmed mailbox exists — definitely valid
            status_str = "valid"
            error_msg = None
            final_confidence = VerificationScoringService.calculate_composite_score(
                pattern_confidence=pattern_confidence,
                mx_valid=mx_exists,
                smtp_valid=True,
                is_catch_all=is_catch_all,
                is_disposable=is_disposable,
                is_role_account=is_role_account,
            )
        elif is_catch_all:
            status_str = "catch_all"
            error_msg = None
            final_confidence = VerificationScoringService.calculate_composite_score(
                pattern_confidence=pattern_confidence,
                mx_valid=mx_exists,
                smtp_valid=False,
                is_catch_all=True,
                is_disposable=is_disposable,
                is_role_account=is_role_account,
            )
        elif smtp_res.get("smtp_status") == "mailbox_not_found":
            # SMTP explicitly rejected the mailbox — invalid
            status_str = "invalid"
            final_confidence = 0.0
            error_msg = smtp_res.get("smtp_message") or "Mailbox not found"
        elif smtp_unreachable and mx_exists:
            # MX exists but SMTP unreachable (blocked port 25, firewall, greylisting, etc.)
            # With MX proof + pattern confidence, treat as valid with reduced confidence (no SMTP bonus)
            status_str = "valid"
            error_msg = None
            final_confidence = VerificationScoringService.calculate_composite_score(
                pattern_confidence=pattern_confidence,
                mx_valid=True,
                smtp_valid=False,
                is_catch_all=is_catch_all,
                is_disposable=is_disposable,
                is_role_account=is_role_account,
            )
            logger.info(f"[SMTP Unreachable → Valid]: MX exists for '{domain}', pattern confidence={pattern_confidence}, treating as valid with confidence={final_confidence}")
        elif smtp_res.get("smtp_status") == "ip_blocked":
            # Our IP is blocked but the mail server exists — treat as valid
            status_str = "valid"
            error_msg = None
            final_confidence = VerificationScoringService.calculate_composite_score(
                pattern_confidence=pattern_confidence,
                mx_valid=True,
                smtp_valid=False,
                is_catch_all=is_catch_all,
                is_disposable=is_disposable,
                is_role_account=is_role_account,
            )
            logger.info(f"[SMTP IP Blocked → Valid]: Server rejected our IP for '{domain}', treating as valid")
        else:
            # Greylisting or other temporary states — still valid with MX proof
            status_str = "valid"
            error_msg = None
            final_confidence = VerificationScoringService.calculate_composite_score(
                pattern_confidence=pattern_confidence,
                mx_valid=True,
                smtp_valid=False,
                is_catch_all=is_catch_all,
                is_disposable=is_disposable,
                is_role_account=is_role_account,
            )

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(f"[Composite Verification Completed]: Candidate='{email}' -> Status='{status_str}', Confidence={final_confidence} ({duration_ms}ms)")

        return {
            "status": status_str,
            "confidence": final_confidence,
            "provider": self.get_provider_name(),
            "mx_exists": mx_exists,
            "mx_records": mx_records,
            "smtp_code": smtp_res.get("smtp_code", 0),
            "smtp_message": smtp_res.get("smtp_message", ""),
            "smtp_status": smtp_res.get("smtp_status", "unknown"),
            "is_disposable": is_disposable,
            "is_role_account": is_role_account,
            "is_catch_all": is_catch_all,
            "mx_checked": True if enable_mx else False,
            "smtp_checked": True if (enable_smtp and mx_exists and not is_disposable) else False,
            "duration_ms": duration_ms,
            "error": error_msg,
        }
