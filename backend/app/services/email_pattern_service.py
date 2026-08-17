"""EmailPatternService managing corporate email candidate generation and pattern library definitions."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.schemas.email_pattern import EmailPatternSchema
from app.utils.email_formatter import format_email_address
from app.utils.string_normalizer import NormalizedName


@dataclass
class PatternDefinition:
    """Definition of a single email pattern template."""

    name: str
    template: str
    description: str
    base_confidence: float
    tier: int = 1
    requires_last_name: bool = False
    requires_middle_name: bool = False


# Supported corporate email pattern library trained from 81 verified Apollo contacts.
# Real-world frequency: first.last=56.8%, first.l=16%, first=13.6%, firstlast/flast=4.9% each, last.first=2.5%
SUPPORTED_PATTERNS: List[PatternDefinition] = [
    # --- Tier 1: Primary person-specific patterns (backed by Apollo 81-contact dataset) ---
    PatternDefinition(
        name="first.last",
        template="{first}.{last}",
        description="First name dot last name (e.g. john.doe@domain) — 56.8% of verified emails",
        base_confidence=0.95,
        tier=1,
        requires_last_name=True,
    ),
    PatternDefinition(
        name="firstname.l",
        template="{first}.{l}",
        description="First name dot last initial (e.g. john.d@domain) — 16.0% of verified emails",
        base_confidence=0.92,
        tier=1,
        requires_last_name=True,
    ),
    PatternDefinition(
        name="first",
        template="{first}",
        description="First name only (e.g. john@domain) — 13.6% of verified emails",
        base_confidence=0.90,
        tier=1,
    ),
    PatternDefinition(
        name="firstinitiallastname",
        template="{f}{last}",
        description="First initial + last name no dot (e.g. jdoe@domain) — 4.9% of verified emails",
        base_confidence=0.88,
        tier=1,
        requires_last_name=True,
    ),
    PatternDefinition(
        name="firstlast",
        template="{first}{last}",
        description="First + last concatenated (e.g. johndoe@domain) — 4.9% of verified emails",
        base_confidence=0.85,
        tier=1,
        requires_last_name=True,
    ),
    PatternDefinition(
        name="f.lastname",
        template="{f}.{last}",
        description="First initial dot last name (e.g. j.doe@domain)",
        base_confidence=0.82,
        tier=1,
        requires_last_name=True,
    ),

    # --- Tier 2: Secondary person-specific patterns ---
    PatternDefinition(
        name="last.first",
        template="{last}.{first}",
        description="Last name dot first name (e.g. doe.john@domain) — 2.5% of verified emails",
        base_confidence=0.78,
        tier=2,
        requires_last_name=True,
    ),
    PatternDefinition(
        name="last.f",
        template="{last}.{f}",
        description="Last name dot first initial (e.g. doe.j@domain) — 1.2% of verified emails",
        base_confidence=0.75,
        tier=2,
        requires_last_name=True,
    ),
    PatternDefinition(
        name="lastnamefirstinitial",
        template="{last}{f}",
        description="Last name + first initial (e.g. doej@domain)",
        base_confidence=0.72,
        tier=2,
        requires_last_name=True,
    ),
    PatternDefinition(
        name="first_last",
        template="{first}_{last}",
        description="First name underscore last name (e.g. john_doe@domain)",
        base_confidence=0.70,
        tier=2,
        requires_last_name=True,
    ),
    PatternDefinition(
        name="first-last",
        template="{first}-{last}",
        description="First name hyphen last name (e.g. john-doe@domain)",
        base_confidence=0.68,
        tier=2,
        requires_last_name=True,
    ),
    PatternDefinition(
        name="firstlastinitial",
        template="{first}{l}",
        description="First name + last initial no dot (e.g. johnd@domain)",
        base_confidence=0.68,
        tier=2,
        requires_last_name=True,
    ),
    PatternDefinition(
        name="f_lastname",
        template="{f}_{last}",
        description="First initial underscore last name (e.g. j_doe@domain)",
        base_confidence=0.65,
        tier=2,
        requires_last_name=True,
    ),
    PatternDefinition(
        name="last.f",
        template="{last}.{f}",
        description="Last name dot first initial (e.g. doe.j@domain)",
        base_confidence=0.60,
        tier=2,
        requires_last_name=True,
    ),
    PatternDefinition(
        name="last",
        template="{last}",
        description="Last name only (e.g. doe@domain)",
        base_confidence=0.55,
        tier=2,
        requires_last_name=True,
    ),
    PatternDefinition(
        name="last_first",
        template="{last}_{first}",
        description="Last name underscore first name (e.g. doe_john@domain)",
        base_confidence=0.50,
        tier=2,
        requires_last_name=True,
    ),
    PatternDefinition(
        name="lastfirst",
        template="{last}{first}",
        description="Last name first name concatenated (e.g. doejohn@domain)",
        base_confidence=0.45,
        tier=2,
        requires_last_name=True,
    ),
    PatternDefinition(
        name="first.middle.last",
        template="{first}.{m}.{last}",
        description="First dot middle initial dot last (e.g. john.m.doe@domain)",
        base_confidence=0.60,
        tier=2,
        requires_last_name=True,
        requires_middle_name=True,
    ),

    # --- Tier 3: Numbered variants (0% in real Apollo data — very rare) ---
    PatternDefinition(
        name="first1",
        template="{first}1",
        description="First name with number 1 (e.g. john1@domain) — 0% in real data",
        base_confidence=0.25,
        tier=3,
    ),
    PatternDefinition(
        name="first.last1",
        template="{first}.{last}1",
        description="First dot last with number 1 (e.g. john.doe1@domain) — 0% in real data",
        base_confidence=0.25,
        tier=3,
        requires_last_name=True,
    ),
    PatternDefinition(
        name="firstinitiallastname1",
        template="{f}{last}1",
        description="First initial last name with number 1 (e.g. jdoe1@domain) — 0% in real data",
        base_confidence=0.22,
        tier=3,
        requires_last_name=True,
    ),
    PatternDefinition(
        name="first2",
        template="{first}2",
        description="First name with number 2 (e.g. john2@domain) — 0% in real data",
        base_confidence=0.20,
        tier=3,
    ),
    PatternDefinition(
        name="first.last2",
        template="{first}.{last}2",
        description="First dot last with number 2 (e.g. john.doe2@domain) — 0% in real data",
        base_confidence=0.20,
        tier=3,
        requires_last_name=True,
    ),
    PatternDefinition(
        name="firstinitiallastname2",
        template="{f}{last}2",
        description="First initial last name with number 2 (e.g. jdoe2@domain) — 0% in real data",
        base_confidence=0.18,
        tier=3,
        requires_last_name=True,
    ),
]


class EmailPatternService:
    """Service providing pattern library metadata and generating email candidates."""

    def __init__(self, patterns: Optional[List[PatternDefinition]] = None) -> None:
        """Initialize pattern service with pattern list."""
        self._patterns = patterns or SUPPORTED_PATTERNS

    def get_pattern_by_name(self, pattern_name: str) -> Optional[PatternDefinition]:
        """Find PatternDefinition by pattern name."""
        for p in self._patterns:
            if p.name == pattern_name:
                return p
        return None

    def get_supported_patterns(self) -> List[EmailPatternSchema]:
        """Return list of supported patterns formatted as API response schemas."""
        sample_name = NormalizedName(first_name="sam", last_name="altman", middle_name="m")
        sample_domain = "openai.com"
        result: List[EmailPatternSchema] = []

        for p in self._patterns:
            formatted = self._format_pattern_local_part(p, sample_name)
            example_email = f"{formatted}@{sample_domain}" if formatted else f"example@{sample_domain}"

            result.append(
                EmailPatternSchema(
                    pattern_name=p.name,
                    template=p.template,
                    description=p.description,
                    base_confidence=p.base_confidence,
                    example=example_email,
                )
            )

        return result

    def _format_pattern_local_part(self, pattern: PatternDefinition, name: NormalizedName) -> Optional[str]:
        """Format pattern template using normalized name attributes."""
        if pattern.requires_last_name and not name.last_name:
            return None
        if pattern.requires_middle_name and not name.middle_name:
            return None
        if not name.first_name and not name.last_name:
            return None

        first = name.first_name or ""
        last = name.last_name or ""
        f_init = name.first_initial or (first[0] if first else "")
        l_init = name.last_initial or (last[0] if last else "")
        m_name = name.middle_name or ""
        m_init = name.middle_initial or (m_name[0] if m_name else "")

        try:
            local_part = pattern.template.format(
                first=first,
                last=last,
                f=f_init,
                l=l_init,
                m=m_init,
                middle=m_name,
            )
            return local_part
        except Exception:
            return None

    def generate_candidate_permutations(
        self,
        name: NormalizedName,
        domain: str,
        tier: Optional[int] = None,
    ) -> List[Tuple[str, str, float]]:
        """Generate (candidate_email, pattern_name, base_confidence) list for given normalized name and domain."""
        candidates: List[Tuple[str, str, float]] = []

        for p in self._patterns:
            # Ignored tier concept to verify and rank all generated patterns flatly
            local_part = self._format_pattern_local_part(p, name)
            if not local_part:
                continue

            email = format_email_address(local_part, domain)
            if email:
                candidates.append((email, p.name, p.base_confidence))

        return candidates

    def generate_tier1_permutations(
        self,
        name: NormalizedName,
        domain: str,
    ) -> List[Tuple[str, str, float]]:
        """Generate standard corporate permutations (legacy tier 1 compatibility)."""
        return self.generate_candidate_permutations(name, domain)

    def generate_tier2_permutations(
        self,
        name: NormalizedName,
        domain: str,
    ) -> List[Tuple[str, str, float]]:
        """Generate edge cases and numbered permutations (legacy tier 2 compatibility)."""
        return self.generate_candidate_permutations(name, domain)

