"""Abstract Domain Resolution Provider Interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict
from app.schemas.domain_provider import DomainResolutionResult


class DomainProvider(ABC):
    """Abstract interface defining contract for company domain resolution services."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier name."""
        pass

    @abstractmethod
    async def resolve_domain(self, company_name: str) -> DomainResolutionResult:
        """Resolve a company name into its official corporate website domain."""
        pass

    @abstractmethod
    async def check_health(self) -> Dict[str, Any]:
        """Check API availability or connectivity for this provider."""
        pass
