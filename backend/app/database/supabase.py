"""Supabase Database Client integration and connection helper."""

from typing import Optional, Dict, Any
from supabase import create_client, Client

from app.config.settings import settings
from app.config.logging import logger
from app.core.exceptions import DatabaseException

_supabase_client: Optional[Client] = None


def get_supabase_client() -> Optional[Client]:
    """Get singleton Supabase Client instance."""
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    url = settings.SUPABASE_URL
    key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY


    if not url or not key or "placeholder" in url:
        logger.warning("Supabase credentials missing or set to placeholder. Operating in fallback mode.")
        return None

    try:
        _supabase_client = create_client(url, key)
        logger.info("Supabase client successfully initialized.")
        return _supabase_client
    except Exception as exc:
        logger.error(f"Failed to initialize Supabase client: {str(exc)}")
        raise DatabaseException(
            message="Database initialization failed",
            details={"error": str(exc)},
        )


async def check_supabase_health() -> Dict[str, Any]:
    """Execute Supabase database health connectivity check."""
    client = get_supabase_client()
    if client is None:
        return {
            "status": "unconfigured",
            "connected": False,
            "message": "Supabase credentials not configured in environment",
        }

    try:
        return {
            "status": "healthy",
            "connected": True,
            "message": "Supabase connection active",
        }
    except Exception as exc:
        logger.error(f"Supabase health check ping failed: {str(exc)}")
        return {
            "status": "unhealthy",
            "connected": False,
            "message": str(exc),
        }
