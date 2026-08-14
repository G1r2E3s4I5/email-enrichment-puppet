"""String normalization utilities for name parsing and email candidate generation."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional


@dataclass
class NormalizedName:
    """Dataclass holding normalized name components and initials."""

    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    first_initial: str = ""
    last_initial: str = ""
    middle_initial: str = ""

    def __post_init__(self) -> None:
        """Derive initials if not explicitly provided."""
        if not self.first_initial and self.first_name:
            self.first_initial = self.first_name[0]
        if not self.last_initial and self.last_name:
            self.last_initial = self.last_name[0]
        if not self.middle_initial and self.middle_name:
            self.middle_initial = self.middle_name[0]


def remove_accents(text: str) -> str:
    """Strip accents and diacritics from string using NFKD normalization.

    Example:
        'José María' -> 'Jose Maria'
        'Müller' -> 'Muller'
        'François' -> 'Francois'
    """
    if not text:
        return ""
    nfkd_form = unicodedata.normalize("NFKD", text)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


def sanitize_name_token(token: str) -> str:
    """Clean name token to retain only lowercase alphanumeric characters.

    Strips apostrophes, hyphens, and punctuation.
    Example:
        "O'Connor" -> "oconnor"
        "Mary-Jane" -> "maryjane"
    """
    if not token:
        return ""
    no_accents = remove_accents(token)
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", no_accents)
    return cleaned.lower()


def normalize_name_input(
    first_name_raw: Optional[str],
    last_name_raw: Optional[str] = None,
) -> NormalizedName:
    """Normalize and parse raw first and last name inputs into NormalizedName object.

    Handles:
    - Single full-name strings (e.g., first_name_raw="John Doe", last_name_raw=None -> first="john", last="doe")
    - Uppercase, lowercase, mixed case
    - Accents/diacritics (e.g., 'José María' -> 'jose maria')
    - Extra whitespace and multi-word names
    - Apostrophes and hyphens (e.g. "O'Connor", "Jean-Luc")
    """
    fn_clean = remove_accents((first_name_raw or "").strip().lower())
    ln_clean = remove_accents((last_name_raw or "").strip().lower())

    fn_words = [w for w in re.split(r"\s+", fn_clean) if w]
    ln_words = [w for w in re.split(r"\s+", ln_clean) if w]

    middle_name: Optional[str] = None

    if not ln_words and len(fn_words) > 1:
        # Full name was supplied in single field (e.g. "John Doe" or "John Michael Doe")
        fn = sanitize_name_token(fn_words[0])
        ln = sanitize_name_token(fn_words[-1])
        if len(fn_words) > 2:
            middle_name = sanitize_name_token("".join(fn_words[1:-1]))
    else:
        if len(fn_words) > 1:
            fn = sanitize_name_token(fn_words[0])
            middle_name = sanitize_name_token("".join(fn_words[1:]))
        elif fn_words:
            fn = sanitize_name_token(fn_words[0])
        else:
            fn = ""

        if ln_words:
            ln = "".join(sanitize_name_token(w) for w in ln_words)
        else:
            ln = ""

    return NormalizedName(
        first_name=fn,
        last_name=ln,
        middle_name=middle_name,
    )
