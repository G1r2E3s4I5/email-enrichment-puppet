"""Database injection dependency for FastAPI route handlers."""

from typing import Optional
from supabase import Client
from app.database.supabase import get_supabase_client


def get_db() -> Optional[Client]:
    """Dependency provider for Supabase database client instance."""
    return get_supabase_client()
