"""Cache validation service managing TTL expiration, cache versioning, and duplicate verification."""

from datetime import datetime, timezone
from typing import Optional, Any

from app.config.logging import logger


class CacheValidationService:
    """Service evaluating cache record freshness, expiration thresholds, and versioning standards."""

    CACHE_VERSION = "v1.0"
    DEFAULT_TTL_DAYS = 30

    def get_cache_version(self) -> str:
        """Return the current system cache schema version identifier."""
        return self.CACHE_VERSION

    def is_expired(self, created_at: Optional[datetime], ttl_days: int = DEFAULT_TTL_DAYS) -> bool:
        """Check if a cached domain record has exceeded its Time-To-Live (TTL) threshold."""
        if not created_at:
            return False

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        age_days = (now - created_at).days

        if age_days >= ttl_days:
            logger.info(f"[Cache Expiration]: Cache entry created at {created_at.isoformat()} is expired ({age_days} days old >= TTL {ttl_days} days)")
            return True
        return False

    def check_duplicate(self, existing_domain: Optional[str], candidate_domain: str) -> bool:
        """Determine if candidate domain already exists in cache."""
        if not existing_domain or not candidate_domain:
            return False
        return existing_domain.strip().lower() == candidate_domain.strip().lower()
