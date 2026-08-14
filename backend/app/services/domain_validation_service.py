"""Domain validation service enforcing syntax, TLD, DNS resolution, and brand protection rules."""

import asyncio
import re
import socket
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from app.config.logging import logger
from app.utils.normalization import normalize_company_name


# Known Enterprise Brand to Canonical Corporate Domain mapping
KNOWN_ENTERPRISE_BRANDS: Dict[str, str] = {
    "ibm": "ibm.com",
    "international business machines": "ibm.com",
    "microsoft": "microsoft.com",
    "google": "google.com",
    "alphabet": "google.com",
    "apple": "apple.com",
    "amazon": "amazon.com",
    "meta": "meta.com",
    "facebook": "meta.com",
    "netflix": "netflix.com",
    "tesla": "tesla.com",
    "oracle": "oracle.com",
    "salesforce": "salesforce.com",
    "adobe": "adobe.com",
    "nvidia": "nvidia.com",
    "intel": "intel.com",
    "cisco": "cisco.com",
    "uber": "uber.com",
    "airbnb": "airbnb.com",
    "spotify": "spotify.com",
    "stripe": "stripe.com",
    "shopify": "shopify.com",
    "hubspot": "hubspot.com",
    "zendesk": "zendesk.com",
    "atlassian": "atlassian.com",
    "slack": "slack.com",
    "github": "github.com",
    "gitlab": "gitlab.com",
    "twilio": "twilio.com",
    "datadog": "datadoghq.com",
    "snowflake": "snowflake.com",
    "square": "squareup.com",
    "paypal": "paypal.com",
    "convegenius": "convegenius.ai",
    "convegenius ai": "convegenius.ai",
    "convigenius": "convegenius.ai",
    "immagnify": "imagnifyinnovations.com",
    "immagnify innovations": "imagnifyinnovations.com",
    "imagnify innovations": "imagnifyinnovations.com",
}

# Generic domain parking or suspicious keywords
PARKED_DOMAIN_KEYWORDS = {
    "domainfor-sale",
    "buythisdomain",
    "parked-content",
    "hugedomains",
    "sedo.com",
    "afternic",
    "dan.com",
    "namecheap-parking",
    "godaddy.com",
    "underconstruction",
    "domainmarket",
    "example.com",
}


@dataclass
class DomainValidationResult:
    """Result container for domain validation evaluations."""

    is_valid: bool
    domain: str
    company_name: str
    syntax_valid: bool
    tld_valid: bool
    dns_resolved: bool
    is_suspicious: bool
    rejection_reason: Optional[str] = None


class DomainValidationService:
    """Service validating resolved domains for syntax, public TLD, DNS resolution, and brand spoofing."""

    DOMAIN_REGEX = re.compile(
        r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$"
    )

    # In-memory DNS resolution cache: domain -> (resolved: bool, timestamp: float)
    # Avoids redundant DNS lookups for the same domain within a job batch
    _dns_cache: Dict[str, Tuple[bool, float]] = {}
    _DNS_CACHE_TTL: float = 300.0  # 5 minute TTL for DNS cache entries

    @classmethod
    def clear_dns_cache(cls) -> None:
        """Clear the in-memory DNS resolution cache."""
        cls._dns_cache.clear()

    def validate_domain_syntax(self, domain: str) -> bool:
        """Validate string against standard RFC domain name structure."""
        if not domain or len(domain) > 253:
            return False
        return bool(self.DOMAIN_REGEX.match(domain.strip().lower()))

    def validate_public_suffix(self, domain: str) -> bool:
        """Verify that the domain has a valid top-level domain suffix."""
        if not self.validate_domain_syntax(domain):
            return False
        parts = domain.strip().lower().split(".")
        tld = parts[-1]
        return len(tld) >= 2 and tld.isalpha()

    async def check_dns_resolution(self, domain: str, timeout: float = 1.5) -> bool:
        """Asynchronously verify DNS host/MX resolution for domain using robust public DNS resolvers.
        
        Uses an in-memory cache to avoid redundant DNS lookups for the same domain
        within a job batch. Cache entries expire after _DNS_CACHE_TTL seconds.
        """
        clean_domain = domain.strip().lower()

        # Check in-memory DNS cache first
        cached = self._dns_cache.get(clean_domain)
        if cached is not None:
            resolved, cached_at = cached
            if (time.time() - cached_at) < self._DNS_CACHE_TTL:
                logger.debug(f"[DNS Cache Hit]: '{clean_domain}' -> {resolved}")
                return resolved
            else:
                # Expired entry, remove it
                del self._dns_cache[clean_domain]
        
        def _query_dns():
            import dns.resolver
            resolver = dns.resolver.Resolver()
            resolver.nameservers = ["8.8.8.8", "1.1.1.1", "8.8.4.4"]
            resolver.lifetime = timeout
            resolver.timeout = timeout
            
            # Check MX records first, fallback to A/AAAA
            for qtype in ("MX", "A", "AAAA"):
                try:
                    ans = resolver.resolve(clean_domain, qtype)
                    if len(ans) > 0:
                        return True
                except Exception:
                    pass
            return False

        try:
            result = await asyncio.to_thread(_query_dns)
            # Cache the result
            self._dns_cache[clean_domain] = (result, time.time())
            return result
        except Exception as exc:
            logger.debug(f"DNS resolution check failed for '{clean_domain}': {str(exc)}")
            # Cache negative result too to avoid repeated timeouts
            self._dns_cache[clean_domain] = (False, time.time())
            return False

    def calculate_domain_similarity(self, company_name: str, domain: str) -> float:
        """Calculate token/string similarity between company name and candidate domain SLD (0.0 to 1.0)."""
        if not company_name or not domain:
            return 0.0

        norm_company = normalize_company_name(company_name)
        clean_comp_tokens = set(re.findall(r"[a-z0-9]+", norm_company))

        clean_domain = domain.strip().lower()
        parts = clean_domain.split(".")
        sld = parts[0] if parts else ""
        domain_tokens = set(re.findall(r"[a-z0-9]+", sld))

        # Check token intersection or direct substring inclusion
        comp_compact = "".join(clean_comp_tokens)
        if not comp_compact or not sld:
            return 0.0

        if sld in comp_compact or comp_compact in sld:
            return 0.95

        overlap = clean_comp_tokens.intersection(domain_tokens)
        if overlap:
            return 0.85

        # Character set overlap similarity
        set_comp = set(comp_compact)
        set_sld = set(sld)
        char_sim = len(set_comp.intersection(set_sld)) / max(len(set_comp), len(set_sld))
        return round(char_sim, 2)

    def is_suspicious_domain(self, company_name: str, domain: str) -> Tuple[bool, Optional[str]]:
        """Identify suspicious domains, brand mismatches, and low similarity domain patterns."""
        clean_domain = domain.strip().lower()
        norm_company = normalize_company_name(company_name)

        # 1. Parked / For Sale Keyword Detection
        for kw in PARKED_DOMAIN_KEYWORDS:
            if kw in clean_domain:
                return True, f"Domain '{clean_domain}' contains parked/suspicious keyword '{kw}'"

        # 2. Known Enterprise Brand Mismatch Check
        if norm_company in KNOWN_ENTERPRISE_BRANDS:
            canonical = KNOWN_ENTERPRISE_BRANDS[norm_company]
            if clean_domain != canonical:
                return (
                    True,
                    f"Brand mismatch: '{company_name}' is a known enterprise brand requiring '{canonical}', "
                    f"got '{clean_domain}'",
                )

        # 3. Domain Similarity Score Check
        sim_score = self.calculate_domain_similarity(company_name, clean_domain)
        if sim_score < 0.35:
            return (
                True,
                f"Low brand domain similarity ({sim_score}): '{clean_domain}' does not match company '{company_name}'",
            )

        # 4. Short Company Name Suffix Spoofing
        parts = clean_domain.split(".")
        sld = parts[0] if parts else ""
        if len(norm_company) <= 4 and norm_company.isalpha():
            if sld.startswith(norm_company) and len(sld) > len(norm_company) + 2:
                return (
                    True,
                    f"Suspicious suffix addition: '{sld}' extends short brand name '{norm_company}'",
                )

        return False, None

    async def validate_resolved_domain(
        self,
        company_name: str,
        domain: str,
        verify_dns: bool = True,
    ) -> DomainValidationResult:
        """Perform comprehensive domain validation pipeline prior to caching."""
        if not domain or not domain.strip():
            logger.warning(f"[Domain Rejected]: Empty domain provided for company '{company_name}'")
            return DomainValidationResult(
                is_valid=False,
                domain=domain or "",
                company_name=company_name,
                syntax_valid=False,
                tld_valid=False,
                dns_resolved=False,
                is_suspicious=False,
                rejection_reason="Domain must not be empty",
            )

        clean_domain = domain.strip().lower()

        # Step 1: Syntax Validation
        syntax_ok = self.validate_domain_syntax(clean_domain)
        if not syntax_ok:
            logger.warning(f"[Domain Rejected]: Invalid domain syntax for '{clean_domain}'")
            return DomainValidationResult(
                is_valid=False,
                domain=clean_domain,
                company_name=company_name,
                syntax_valid=False,
                tld_valid=False,
                dns_resolved=False,
                is_suspicious=False,
                rejection_reason=f"Invalid domain syntax '{clean_domain}'",
            )

        # Step 2: Public Suffix Validation
        tld_ok = self.validate_public_suffix(clean_domain)
        if not tld_ok:
            logger.warning(f"[Domain Rejected]: Invalid public suffix TLD for '{clean_domain}'")
            return DomainValidationResult(
                is_valid=False,
                domain=clean_domain,
                company_name=company_name,
                syntax_valid=True,
                tld_valid=False,
                dns_resolved=False,
                is_suspicious=False,
                rejection_reason=f"Invalid public TLD suffix in '{clean_domain}'",
            )

        # Step 3: Suspicious Domain / Brand Protection Check
        suspicious, susp_reason = self.is_suspicious_domain(company_name, clean_domain)
        if suspicious:
            logger.warning(f"[Domain Rejected]: {susp_reason}")
            return DomainValidationResult(
                is_valid=False,
                domain=clean_domain,
                company_name=company_name,
                syntax_valid=True,
                tld_valid=True,
                dns_resolved=False,
                is_suspicious=True,
                rejection_reason=susp_reason,
            )

        # Step 4: DNS Resolution Verification
        dns_ok = True
        if verify_dns:
            dns_ok = await self.check_dns_resolution(clean_domain)
            if not dns_ok:
                logger.warning(f"[Domain Rejected]: DNS host lookup failed for '{clean_domain}' (Non-existent domain in DNS)")
                return DomainValidationResult(
                    is_valid=False,
                    domain=clean_domain,
                    company_name=company_name,
                    syntax_valid=True,
                    tld_valid=True,
                    dns_resolved=False,
                    is_suspicious=False,
                    rejection_reason=f"DNS resolution lookup failed for '{clean_domain}'",
                )

        logger.info(f"Domain validation PASSED for '{company_name}' -> '{clean_domain}' (DNS: {dns_ok})")
        return DomainValidationResult(
            is_valid=True,
            domain=clean_domain,
            company_name=company_name,
            syntax_valid=True,
            tld_valid=True,
            dns_resolved=dns_ok,
            is_suspicious=False,
            rejection_reason=None,
        )
