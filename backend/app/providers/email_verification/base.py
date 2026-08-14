"""Abstract Base Class interface for email verification providers in Phase 4.3/4.4 architecture."""

from abc import ABC, abstractmethod
from typing import Dict, List, Any


class EmailVerificationProvider(ABC):
    """Abstract interface defining the contract for all email verification providers."""

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the unique human-readable provider name (e.g. 'Mock', 'NeverBounce', 'ZeroBounce', 'Hunter', 'Abstract')."""
        pass

    @abstractmethod
    async def verify(self, email: str) -> Dict[str, Any]:
        """Verify deliverability and validity status of a candidate email address.

        Returns dict containing:
        - status: str (e.g. 'valid', 'invalid', 'catch_all', 'unknown')
        - confidence: float (0.0 to 100.0)
        - provider: str
        - is_disposable: bool
        - is_role_account: bool
        - is_catch_all: bool
        - mx_checked: bool
        - smtp_checked: bool
        - error: Optional[str]
        """
        pass

    async def verify_batch(self, emails: List[str]) -> List[Dict[str, Any]]:
        """Verify a list of candidate email addresses in batch concurrently.

        Providers with native batch API endpoints should override this method.
        Default implementation executes concurrent single-email verification with error isolation.
        """
        import asyncio

        async def _safe_verify(email_addr: str) -> Dict[str, Any]:
            try:
                return await self.verify(email_addr)
            except Exception as exc:
                return {
                    "status": "unknown",
                    "confidence": 0.0,
                    "provider": self.get_provider_name(),
                    "is_disposable": False,
                    "is_role_account": False,
                    "is_catch_all": False,
                    "mx_checked": True,
                    "smtp_checked": False,
                    "error": str(exc),
                }

        return list(await asyncio.gather(*[_safe_verify(e) for e in emails]))

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Perform provider connectivity and health status check."""
        pass
