"""Provider Health Service aggregating real-time provider circuit breaker metrics and status."""

from typing import Dict, List, Any, Optional

from app.core.circuit_breaker import ProviderCircuitBreaker
from app.providers.brandfetch_provider import BrandfetchDomainProvider
from app.providers.tavily_provider import TavilyDomainProvider
from app.providers.serpapi_provider import SerpApiDomainProvider
from app.providers.openai_provider import OpenAIDomainProvider
from app.providers.email_verification.provider_factory import ProviderFactory


class ProviderHealthService:
    """Service retrieving operational health, latency metrics, and circuit breaker status across all providers."""

    def __init__(self) -> None:
        """Initialize provider health service."""
        pass

    def get_registered_circuit_breakers(self) -> Dict[str, ProviderCircuitBreaker]:
        """Collect all active provider circuit breakers."""
        breakers: Dict[str, ProviderCircuitBreaker] = {}

        # Domain Resolution Providers
        providers = [
            BrandfetchDomainProvider(),
            TavilyDomainProvider(),
            SerpApiDomainProvider(),
            OpenAIDomainProvider(),
        ]
        for p in providers:
            cb = p.get_circuit_breaker()
            breakers[cb.name] = cb

        # Verification Provider Factory instance
        verification_provider = ProviderFactory.create()
        if hasattr(verification_provider, "get_circuit_breaker"):
            cb = verification_provider.get_circuit_breaker()
            breakers[cb.name] = cb

        return breakers

    def get_all_provider_health(self) -> List[Dict[str, Any]]:
        """Return telemetry dictionaries for all active providers."""
        breakers = self.get_registered_circuit_breakers()
        return [cb.get_health_telemetry() for cb in breakers.values()]

    def get_provider_health(self, provider_name: str) -> Optional[Dict[str, Any]]:
        """Return operational health telemetry for a specific provider by name."""
        breakers = self.get_registered_circuit_breakers()
        for name, cb in breakers.items():
            if name.lower() == provider_name.lower():
                return cb.get_health_telemetry()
        return None
