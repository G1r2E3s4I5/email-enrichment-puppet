"""Database Migration Runner and Table Verification Tool."""

import os
import sys
from typing import List, Dict, Any
import httpx

# Add project root directory to python path
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from app.config.settings import settings
from app.config.logging import logger


REQUIRED_TABLES = [
    "company_domains",
    "domain_resolution_logs",
    "processing_jobs",
    "job_results",
    "generated_email_candidates",
]


def check_table_status() -> Dict[str, bool]:
    """Check existence of required tables via Supabase REST API."""
    url = settings.SUPABASE_URL
    key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY

    if not url or not key:
        logger.warning("Supabase credentials missing.")
        return {t: False for t in REQUIRED_TABLES}

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }

    status_map: Dict[str, bool] = {}
    for table in REQUIRED_TABLES:
        target_url = f"{url.rstrip('/')}/rest/v1/{table}?select=*&limit=1"
        try:
            resp = httpx.get(target_url, headers=headers, timeout=5.0)
            if resp.status_code == 200:
                status_map[table] = True
            elif resp.status_code == 404 and "PGRST205" in resp.text:
                status_map[table] = False
            else:
                status_map[table] = False
        except Exception as exc:
            logger.error(f"Failed to check table '{table}': {str(exc)}")
            status_map[table] = False

    return status_map


def get_migration_files() -> List[str]:
    """Return sorted list of migration SQL file paths."""
    migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")
    if not os.path.exists(migrations_dir):
        return []

    files = sorted([f for f in os.listdir(migrations_dir) if f.endswith(".sql")])
    return [os.path.join(migrations_dir, f) for f in files]


def main() -> None:
    """Main migration runner entrypoint."""
    logger.info("=== Phase 2 Database Table Verification ===")
    table_status = check_table_status()

    for table, exists in table_status.items():
        status_str = "✅ EXISTS" if exists else "❌ MISSING"
        logger.info(f"Table '{table}': {status_str}")

    migration_files = get_migration_files()
    logger.info(f"Found {len(migration_files)} migration files in app/database/migrations:")
    for path in migration_files:
        logger.info(f" - {os.path.basename(path)}")

    missing_tables = [t for t, exists in table_status.items() if not exists]
    if missing_tables:
        logger.warning(f"Missing tables in Supabase database: {missing_tables}")
        logger.info("\nPlease execute the migration SQL scripts in the Supabase SQL Editor if unapplied:\n")
        for path in migration_files:
            logger.info(f"--- File: {os.path.basename(path)} ---")
            with open(path, "r", encoding="utf-8") as f:
                logger.info(f.read())
            logger.info("-----------------------------------------\n")
    else:
        logger.info("🎉 All required tables exist in Supabase database!")


if __name__ == "__main__":
    main()
