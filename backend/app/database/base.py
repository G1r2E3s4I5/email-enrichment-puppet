"""Base abstract database connection interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseDatabaseClient(ABC):
    """Abstract interface defining contract for database client wrappers."""

    @abstractmethod
    def get_client(self) -> Any:
        """Return initialized raw client object."""
        pass

    @abstractmethod
    async def check_health(self) -> Dict[str, Any]:
        """Perform database health check ping."""
        pass
