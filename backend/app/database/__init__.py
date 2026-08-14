"""Database integration package for Email Enrichment Tool."""

from app.database.supabase import get_supabase_client, check_supabase_health

__all__ = ["get_supabase_client", "check_supabase_health"]
