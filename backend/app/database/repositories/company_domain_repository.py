"""Repository layer for company_domains database operations with resilient memory caching, connection outage protection, and negative lookup caching."""

from datetime import datetime, timezone
from typing import Optional, Dict, List
from uuid import UUID, uuid4
from supabase import Client

from app.config.logging import logger
from app.core.exceptions import (
    DatabaseException,
    DuplicateRecordException,
    EntityNotFoundException,
    ValidationException,
)
from app.database.supabase import get_supabase_client
from app.schemas.company_domain import (
    CompanyDomainCreate,
    CompanyDomainResponse,
    CompanyDomainUpdate,
)
from app.utils.normalization import normalize_company_name


class CompanyDomainRepository:
    """Data access repository for managing company_domains cache records with DB and resilient memory caching."""

    TABLE_NAME = "company_domains"
    _shared_memory_cache: Dict[str, CompanyDomainResponse] = {}

    def __init__(self, client: Optional[Client] = None) -> None:
        """Initialize repository with injected Supabase database client or fallback singleton."""
        self._client = client

    @property
    def client(self) -> Client:
        """Access database client instance or raise exception if unconfigured."""
        if self._client is not None:
            return self._client
        client = get_supabase_client()
        if client is None:
            raise DatabaseException("Supabase database client is not configured or uninitialized")
        return client

    def _get_client(self) -> Optional[Client]:
        """Retrieve injected client or fallback singleton."""
        if self._client is not None:
            return self._client
        try:
            return get_supabase_client()
        except Exception:
            return None

    def record_negative_lookup(self, company_name: str) -> CompanyDomainResponse:
        """Record a negative lookup cache entry ('NOT_FOUND') for an unresolvable company."""
        normalized = normalize_company_name(company_name)
        if not normalized:
            return CompanyDomainResponse(
                id=uuid4(),
                company_name=company_name,
                normalized_name="",
                domain="NOT_FOUND",
                provider="NegativeCache",
                confidence=0.0,
                created_at=datetime.now(timezone.utc),
                updated_at=None,
            )

        now = datetime.now(timezone.utc)
        mem_entry = CompanyDomainResponse(
            id=uuid4(),
            company_name=company_name.strip(),
            normalized_name=normalized,
            domain="NOT_FOUND",
            provider="NegativeCache",
            confidence=0.0,
            created_at=now,
            updated_at=now,
        )
        self._shared_memory_cache[normalized] = mem_entry
        logger.debug(f"[Negative Cache Stored]: Recorded unresolvable company '{normalized}' as NOT_FOUND")
        return mem_entry

    def get_by_normalized_name(self, normalized_name: str) -> Optional[CompanyDomainResponse]:
        """Retrieve cached domain mapping by normalized company name from DB or resilient memory cache."""
        if not normalized_name:
            raise ValidationException("Normalized name must not be empty")

        query_name = normalize_company_name(normalized_name)
        mem_hit = self._shared_memory_cache.get(query_name)

        client = self._get_client()
        if client is None:
            return mem_hit

        try:
            response = client.table(self.TABLE_NAME).select("*").eq("normalized_name", query_name).execute()

            if not response.data or len(response.data) == 0:
                return mem_hit

            record = response.data[0]
            db_res = CompanyDomainResponse.model_validate(record)
            self._shared_memory_cache[query_name] = db_res
            return db_res
        except ValidationException:
            raise
        except Exception as exc:
            err_str = str(exc)
            if "getaddrinfo failed" in err_str or "connection" in err_str.lower() or "timeout" in err_str.lower() or "PGRST" in err_str:
                logger.warning(f"Domain cache DB query warning for '{normalized_name}': {err_str}. Returning memory cache if available.")
                return mem_hit
            raise DatabaseException(f"Database query failed: {err_str}", details={"error": err_str})

    def get_by_domain(self, domain: str) -> Optional[CompanyDomainResponse]:
        """Retrieve cached company domain record by domain string."""
        if not domain:
            return None
        clean_d = domain.strip().lower()
        for res in self._shared_memory_cache.values():
            if res.domain.lower() == clean_d:
                return res

        client = self._get_client()
        if client is None:
            return None

        try:
            response = client.table(self.TABLE_NAME).select("*").eq("domain", clean_d).execute()
            if response.data and len(response.data) > 0:
                res = CompanyDomainResponse.model_validate(response.data[0])
                self._shared_memory_cache[res.normalized_name] = res
                return res
            return None
        except Exception:
            return None

    def update_preferred_pattern(self, domain: str, pattern_name: str, confidence: float = 95.0) -> bool:
        """Update Organization Memory preferred_pattern for a given domain."""
        if not domain or not pattern_name:
            return False

        clean_d = domain.strip().lower()
        now_iso = datetime.now(timezone.utc).isoformat()
        now_dt = datetime.now(timezone.utc)

        # 1. Update memory cache
        for norm, entry in list(self._shared_memory_cache.items()):
            if entry.domain.lower() == clean_d:
                updated_dict = entry.model_dump()
                updated_dict["preferred_pattern"] = pattern_name
                updated_dict["pattern_confidence"] = confidence
                updated_dict["pattern_last_verified_at"] = now_dt
                self._shared_memory_cache[norm] = CompanyDomainResponse.model_validate(updated_dict)

        client = self._get_client()
        if client is None:
            logger.info(f"[Organization Memory Cached]: Learned pattern '{pattern_name}' for domain '{clean_d}'")
            return True

        try:
            client.table(self.TABLE_NAME).update(
                {
                    "preferred_pattern": pattern_name,
                    "pattern_confidence": confidence,
                    "pattern_last_verified_at": now_iso,
                    "updated_at": now_iso,
                }
            ).eq("domain", clean_d).execute()
            logger.info(f"[Organization Memory Saved]: Persisted preferred_pattern '{pattern_name}' for domain '{clean_d}'")
            return True
        except Exception as exc:
            logger.warning(f"Failed to update preferred_pattern for domain '{clean_d}' in DB: {str(exc)}")
            return True

    def get_by_normalized_names_batch(self, normalized_names: List[str]) -> Dict[str, CompanyDomainResponse]:
        """Bulk retrieve cached domain mappings for multiple normalized company names in a single query."""
        if not normalized_names:
            return {}

        clean_names = list(set(normalize_company_name(n) for n in normalized_names if n and n.strip()))
        if not clean_names:
            return {}

        results: Dict[str, CompanyDomainResponse] = {}

        # 1. Check memory store
        for name in clean_names:
            if name in self._shared_memory_cache:
                results[name] = self._shared_memory_cache[name]

        missing_names = [n for n in clean_names if n not in results]
        if not missing_names:
            return results

        client = self._get_client()
        if client is None:
            return results

        # 2. Bulk query DB for missing names
        try:
            response = client.table(self.TABLE_NAME).select("*").in_("normalized_name", missing_names).execute()

            if response.data:
                for record in response.data:
                    res = CompanyDomainResponse.model_validate(record)
                    self._shared_memory_cache[res.normalized_name] = res
                    results[res.normalized_name] = res
            return results
        except Exception as exc:
            logger.warning(f"Bulk domain cache DB query warning: {str(exc)}. Returning memory cache results.")
            return results

    def get_by_id(self, domain_id: UUID) -> Optional[CompanyDomainResponse]:
        """Retrieve cached domain mapping by primary key UUID."""
        if not domain_id:
            raise ValidationException("Domain ID must be provided")

        for c in self._shared_memory_cache.values():
            if c.id == domain_id:
                return c

        client = self._get_client()
        if client is None:
            return None

        try:
            response = client.table(self.TABLE_NAME).select("*").eq("id", str(domain_id)).execute()

            if not response.data or len(response.data) == 0:
                return None

            return CompanyDomainResponse.model_validate(response.data[0])
        except ValidationException:
            raise
        except Exception as exc:
            err_str = str(exc)
            if "getaddrinfo failed" in err_str or "connection" in err_str.lower() or "timeout" in err_str.lower() or "PGRST" in err_str:
                logger.warning(f"Error querying company domain by ID '{domain_id}': {err_str}")
                return None
            raise DatabaseException(f"Database query failed: {err_str}", details={"error": err_str})

    def insert_cache(self, data: CompanyDomainCreate) -> CompanyDomainResponse:
        """Insert a new company domain cache record into database or memory store."""
        normalized = data.normalized_name or normalize_company_name(data.company_name)
        if not normalized:
            raise ValidationException("Cannot normalize company name to a valid string")

        existing = self.get_by_normalized_name(normalized)
        if existing:
            raise DuplicateRecordException(
                message=f"Company domain cache entry already exists for normalized name '{normalized}'",
                details={"normalized_name": normalized},
            )

        now = datetime.now(timezone.utc)
        mem_entry = CompanyDomainResponse(
            id=uuid4(),
            company_name=data.company_name.strip(),
            normalized_name=normalized,
            domain=data.domain.strip().lower(),
            provider=data.provider.strip(),
            confidence=data.confidence,
            created_at=now,
            updated_at=now,
        )
        self._shared_memory_cache[normalized] = mem_entry

        client = self._get_client()
        if client is None:
            return mem_entry

        payload = {
            "company_name": data.company_name.strip(),
            "normalized_name": normalized,
            "domain": data.domain.strip().lower(),
            "provider": data.provider.strip(),
            "confidence": data.confidence,
        }

        try:
            response = client.table(self.TABLE_NAME).insert(payload).execute()
            if response.data and len(response.data) > 0:
                saved = CompanyDomainResponse.model_validate(response.data[0])
                self._shared_memory_cache[normalized] = saved
                return saved
            return mem_entry
        except (DuplicateRecordException, ValidationException):
            raise
        except Exception as exc:
            error_str = str(exc).lower()
            if "duplicate key" in error_str or "unique constraint" in error_str or "23505" in error_str:
                raise DuplicateRecordException(
                    message=f"Company domain cache entry already exists for '{normalized}'",
                    details={"error": str(exc)},
                )
            if "getaddrinfo failed" in error_str or "connection" in error_str or "timeout" in error_str or "pgrst" in error_str:
                logger.warning(f"Domain cache DB insert warning for '{normalized}': {str(exc)}. Saved in memory cache.")
                return mem_entry
            raise DatabaseException(f"Failed to insert cache record: {str(exc)}", details={"error": str(exc)})

    def update_cache(self, domain_id: UUID, data: CompanyDomainUpdate) -> CompanyDomainResponse:
        """Update existing company domain cache record fields."""
        if not domain_id:
            raise ValidationException("Domain ID must be provided")

        update_payload = data.model_dump(exclude_unset=True)
        if not update_payload:
            raise ValidationException("No fields provided for update")

        if "company_name" in update_payload and "normalized_name" not in update_payload:
            update_payload["normalized_name"] = normalize_company_name(update_payload["company_name"])

        update_payload["updated_at"] = datetime.now(timezone.utc).isoformat()

        client = self._get_client()
        if client is None:
            for norm, entry in self._shared_memory_cache.items():
                if entry.id == domain_id:
                    updated_dict = entry.model_dump()
                    updated_dict.update(update_payload)
                    res = CompanyDomainResponse.model_validate(updated_dict)
                    self._shared_memory_cache[norm] = res
                    return res
            raise EntityNotFoundException(f"Company domain cache record '{domain_id}' not found")

        try:
            response = (
                client.table(self.TABLE_NAME)
                .update(update_payload)
                .eq("id", str(domain_id))
                .execute()
            )

            if not response.data or len(response.data) == 0:
                raise EntityNotFoundException(
                    message=f"Company domain cache record with ID '{domain_id}' not found",
                    details={"domain_id": str(domain_id)},
                )

            return CompanyDomainResponse.model_validate(response.data[0])
        except (EntityNotFoundException, ValidationException):
            raise
        except Exception as exc:
            logger.warning(f"Failed to update company domain cache entry '{domain_id}': {str(exc)}")
            raise EntityNotFoundException(f"Company domain cache record '{domain_id}' not found")

    def delete_cache(self, domain_id: UUID) -> bool:
        """Delete company domain cache record by UUID."""
        if not domain_id:
            raise ValidationException("Domain ID must be provided")

        client = self._get_client()
        if client is None:
            to_del = [norm for norm, entry in self._shared_memory_cache.items() if entry.id == domain_id]
            if not to_del:
                raise EntityNotFoundException(f"Company domain cache record '{domain_id}' not found")
            for norm in to_del:
                del self._shared_memory_cache[norm]
            return True

        try:
            response = client.table(self.TABLE_NAME).delete().eq("id", str(domain_id)).execute()
            if not response.data or len(response.data) == 0:
                raise EntityNotFoundException(
                    message=f"Company domain cache record with ID '{domain_id}' not found",
                    details={"domain_id": str(domain_id)},
                )
            to_del = [norm for norm, entry in self._shared_memory_cache.items() if entry.id == domain_id]
            for norm in to_del:
                del self._shared_memory_cache[norm]
            return True
        except EntityNotFoundException:
            raise
        except Exception as exc:
            logger.warning(f"Failed to delete company domain cache entry '{domain_id}': {str(exc)}")
            return True
