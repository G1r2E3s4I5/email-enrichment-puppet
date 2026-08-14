"""ProviderFactory instantiating configured email verification provider."""

from typing import Optional
from app.config.logging import logger
from app.config.settings import settings
from app.providers.email_verification.base import EmailVerificationProvider
from app.providers.email_verification.provider_registry import ProviderRegistry


class ProviderFactory:
    """Factory responsible for instantiating verification provider based on configuration."""

    def __init__(self, provider_name: Optional[str] = None) -> None:
        """Initialize factory with explicit provider name or fallback to settings."""
        if provider_name and str(provider_name).strip():
            self.active_provider_name = str(provider_name).strip().lower()
            logger.info(f"[ProviderFactory]: Explicit provider specified: '{self.active_provider_name}'")
            return

        configured_name = (
            getattr(settings, "EMAIL_VERIFICATION_PROVIDER", None)
            or getattr(settings, "EMAIL_VERIFICATION_MODE", None)
            or getattr(settings, "VERIFICATION_PROVIDER", None)
            or "composite"
        )
        self.active_provider_name = str(configured_name).strip().lower()
        logger.info(f"[ProviderFactory]: Selected verification provider key from settings: '{self.active_provider_name}'")

    def get_provider(self) -> EmailVerificationProvider:
        """Instantiate and return the configured EmailVerificationProvider instance."""
        provider_cls = ProviderRegistry.get_provider(self.active_provider_name)
        provider_instance = provider_cls()
        logger.info(f"Provider selected: '{provider_instance.get_provider_name()}'")
        return provider_instance

    @classmethod
    def create(cls, provider_name: Optional[str] = None) -> EmailVerificationProvider:
        """Convenience factory method instantiating provider."""
        factory = cls(provider_name=provider_name)
        return factory.get_provider()
