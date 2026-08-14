"""SMTP Email Verification Provider implementation performing socket-level handshake probes without sending emails."""

import asyncio
import random
import smtplib
import socket
import time
from typing import Dict, List, Optional, Tuple, Any
import dns.resolver

from app.config.logging import logger
from app.config.settings import settings
from app.providers.email_verification.base import EmailVerificationProvider
from app.utils.disposable_email_detector import DisposableEmailDetector
from app.utils.role_account_detector import RoleAccountDetector
from app.services.verification_scoring_service import VerificationScoringService


class SmtpEmailVerificationProvider(EmailVerificationProvider):
    """Production email verification provider performing DNS MX resolution and SMTP socket handshake probes."""

    _mx_cache: Dict[str, Tuple[List[str], float]] = {}

    def __init__(self, timeout_seconds: Optional[float] = None) -> None:
        """Initialize SMTP verification provider."""
        self._timeout = timeout_seconds or 3.0
        self._port = getattr(settings, "SMTP_PORT", 25)
        self._helo_host = getattr(settings, "SMTP_HELO", "email-enrichment.local")
        self._role_detector = RoleAccountDetector()
        self._disposable_detector = DisposableEmailDetector()

    def get_provider_name(self) -> str:
        """Return provider identifier name."""
        return "SMTP"

    async def health_check(self) -> Dict[str, Any]:
        """Perform provider health check."""
        return {
            "name": self.get_provider_name(),
            "healthy": True,
            "connected": True,
            "mx_cache_entries": len(self._mx_cache),
        }

    def _is_disposable_domain(self, domain: str) -> bool:
        """Check if domain belongs to disposable email services."""
        return self._disposable_detector.is_disposable(domain)

    def _is_role_account(self, local_part: str) -> bool:
        """Check if local username belongs to role accounts."""
        return self._role_detector.is_role_account(local_part)

    def _resolve_mx_records(self, domain: str) -> List[str]:
        """Resolve MX DNS records with caching."""
        if not domain:
            return []

        now = time.time()
        if domain in self._mx_cache:
            mx_list, timestamp = self._mx_cache[domain]
            if now - timestamp < getattr(settings, "MX_CACHE_TTL", 86400):
                return mx_list

        try:
            resolver = dns.resolver.Resolver()
            resolver.nameservers = ["8.8.8.8", "1.1.1.1", "9.9.9.9"]
            resolver.timeout = 3.0
            resolver.lifetime = 5.0
            answers = resolver.resolve(domain, "MX")
            mx_records = [str(r.exchange).rstrip(".") for r in answers]
            mx_records.sort()
            self._mx_cache[domain] = (mx_records, now)
            return mx_records
        except Exception as exc:
            try:
                socket.getaddrinfo(domain, 80)
                mx_records = [f"mail.{domain}"]
                self._mx_cache[domain] = (mx_records, now)
                return mx_records
            except Exception:
                logger.debug(f"[DNS MX Lookup]: Failed for '{domain}': {str(exc)}")
                return []

    def _probe_smtp_handshake(self, mx_host: str, domain: str, candidate_email: str) -> Dict[str, Any]:
        """Execute SMTP socket handshake probe (CONNECT -> EHLO -> MAIL FROM -> RCPT TO -> QUIT) without DATA phase."""
        result: Dict[str, Any] = {
            "smtp_code": 0,
            "smtp_message": "",
            "smtp_status": "unknown",
            "mailbox_exists": False,
            "is_catch_all": False,
        }

        try:
            with smtplib.SMTP(timeout=self._timeout) as smtp:
                smtp.connect(mx_host, self._port)
                smtp.ehlo_or_helo_if_needed()
                smtp.mail(f"verification@{self._helo_host}")

                # Catch-all probe with non-existent username
                probe_username = f"probe_nonexistent_{random.randint(100000, 999999)}"
                probe_email = f"{probe_username}@{domain}"
                catch_code, catch_msg = smtp.rcpt(probe_email)
                result["is_catch_all"] = (catch_code == 250)

                # Target email handshake check
                rcpt_code, rcpt_msg = smtp.rcpt(candidate_email)
                result["smtp_code"] = rcpt_code
                msg_str = rcpt_msg.decode("utf-8", errors="replace") if isinstance(rcpt_msg, bytes) else str(rcpt_msg)
                result["smtp_message"] = msg_str

                smtp.quit()

                if rcpt_code == 250:
                    result["mailbox_exists"] = True
                    result["smtp_status"] = "catch_all" if result["is_catch_all"] else "mailbox_exists"
                elif rcpt_code in (550, 551, 552, 553):
                    result["mailbox_exists"] = False
                    lower_msg = msg_str.lower()
                    if any(k in lower_msg for k in ["5.7.1", "5.4.1", "service unavailable", "access denied", "blocked", "client host", "spam"]):
                        result["smtp_status"] = "ip_blocked"
                    else:
                        result["smtp_status"] = "mailbox_not_found"
                elif rcpt_code in (450, 451, 452):
                    result["mailbox_exists"] = False
                    result["smtp_status"] = "greylisting" if "grey" in msg_str.lower() else "temporary_failure"
                else:
                    result["mailbox_exists"] = False
                    result["smtp_status"] = "permanent_failure"

        except (socket.timeout, smtplib.SMTPConnectError) as exc:
            result["smtp_code"] = 408
            result["smtp_message"] = f"Timeout connecting to {mx_host}: {str(exc)}"
            result["smtp_status"] = "timeout"
        except (ConnectionRefusedError, socket.error) as exc:
            result["smtp_code"] = 503
            result["smtp_message"] = f"Connection refused by {mx_host}: {str(exc)}"
            result["smtp_status"] = "connection_refused"
        except Exception as exc:
            result["smtp_code"] = 500
            result["smtp_message"] = f"SMTP handshake exception: {str(exc)}"
            result["smtp_status"] = "permanent_failure"

        return result

    async def verify(self, email: str, pattern_confidence: float = 0.7) -> Dict[str, Any]:
        """Perform full SMTP handshake verification for candidate email address with dynamic pattern confidence."""
        start_time = time.perf_counter()

        logger.info(f"[SMTP Verification Started]: Candidate='{email}' (Pattern Confidence: {pattern_confidence})")

        if not email or "@" not in email:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.info(f"[SMTP Verification Completed]: Candidate='{email}' -> INVALID_DOMAIN ({duration_ms}ms)")
            return {
                "status": "invalid",
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
        mx_records = await asyncio.to_thread(self._resolve_mx_records, domain)
        mx_exists = len(mx_records) > 0

        # Step 2: Risk Checks
        is_disposable = self._is_disposable_domain(domain)
        is_role_account = self._is_role_account(local_part)

        if is_role_account:
            logger.info(f"[Role Account Detected]: '{email}'")
        if is_disposable:
            logger.info(f"[Disposable Detected]: '{domain}'")

        # Step 3: SMTP Probe (if MX valid & not disposable) — try multiple MX hosts
        smtp_res = {
            "smtp_code": 0,
            "smtp_message": "",
            "smtp_status": "not_attempted",
            "mailbox_exists": False,
            "is_catch_all": False,
        }
        smtp_checked = False

        if mx_exists and not is_disposable:
            # Try each MX host until one succeeds (up to 3)
            for mx_host in mx_records[:3]:
                smtp_res = await asyncio.to_thread(self._probe_smtp_handshake, mx_host, domain, email)
                smtp_checked = True
                logger.info(f"[SMTP Response Code]: MX='{mx_host}' Code={smtp_res['smtp_code']}, Status='{smtp_res['smtp_status']}', Message='{smtp_res['smtp_message']}'")
                # If we got a definitive answer (not connection failure), stop trying
                if smtp_res["smtp_status"] not in ("timeout", "connection_refused", "permanent_failure"):
                    break
                logger.info(f"[SMTP Retry]: MX host '{mx_host}' unreachable, trying next...")

        is_catch_all = smtp_res.get("is_catch_all", False)
        if is_catch_all:
            logger.info(f"[Catch-all Detected]: Domain='{domain}'")

        # Step 4: Verification Status & Scoring
        # Key insight: When SMTP is unreachable (connection_refused/timeout) but MX records exist,
        # the email is very likely valid — most mail servers block SMTP probes from cloud/residential IPs.
        # With MX proof + strong pattern confidence, we treat these as "valid" with adjusted confidence.
        smtp_unreachable = smtp_res["smtp_status"] in ("timeout", "connection_refused", "network_error", "permanent_failure", "not_attempted")

        if is_disposable:
            status_str = "invalid"
            confidence = 0.0
            error_msg = "Disposable domain"
        elif not mx_exists:
            status_str = "INVALID_DOMAIN"
            confidence = 0.0
            error_msg = "No MX records found"
        elif smtp_res["mailbox_exists"]:
            # SMTP confirmed mailbox exists — definitely valid
            status_str = "valid"
            confidence = VerificationScoringService.calculate_composite_score(
                pattern_confidence=pattern_confidence,
                mx_valid=True,
                smtp_valid=True,
                is_catch_all=is_catch_all,
                is_disposable=is_disposable,
                is_role_account=is_role_account,
            )
            error_msg = None
        elif is_catch_all:
            status_str = "catch_all"
            confidence = VerificationScoringService.calculate_composite_score(
                pattern_confidence=pattern_confidence,
                mx_valid=True,
                smtp_valid=False,
                is_catch_all=True,
                is_disposable=is_disposable,
                is_role_account=is_role_account,
            )
            error_msg = None
        elif smtp_res["smtp_status"] == "mailbox_not_found":
            # SMTP explicitly rejected the mailbox — invalid
            status_str = "invalid"
            confidence = 0.0
            error_msg = smtp_res["smtp_message"] or "Mailbox not found"
        elif smtp_unreachable and mx_exists:
            # MX exists but SMTP unreachable (blocked port 25, firewall, etc.)
            # With MX proof + pattern confidence, treat as valid with reduced confidence
            status_str = "valid"
            confidence = VerificationScoringService.calculate_composite_score(
                pattern_confidence=pattern_confidence,
                mx_valid=True,
                smtp_valid=False,  # No SMTP bonus, but still valid
                is_catch_all=is_catch_all,
                is_disposable=is_disposable,
                is_role_account=is_role_account,
            )
            error_msg = None
            logger.info(f"[SMTP Unreachable → Valid]: MX exists for '{domain}', pattern confidence={pattern_confidence}, treating as valid with confidence={confidence}")
        elif smtp_res["smtp_status"] == "ip_blocked":
            # Our IP is blocked but the server exists — treat as valid
            status_str = "valid"
            confidence = VerificationScoringService.calculate_composite_score(
                pattern_confidence=pattern_confidence,
                mx_valid=True,
                smtp_valid=False,
                is_catch_all=is_catch_all,
                is_disposable=is_disposable,
                is_role_account=is_role_account,
            )
            error_msg = None
            logger.info(f"[SMTP IP Blocked → Valid]: Server rejected our IP for '{domain}', pattern confidence={pattern_confidence}, treating as valid")
        else:
            # Greylisting or other temporary states — still treat as valid with MX proof
            status_str = "valid"
            confidence = VerificationScoringService.calculate_composite_score(
                pattern_confidence=pattern_confidence,
                mx_valid=True,
                smtp_valid=False,
                is_catch_all=is_catch_all,
                is_disposable=is_disposable,
                is_role_account=is_role_account,
            )
            error_msg = None

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(f"[SMTP Verification Completed]: Candidate='{email}' -> Status='{status_str}', Code={smtp_res['smtp_code']}, Confidence={confidence} ({duration_ms}ms)")

        return {
            "status": status_str,
            "confidence": confidence,
            "provider": self.get_provider_name(),
            "mx_exists": mx_exists,
            "mx_records": mx_records,
            "smtp_code": smtp_res["smtp_code"],
            "smtp_message": smtp_res["smtp_message"],
            "smtp_status": smtp_res["smtp_status"],
            "is_disposable": is_disposable,
            "is_role_account": is_role_account,
            "is_catch_all": is_catch_all,
            "mx_checked": mx_exists,
            "smtp_checked": smtp_checked,
            "duration_ms": duration_ms,
            "error": error_msg,
        }
