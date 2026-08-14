"""Confidence recalculation service computing quality scores (0-100) for domain resolutions."""

from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Optional, Dict

from app.config.logging import logger
from app.services.domain_validation_service import KNOWN_ENTERPRISE_BRANDS
from app.utils.normalization import normalize_company_name


PROVIDER_BASE_SCORES: Dict[str, float] = {
    "Brandfetch": 30.0,
    "SerpAPI": 20.0,
    "Cache": 30.0,
    "Manual": 35.0,
    "PlaceholderFallback": 5.0,
}


class ConfidenceRecalculationService:
    """Service recalculating domain resolution confidence score on a 0-100 quality scale."""

    def calculate_confidence(
        self,
        company_name: str,
        domain: str,
        provider: str = "Brandfetch",
        dns_resolved: bool = True,
        created_at: Optional[datetime] = None,
        provider_agreement: bool = False,
    ) -> float:
        """Calculate quality confidence score between 0.0 and 100.0 based on deterministic quality factors."""
        if not domain or not domain.strip() or not company_name:
            return 0.0

        clean_domain = domain.strip().lower()
        norm_company = normalize_company_name(company_name)
        parts = clean_domain.split(".")
        sld = parts[0] if parts else ""

        score = 0.0

        # 1. Provider Baseline Weight (Max 30 pts)
        base_provider_score = PROVIDER_BASE_SCORES.get(provider, 20.0)
        score += base_provider_score

        # 2. String Similarity Ratio (Max 30 pts)
        clean_company_no_space = norm_company.replace(" ", "").replace("-", "")
        clean_sld_no_space = sld.replace("-", "")
        similarity_ratio = SequenceMatcher(None, clean_company_no_space, clean_sld_no_space).ratio()
        score += similarity_ratio * 30.0

        # 3. Known Enterprise Brand or Exact SLD / Primary Word Match (Max 25 pts)
        primary_word = norm_company.split()[0] if norm_company else ""
        if norm_company in KNOWN_ENTERPRISE_BRANDS:
            if KNOWN_ENTERPRISE_BRANDS[norm_company] == clean_domain:
                score += 25.0
        elif (
            clean_company_no_space == clean_sld_no_space
            or primary_word == clean_sld_no_space
            or similarity_ratio >= 0.80
        ):
            score += 25.0

        # 4. Domain Validity & DNS Status (Max 15 pts)
        if len(parts) >= 2 and parts[-1].isalpha():
            score += 10.0
        if dns_resolved:
            score += 5.0

        # 5. Provider Agreement Bonus (Max 5 pts)
        if provider_agreement:
            score += 5.0

        # 6. Cache Age Decay (Deduction for aged cache entries > 30 days)
        if created_at:
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            days_old = max(0, (now - created_at).days)
            if days_old > 30:
                decay = min(20.0, (days_old - 30) * 0.5)
                score -= decay

        final_score = round(max(0.0, min(100.0, score)), 2)
        logger.debug(
            f"[Confidence Updated]: '{company_name}' -> '{clean_domain}' (Provider: {provider}, Score: {final_score}/100)"
        )
        return final_score
