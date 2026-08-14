"""Mock Email Verification Provider implementation for development and testing."""

import re
import asyncio
from typing import Dict, List, Any
from app.config.logging import logger
from app.providers.email_verification.base import EmailVerificationProvider


DISPOSABLE_DOMAINS = {
    "mailinator.com",
    "tempmail.com",
    "10minutemail.com",
    "guerrillamail.com",
    "trashmail.com",
    "dispostable.com",
    "yopmail.com",
}

ROLE_ACCOUNT_PREFIXES = {
    "admin",
    "info",
    "support",
    "sales",
    "contact",
    "hello",
    "help",
    "billing",
    "jobs",
    "team",
    "postmaster",
    "hostmaster",
}

EMAIL_SYNTAX_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)


class MockProvider(EmailVerificationProvider):
    """Mock implementation returning deterministic verification results for development and testing."""

    def get_provider_name(self) -> str:
        """Return unique provider slug name."""
        return "Mock"

    async def health_check(self) -> Dict[str, Any]:
        """Perform simulated health check for Mock provider."""
        return {
            "name": self.get_provider_name(),
            "healthy": True,
            "connected": True,
            "mode": "development",
            "simulated_latency_ms": 0,
        }

    async def verify(self, email: str, **kwargs) -> Dict[str, Any]:
        """Deterministically verify deliverability status of candidate email address."""
        if not email or not email.strip():
            return {
                "status": "invalid",
                "confidence": 0.0,
                "provider": self.get_provider_name(),
                "is_disposable": False,
                "is_role_account": False,
                "is_catch_all": False,
                "mx_checked": False,
                "smtp_checked": False,
                "error": "Email address must not be empty",
            }

        clean_email = email.strip().lower()

        # Step 1: Syntax Validation
        if not EMAIL_SYNTAX_REGEX.match(clean_email):
            logger.debug(f"[Mock Provider]: Invalid email syntax for '{clean_email}'")
            return {
                "status": "invalid",
                "confidence": 0.0,
                "provider": self.get_provider_name(),
                "is_disposable": False,
                "is_role_account": False,
                "is_catch_all": False,
                "mx_checked": False,
                "smtp_checked": False,
                "error": "Invalid email syntax format",
            }

        parts = clean_email.split("@")
        local_part = parts[0]
        domain_part = parts[1]

        # Step 2: Disposable Domain Detection
        if domain_part in DISPOSABLE_DOMAINS:
            logger.debug(f"[Mock Provider]: Disposable domain detected for '{clean_email}'")
            return {
                "status": "invalid",
                "confidence": 10.0,
                "provider": self.get_provider_name(),
                "is_disposable": True,
                "is_role_account": False,
                "is_catch_all": False,
                "mx_checked": True,
                "smtp_checked": False,
                "error": None,
            }

        # Step 3: Role Account Detection
        if local_part in ROLE_ACCOUNT_PREFIXES:
            logger.debug(f"[Mock Provider]: Role account detected for '{clean_email}'")
            return {
                "status": "valid",
                "confidence": 80.0,
                "provider": self.get_provider_name(),
                "is_disposable": False,
                "is_role_account": True,
                "is_catch_all": False,
                "mx_checked": True,
                "smtp_checked": True,
                "error": None,
            }

        # Step 4: Catch-All Domain Detection
        if "catchall" in domain_part or "catch-all" in domain_part:
            logger.debug(f"[Mock Provider]: Catch-all domain detected for '{clean_email}'")
            return {
                "status": "catch_all",
                "confidence": 60.0,
                "provider": self.get_provider_name(),
                "is_disposable": False,
                "is_role_account": False,
                "is_catch_all": True,
                "mx_checked": True,
                "smtp_checked": True,
                "error": None,
            }

        # Step 5: Standard Valid Deliverable Email
        logger.debug(f"[Mock Provider]: Valid email verified for '{clean_email}'")
        return {
            "status": "valid",
            "confidence": 96.0,
            "provider": self.get_provider_name(),
            "is_disposable": False,
            "is_role_account": False,
            "is_catch_all": False,
            "mx_checked": True,
            "smtp_checked": True,
            "error": None,
        }

    async def verify_batch(self, emails: List[str]) -> List[Dict[str, Any]]:
        """Verify candidate email addresses concurrently in batch."""
        if not emails:
            return []

        tasks = [self.verify(email) for email in emails]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        formatted_results: List[Dict[str, Any]] = []
        for email, res in zip(emails, results):
            if isinstance(res, Exception):
                formatted_results.append(
                    {
                        "status": "unknown",
                        "confidence": 0.0,
                        "provider": self.get_provider_name(),
                        "is_disposable": False,
                        "is_role_account": False,
                        "is_catch_all": False,
                        "mx_checked": False,
                        "smtp_checked": False,
                        "error": str(res),
                    }
                )
            else:
                formatted_results.append(res)

        return formatted_results
