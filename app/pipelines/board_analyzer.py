"""Board composition analyzer: derive governance signal from leadership raw text (Table 3 scoring)."""

import logging
import re
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Table 3: Base 20, max 100
BASE_SCORE = Decimal("20")
MAX_SCORE = Decimal("100")
POINTS_TECH_COMMITTEE = Decimal("15")
POINTS_AI_EXPERTISE = Decimal("20")
POINTS_DATA_OFFICER = Decimal("15")
POINTS_INDEPENDENT_RATIO = Decimal("10")
POINTS_RISK_TECH_OVERSIGHT = Decimal("10")
POINTS_AI_IN_STRATEGY = Decimal("10")

AI_EXPERTISE_KEYWORDS = [
    "artificial intelligence",
    "machine learning",
    "chief data officer",
    "cdo",
    "caio",
    "chief ai",
    "chief technology",
    "cto",
    "chief digital",
    "data science",
    "analytics",
    "digital transformation",
]

TECH_COMMITTEE_NAMES = [
    "technology committee",
    "digital committee",
    "innovation committee",
    "it committee",
    "technology and cybersecurity",
]

DATA_OFFICER_TITLES = [
    "chief data officer",
    "cdo",
    "chief ai officer",
    "caio",
    "chief analytics officer",
    "cao",
    "chief digital officer",
]

RISK_TECH_KEYWORDS = [
    "risk committee",
    "audit committee",
    "technology oversight",
    "cybersecurity",
    "tech oversight",
    "digital oversight",
]

AI_STRATEGY_KEYWORDS = [
    "artificial intelligence",
    "machine learning",
    "ai strategy",
    "strategic priority",
    "digital transformation",
    "data strategy",
]

# Committee header phrases in DEF-14A
COMMITTEE_HEADERS = [
    "board committees",
    "committees of the board",
    "committee membership",
    "standing committees",
]


class BoardMember(BaseModel):
    """Single board member extracted from proxy (DEF-14A)."""

    name: str = ""
    title: str = ""
    committees: List[str] = Field(default_factory=list)
    bio: str = ""
    is_independent: bool = False
    tenure_years: Optional[float] = None


class GovernanceSignal(BaseModel):
    """Board-derived governance signal (Table 3)."""

    company_id: str
    ticker: str
    has_tech_committee: bool = False
    has_ai_expertise: bool = False
    has_data_officer: bool = False
    has_risk_tech_oversight: bool = False
    has_ai_in_strategy: bool = False
    tech_expertise_count: int = 0
    independent_ratio: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    governance_score: Decimal = Field(default=BASE_SCORE, ge=0, le=100)
    confidence: Decimal = Field(default=Decimal("0.5"), ge=0, le=1)
    ai_experts: List[str] = Field(default_factory=list)
    relevant_committees: List[str] = Field(default_factory=list)


class BoardCompositionAnalyzer:
    """
    Analyze board composition for AI governance indicators from leadership page text.

    Scoring (Table 3):
    - Tech committee exists: +15
    - AI expertise on board: +20
    - Data officer role: +15
    - Independent ratio > 0.5: +10 (omitted when only leadership text)
    - Risk committee tech oversight: +10
    - AI in strategic priorities: +10
    - Base: 20, Max: 100
    """

    def analyze_from_leadership_text(
        self,
        company_id: str | UUID,
        ticker: str,
        leadership_text: str,
    ) -> GovernanceSignal:
        """
        Run Table 3 scoring on a single leadership text (no proxy/DEF 14A).

        Scans text for: tech committee, AI expertise, data officer titles,
        risk/tech oversight, AI in strategy. Independent ratio is left 0 when
        only leadership text is available.
        """
        cid = str(company_id) if isinstance(company_id, UUID) else company_id
        text = (leadership_text or "").lower().strip()
        score = BASE_SCORE
        has_tech = False
        has_ai = False
        has_data_officer = False
        has_risk_tech = False
        has_ai_strategy = False
        ai_experts: List[str] = []
        relevant_committees: List[str] = []

        if not text:
            confidence = Decimal("0.2")
            return GovernanceSignal(
                company_id=cid,
                ticker=ticker or "",
                governance_score=score,
                confidence=confidence,
            )

        # Tech committee: any committee name mentioned
        for name in TECH_COMMITTEE_NAMES:
            if name in text:
                has_tech = True
                relevant_committees.append(name)
                score += POINTS_TECH_COMMITTEE
                break

        # AI expertise: keywords in text (e.g. director/exec bios)
        for kw in AI_EXPERTISE_KEYWORDS:
            if kw in text:
                has_ai = True
                ai_experts.append(kw)
        if has_ai:
            score += POINTS_AI_EXPERTISE

        # Data officer: executive titles
        for title in DATA_OFFICER_TITLES:
            if title in text:
                has_data_officer = True
                score += POINTS_DATA_OFFICER
                break

        # Independent ratio: not derivable from leadership text alone; skip (+0)

        # Risk committee with tech oversight
        for kw in RISK_TECH_KEYWORDS:
            if kw in text:
                has_risk_tech = True
                score += POINTS_RISK_TECH_OVERSIGHT
                break

        # AI in strategic priorities
        for kw in AI_STRATEGY_KEYWORDS:
            if kw in text:
                has_ai_strategy = True
                score += POINTS_AI_IN_STRATEGY
                break

        score = min(score, MAX_SCORE)
        # Confidence from text length (more text = more evidence)
        word_count = len(text.split())
        confidence = min(Decimal("0.5") + Decimal(word_count) / Decimal("500"), Decimal("0.95"))

        return GovernanceSignal(
            company_id=cid,
            ticker=ticker or "",
            has_tech_committee=has_tech,
            has_ai_expertise=has_ai,
            has_data_officer=has_data_officer,
            has_risk_tech_oversight=has_risk_tech,
            has_ai_in_strategy=has_ai_strategy,
            tech_expertise_count=len(ai_experts),
            governance_score=score,
            confidence=confidence,
            ai_experts=ai_experts,
            relevant_committees=relevant_committees,
        )


def extract_from_proxy(proxy_text: str) -> Tuple[List[BoardMember], List[str]]:
    """
    Heuristic extraction of board members and committee names from DEF-14A (proxy) text.
    Returns (members, committee_names). DEF-14A format varies; uses regex and keyword search.
    """
    if not (proxy_text or "").strip():
        return [], []

    text = proxy_text
    text_lower = text.lower()
    members: List[BoardMember] = []
    committee_names: List[str] = []

    # Committees: "X Committee" pattern and known tech/risk names
    committee_pattern = re.compile(
        r"\b([A-Za-z][A-Za-z\s&-]+(?:Committee|committee))\b",
        re.IGNORECASE,
    )
    for m in committee_pattern.finditer(text):
        name = m.group(1).strip()
        if name and name.lower() not in [c.lower() for c in committee_names]:
            committee_names.append(name)

    for name in TECH_COMMITTEE_NAMES:
        if name in text_lower and name not in [c.lower() for c in committee_names]:
            committee_names.append(name.title())

    for kw in RISK_TECH_KEYWORDS:
        if kw in text_lower:
            if "committee" in kw and kw not in [c.lower() for c in committee_names]:
                committee_names.append(kw.title())

    # Directors: look for lines/blocks with "Director" and optionally "Independent"
    # Common pattern: "Name  Director  Since  Independent  Committees"
    lines = text.split("\n")
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if "director" not in line_lower:
            continue
        # Try to get name: often the line starts with a name or it's the previous line
        name = ""
        if i > 0 and lines[i - 1].strip() and not re.search(r"(director|independent|committee|since|year)", lines[i - 1].lower()):
            prev = lines[i - 1].strip()
            # First two words as potential name
            parts = prev.split()
            if len(parts) >= 2 and len(parts[0]) > 1 and len(parts[1]) > 1:
                name = f"{parts[0]} {parts[1]}"
        if not name:
            parts = line.strip().split()
            for j, p in enumerate(parts):
                if "director" in p.lower():
                    if j >= 2:
                        name = f"{parts[0]} {parts[1]}"
                    elif j == 1 and len(parts) > 1:
                        name = parts[0]
                    break
        if not name:
            name = "Unknown"
        is_ind = "independent" in line_lower
        # Bio: use current line or next few lines if short
        bio = line.strip()
        if i + 1 < len(lines) and lines[i + 1].strip() and "director" not in lines[i + 1].lower():
            bio = (bio + " " + lines[i + 1].strip())[:500]
        member = BoardMember(
            name=name,
            title="Director",
            committees=[],
            bio=bio,
            is_independent=is_ind,
        )
        # Dedupe by name
        if not any(m.name == name for m in members):
            members.append(member)

    return members, committee_names


def analyze_board(
    company_id: str | UUID,
    ticker: str,
    members: List[BoardMember],
    committees: List[str],
    strategy_text: str,
    leadership_text: Optional[str] = None,
) -> GovernanceSignal:
    """
    Full Table 3 scoring from SEC-derived board data plus optional leadership text.
    - Tech committee: +15
    - AI expertise (from member bios): +20
    - Data officer (from leadership text): +15
    - Independent ratio > 0.5: +10
    - Risk/tech oversight: +10
    - AI in strategy: +10
    Base 20, cap 100.
    """
    cid = str(company_id) if isinstance(company_id, UUID) else company_id
    score = BASE_SCORE
    has_tech = False
    has_ai = False
    has_data_officer = False
    has_risk_tech = False
    has_ai_strategy = False
    ai_experts: List[str] = []
    relevant_committees: List[str] = []
    leadership_lower = (leadership_text or "").lower()
    strategy_lower = (strategy_text or "").lower()
    committees_lower = [c.lower() for c in committees]

    # Tech committee
    for name in TECH_COMMITTEE_NAMES:
        if any(name in c for c in committees_lower):
            has_tech = True
            relevant_committees.append(name)
            score += POINTS_TECH_COMMITTEE
            break

    # AI expertise from member bios
    for m in members:
        bio_lower = (m.bio or "").lower()
        for kw in AI_EXPERTISE_KEYWORDS:
            if kw in bio_lower:
                has_ai = True
                if m.name and m.name not in ai_experts:
                    ai_experts.append(m.name)
                break
    if has_ai:
        score += POINTS_AI_EXPERTISE

    # Data officer from leadership text only
    for title in DATA_OFFICER_TITLES:
        if title in leadership_lower:
            has_data_officer = True
            score += POINTS_DATA_OFFICER
            break

    # Independent ratio
    n = len(members)
    ind_count = sum(1 for m in members if m.is_independent)
    ratio = Decimal(ind_count) / Decimal(n) if n else Decimal("0")
    if ratio > Decimal("0.5"):
        score += POINTS_INDEPENDENT_RATIO

    # Risk/tech oversight from committees or proxy text (we don't have raw proxy here, use committees)
    for kw in RISK_TECH_KEYWORDS:
        if any(kw in c for c in committees_lower):
            has_risk_tech = True
            score += POINTS_RISK_TECH_OVERSIGHT
            break

    # AI in strategy (10-K Item 1)
    for kw in AI_STRATEGY_KEYWORDS:
        if kw in strategy_lower:
            has_ai_strategy = True
            score += POINTS_AI_IN_STRATEGY
            break

    score = min(score, MAX_SCORE)
    total_words = len((strategy_text or "").split()) + sum(
        len((m.bio or "").split()) for m in members
    )
    confidence = min(Decimal("0.5") + Decimal(total_words) / Decimal("500"), Decimal("0.95"))

    return GovernanceSignal(
        company_id=cid,
        ticker=ticker or "",
        has_tech_committee=has_tech,
        has_ai_expertise=has_ai,
        has_data_officer=has_data_officer,
        has_risk_tech_oversight=has_risk_tech,
        has_ai_in_strategy=has_ai_strategy,
        tech_expertise_count=len(ai_experts),
        independent_ratio=ratio,
        governance_score=score,
        confidence=confidence,
        ai_experts=ai_experts,
        relevant_committees=relevant_committees,
    )
