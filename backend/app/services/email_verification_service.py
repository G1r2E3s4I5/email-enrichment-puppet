"""Service layer orchestrating email verification through provider-agnostic framework."""

import time
from typing import Dict, List, Optional, Any

from app.config.logging import logger
from app.providers.email_verification.provider_factory import ProviderFactory
from app.providers.email_verification.provider_registry import ProviderRegistry
from app.schemas.email_verification import EmailVerificationResponse, VerificationProviderHealthResponse
from app.services.verification_provider_service import VerificationProviderService


class EmailVerificationService:
    """Production service layer managing email deliverability verification delegating to configured providers."""

    def __init__(self, provider: Optional[Any] = None) -> None:
        """Initialize service with injected verification provider implementation or default VerificationProviderService."""
        self._provider_service = VerificationProviderService(provider=provider) if provider else VerificationProviderService()

    def get_active_provider_name(self) -> str:
        """Return the active provider's human-readable identifier."""
        return self._provider_service.get_active_provider_name()

    def get_supported_providers(self) -> List[str]:
        """Return list of supported provider configuration keys."""
        return ProviderRegistry.list_providers()

    async def verify_email(self, email: str, pattern_confidence: Optional[float] = None) -> EmailVerificationResponse:
        """Execute single email verification through the active provider."""
        return await self._provider_service.verify_email(email, pattern_confidence=pattern_confidence)

    async def verify_emails_batch(
        self,
        emails: List[str],
        batch_size: Optional[int] = None,
        max_concurrency: Optional[int] = None,
    ) -> List[EmailVerificationResponse]:
        """Batch verify candidate email addresses through active provider in parallel."""
        return await self._provider_service.verify_emails_batch(
            emails=emails,
            batch_size=batch_size,
            max_concurrency=max_concurrency,
        )

    async def get_active_provider_health(self) -> VerificationProviderHealthResponse:
        """Perform health check on the active verification provider."""
        provider = self._provider_service.get_provider()
        provider_name = self.get_active_provider_name()
        try:
            health_dict = await provider.health_check() if hasattr(provider, "health_check") else {"healthy": True}
            return VerificationProviderHealthResponse(
                provider=health_dict.get("name", provider_name),
                status="healthy" if health_dict.get("healthy", True) else "unhealthy",
                connected=health_dict.get("connected", True),
                details=health_dict,
            )
        except Exception as exc:
            logger.warning(f"Health check failed for provider '{provider_name}': {str(exc)}")
            return VerificationProviderHealthResponse(
                provider=provider_name,
                status="unreachable",
                connected=False,
                details={"error": str(exc)},
            )
