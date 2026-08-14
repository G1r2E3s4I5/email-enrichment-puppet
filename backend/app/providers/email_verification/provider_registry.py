"""ProviderRegistry for managing email verification provider class registrations."""

from typing import Dict, List, Type, Optional
from app.config.logging import logger
from app.providers.email_verification.base import EmailVerificationProvider


class ProviderRegistry:
    """Registry responsible for registering and looking up email verification providers."""

    _registry: Dict[str, Type[EmailVerificationProvider]] = {}
    _initialized: bool = False

    @classmethod
    def _ensure_defaults(cls) -> None:
        """Lazily register default providers to prevent circular import loops."""
        if cls._initialized:
            return
        from app.providers.email_verification.mock_provider import MockProvider
        from app.providers.email_verification.mx_provider import MxVerificationProvider
        from app.providers.email_verification.smtp_provider import SmtpEmailVerificationProvider
        from app.providers.email_verification.composite_provider import CompositeVerificationProvider

        cls._registry["mock"] = MockProvider
        cls._registry["mx"] = MxVerificationProvider
        cls._registry["smtp"] = SmtpEmailVerificationProvider
        cls._registry["composite"] = CompositeVerificationProvider
        cls._registry["neverbounce"] = MockProvider
        cls._registry["zerobounce"] = MockProvider
        cls._registry["hunter"] = MockProvider
        cls._registry["abstract"] = MockProvider
        cls._registry["kickbox"] = MockProvider
        cls._initialized = True

    @classmethod
    def register_provider(
        cls,
        name: str,
        provider_cls: Type[EmailVerificationProvider],
    ) -> None:
        """Register a provider class under a slug identifier name."""
        cls._ensure_defaults()
        clean_name = name.strip().lower()
        cls._registry[clean_name] = provider_cls
        logger.info(f"Registered verification provider '{clean_name}' -> {provider_cls.__name__}")

    @classmethod
    def get_provider(cls, name: str) -> Type[EmailVerificationProvider]:
        """Lookup provider class by slug name or raise ValidationException."""
        cls._ensure_defaults()
        clean_name = (name or "").strip().lower()
        if clean_name not in cls._registry:
            from app.providers.email_verification.mock_provider import MockProvider
            logger.warning(
                f"Requested provider '{clean_name}' not found in registry. "
                f"Available: {list(cls._registry.keys())}. Falling back to 'mock'."
            )
            return cls._registry.get("mock", MockProvider)
        return cls._registry[clean_name]

    @classmethod
    def list_providers(cls) -> List[str]:
        """Return list of all registered provider slug names."""
        cls._ensure_defaults()
        return sorted(list(cls._registry.keys()))
