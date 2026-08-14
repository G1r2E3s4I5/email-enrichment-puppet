"""Email formatting and sanitization utilities."""

import re
from typing import Optional


def sanitize_domain(domain_raw: Optional[str]) -> str:
    """Clean and normalize domain name string.

    Removes http://, https://, www., trailing slashes, spaces, and lowercases.
    Example:
        ' https://WWW.OpenAI.com/ ' -> 'openai.com'
    """
    if not domain_raw:
        return ""
    d = domain_raw.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    d = d.split("/")[0].split("?")[0].strip()
    return d


def sanitize_local_part(local_part_raw: str) -> str:
    """Clean email local-part username string.

    Rules:
    - Replace consecutive dots with a single dot ('..' -> '.')
    - Replace consecutive separators with single separator
    - Remove leading/trailing dots, hyphens, and underscores
    - Keep only alphanumeric, dots, hyphens, and underscores

    Example:
        '.sam..altman_' -> 'sam.altman'
    """
    if not local_part_raw:
        return ""
    lp = local_part_raw.strip().lower()
    # Remove characters not allowed in standard corporate email local part
    lp = re.sub(r"[^a-z0-9._-]", "", lp)
    # Collapse duplicate dots
    lp = re.sub(r"\.+", ".", lp)
    # Collapse duplicate underscores or hyphens
    lp = re.sub(r"_+", "_", lp)
    lp = re.sub(r"-+", "-", lp)
    # Strip leading/trailing non-alphanumeric chars
    lp = lp.strip("._-")
    return lp


def format_email_address(local_part: str, domain: str) -> Optional[str]:
    """Combine sanitized local part and domain into a valid candidate email address.

    Returns None if either local part or domain is invalid/empty.

    Example:
        format_email_address('sam.altman', 'openai.com') -> 'sam.altman@openai.com'
    """
    clean_lp = sanitize_local_part(local_part)
    clean_dom = sanitize_domain(domain)

    if not clean_lp or not clean_dom or "." not in clean_dom:
        return None

    return f"{clean_lp}@{clean_dom}"
