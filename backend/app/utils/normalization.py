"""Company name normalization utilities for consistent indexing and caching."""

import re
import string


# Common company name typo corrections dictionary
COMMON_COMPANY_TYPOS = {
    "micrsoft": "microsoft",
    "microsof": "microsoft",
    "micosoft": "microsoft",
    "amazn": "amazon",
    "amzon": "amazon",
    "gooogle": "google",
    "gogle": "google",
    "facbook": "meta",
    "facebk": "meta",
    "convegeniusai": "convegenius ai",
    "convegenius": "convegenius ai",
    "convigenius": "convegenius ai",
    "immagnify": "immagnify innovations",
    "immagnifyinnovations": "immagnify innovations",
}


def normalize_company_name(name: str) -> str:
    """Normalize company name string for consistent caching and lookup with typo correction."""
    if not name:
        return ""

    # Step 1: Strip outer whitespace & lowercase
    normalized = name.strip().lower()

    # Step 2: Collapse multiple spaces into single space
    normalized = re.sub(r"\s+", " ", normalized)

    # Step 3: Remove leading and trailing non-alphanumeric punctuation/symbols
    normalized = re.sub(r"^[^\w]+|[^\w]+$", "", normalized)

    # Step 4: Auto-correct known typos / aliases
    if normalized in COMMON_COMPANY_TYPOS:
        normalized = COMMON_COMPANY_TYPOS[normalized]

    return normalized

