"""Utility for identifying role-based email accounts (info@, admin@, support@)."""

from typing import Set


class RoleAccountDetector:
    """Detector for common functional/role email account prefixes."""

    DEFAULT_ROLE_PREFIXES: Set[str] = {
        "admin", "administrator", "info", "sales", "support", "contact",
        "help", "billing", "jobs", "team", "marketing", "office", "hr",
        "careers", "inquiries", "hello", "media", "press", "security",
        "master", "postmaster", "webmaster", "hostmaster", "accounts",
        "service", "enquiries", "compliance", "privacy", "legal"
    }

    def __init__(self, custom_prefixes: Set[str] = None) -> None:
        """Initialize role detector with default or extended custom prefix set."""
        self._role_prefixes = set(self.DEFAULT_ROLE_PREFIXES)
        if custom_prefixes:
            self._role_prefixes.update(p.lower().strip() for p in custom_prefixes)

    def is_role_account(self, email_or_username: str) -> bool:
        """Check if local part or full email matches a known role account prefix."""
        if not email_or_username:
            return False

        clean = email_or_username.lower().strip()
        if "@" in clean:
            local_part = clean.split("@", 1)[0]
        else:
            local_part = clean

        return local_part in self._role_prefixes
