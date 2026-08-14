"""Utility for identifying disposable/temporary email provider domains."""

from typing import Set, Optional


class DisposableEmailDetector:
    """Detector maintaining a local blacklist of disposable temporary email domains."""

    DEFAULT_DISPOSABLE_DOMAINS: Set[str] = {
        "mailinator.com", "10minutemail.com", "tempmail.com", "guerrillamail.com",
        "throwawaymail.com", "maildrop.cc", "yopmail.com", "trashmail.com",
        "sharklasers.com", "dispostable.com", "getairmail.com", "fakeinbox.com",
        "tmpmail.org", "generator.email", "disposable.com", "nada.ltd",
        "getnada.com", "temp-mail.org", "boun.cr", "mailnesia.com"
    }

    def __init__(self, custom_domains: Optional[Set[str]] = None) -> None:
        """Initialize disposable detector with default or extended custom domain set."""
        self._disposable_domains = set(self.DEFAULT_DISPOSABLE_DOMAINS)
        if custom_domains:
            self._disposable_domains.update(d.lower().strip() for d in custom_domains)

    def is_disposable(self, email_or_domain: str) -> bool:
        """Check if domain or email address belongs to a disposable mail service."""
        if not email_or_domain:
            return False

        clean = email_or_domain.lower().strip()
        if "@" in clean:
            domain = clean.split("@", 1)[1]
        else:
            domain = clean

        return domain in self._disposable_domains
