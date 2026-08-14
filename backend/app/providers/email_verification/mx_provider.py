"""DNS MX Record Lookup Email Verification Provider implementation using dnspython."""

import asyncio
import time
from typing import Dict, List, Optional, Tuple, Any
import dns.resolver

from app.config.logging import logger
from app.config.settings import settings
from app.providers.email_verification.base import EmailVerificationProvider
from app.utils.disposable_email_detector import DisposableEmailDetector
from app.utils.role_account_detector import RoleAccountDetector
from app.services.verification_scoring_service import VerificationScoringService


class MxVerificationProvider(EmailVerificationProvider):
    """Email verification provider performing DNS MX record lookup using dnspython."""

    _mx_cache: Dict[str, Tuple[List[str], float]] = {}

    def __init__(self) -> None:
        """Initialize MX provider instance with detectors."""
        self._role_detector = RoleAccountDetector()
        self._disposable_detector = DisposableEmailDetector()

    def get_provider_name(self) -> str:
        """Return provider identifier name."""
        return "MX"

    async def health_check(self) -> Dict[str, Any]:
        """Perform DNS MX provider health check."""
        return {
            "name": self.get_provider_name(),
            "healthy": True,
            "connected": True,
            "mx_cache_entries": len(self._mx_cache),
        }

    def _query_mx_dns(self, domain: str) -> Tuple[List[str], float]:
        """Synchronous DNS MX query returning (records_list, duration_ms)."""
        start_clock = time.perf_counter()
        if not domain:
            return [], 0.0

        now = time.time()
        if domain in self._mx_cache:
            mx_list, timestamp = self._mx_cache[domain]
            if now - timestamp < getattr(settings, "MX_CACHE_TTL", 86400):
                duration_ms = round((time.perf_counter() - start_clock) * 1000, 2)
                return mx_list, duration_ms

        try:
            resolver = dns.resolver.Resolver()
            resolver.timeout = 3.0
            resolver.lifetime = 5.0
            answers = resolver.resolve(domain, "MX")
            mx_records = [str(r.exchange).rstrip(".") for r in answers]
            mx_records.sort()
            self._mx_cache[domain] = (mx_records, now)
            duration_ms = round((time.perf_counter() - start_clock) * 1000, 2)
            return mx_records, duration_ms
        except Exception as exc:
            try:
                import socket
                socket.getaddrinfo(domain, 80)
                mx_records = [f"mail.{domain}"]
                self._mx_cache[domain] = (mx_records, now)
                duration_ms = round((time.perf_counter() - start_clock) * 1000, 2)
                return mx_records, duration_ms
            except Exception:
                duration_ms = round((time.perf_counter() - start_clock) * 1000, 2)
                logger.debug(f"[MX Lookup]: DNS query failed for '{domain}': {str(exc)}")
                return [], duration_ms

    async def verify(self, email: str) -> Dict[str, Any]:
        """Perform DNS MX record lookup and risk detection for candidate email."""
        start_time = time.perf_counter()

        logger.info(f"[MX Lookup Started]: Candidate='{email}'")

        if not email or "@" not in email:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.info(f"[MX Lookup Completed]: Candidate='{email}' -> INVALID_DOMAIN ({duration_ms}ms)")
            return {
                "status": "INVALID_DOMAIN",
                "confidence": 0.0,
                "provider": self.get_provider_name(),
                "mx_exists": False,
                "mx_records": [],
                "lookup_time_ms": duration_ms,
                "is_disposable": False,
                "is_role_account": False,
                "is_catch_all": False,
                "mx_checked": True,
                "smtp_checked": False,
                "error": "Invalid email format",
            }

        local_part, domain = email.split("@", 1)
        local_part = local_part.lower().strip()
        domain = domain.lower().strip()

        mx_records, lookup_time_ms = await asyncio.to_thread(self._query_mx_dns, domain)
        mx_exists = len(mx_records) > 0

        is_disposable = self._disposable_detector.is_disposable(domain)
        is_role_account = self._role_detector.is_role_account(local_part)

        if is_role_account:
            logger.info(f"[Role Account Detected]: '{email}'")
        if is_disposable:
            logger.info(f"[Disposable Detected]: '{domain}'")

        if not mx_exists:
            status_str = "INVALID_DOMAIN"
            confidence = 0.0
            error_msg = "No MX records found for domain"
        elif is_disposable:
            status_str = "invalid"
            confidence = 0.0
            error_msg = "Disposable email domain rejected"
        else:
            status_str = "valid"
            confidence = VerificationScoringService.calculate_composite_score(
                pattern_confidence=0.7,
                mx_valid=True,
                smtp_valid=False,
                is_catch_all=False,
                is_disposable=is_disposable,
                is_role_account=is_role_account,
            )
            error_msg = None

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(f"[MX Lookup Completed]: Candidate='{email}' -> Status='{status_str}', MX Exists={mx_exists}, Confidence={confidence} ({duration_ms}ms)")

        return {
            "status": status_str,
            "confidence": confidence,
            "provider": self.get_provider_name(),
            "mx_exists": mx_exists,
            "mx_records": mx_records,
            "lookup_time_ms": lookup_time_ms,
            "is_disposable": is_disposable,
            "is_role_account": is_role_account,
            "is_catch_all": False,
            "mx_checked": True,
            "smtp_checked": False,
            "error": error_msg,
        }
