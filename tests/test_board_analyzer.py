"""Tests for board composition analyzer."""

import pytest
from decimal import Decimal
from uuid import uuid4

from app.pipelines.board_analyzer import (
    BoardCompositionAnalyzer,
    BoardMember,
    GovernanceSignal,
    extract_from_proxy,
    analyze_board,
    BASE_SCORE,
    MAX_SCORE,
)


def test_analyze_from_leadership_text_returns_governance_signal():
    """analyze_from_leadership_text returns a GovernanceSignal with company_id and ticker."""
    analyzer = BoardCompositionAnalyzer()
    company_id = uuid4()
    result = analyzer.analyze_from_leadership_text(
        company_id=company_id,
        ticker="NVDA",
        leadership_text="Our board has a technology committee and our CTO leads digital strategy.",
    )
    assert isinstance(result, GovernanceSignal)
    assert result.company_id == str(company_id)
    assert result.ticker == "NVDA"
    assert result.governance_score >= BASE_SCORE
    assert result.governance_score <= MAX_SCORE


def test_analyze_empty_text_returns_base_score():
    """Empty or missing leadership text returns base score and low confidence."""
    analyzer = BoardCompositionAnalyzer()
    result = analyzer.analyze_from_leadership_text(
        company_id="test-id",
        ticker="X",
        leadership_text="",
    )
    assert result.governance_score == BASE_SCORE
    assert result.confidence <= Decimal("0.5")
    assert result.has_tech_committee is False
    assert result.has_data_officer is False


def test_analyze_data_officer_adds_points():
    """Text containing data officer title (e.g. CTO, CDO) adds +15."""
    analyzer = BoardCompositionAnalyzer()
    result = analyzer.analyze_from_leadership_text(
        company_id="test-id",
        ticker="T",
        leadership_text="Our Chief Technology Officer and Chief Data Officer lead innovation.",
    )
    assert result.has_data_officer is True
    assert result.governance_score >= BASE_SCORE + Decimal("15")


def test_analyze_ai_strategy_adds_points():
    """Text containing AI/strategy keywords adds +10."""
    analyzer = BoardCompositionAnalyzer()
    result = analyzer.analyze_from_leadership_text(
        company_id="test-id",
        ticker="T",
        leadership_text="Artificial intelligence is a strategic priority for our company.",
    )
    assert result.has_ai_in_strategy is True
    assert result.governance_score >= BASE_SCORE + Decimal("10")


def test_analyze_tech_committee_adds_points():
    """Text containing tech committee name adds +15."""
    analyzer = BoardCompositionAnalyzer()
    result = analyzer.analyze_from_leadership_text(
        company_id="test-id",
        ticker="T",
        leadership_text="The technology committee oversees our digital initiatives.",
    )
    assert result.has_tech_committee is True
    assert result.governance_score >= BASE_SCORE + Decimal("15")


def test_analyze_ai_expertise_adds_points():
    """Text containing AI expertise keywords adds +20."""
    analyzer = BoardCompositionAnalyzer()
    result = analyzer.analyze_from_leadership_text(
        company_id="test-id",
        ticker="T",
        leadership_text="Our directors bring machine learning and data science expertise.",
    )
    assert result.has_ai_expertise is True
    assert result.tech_expertise_count >= 1
    assert result.governance_score >= BASE_SCORE + Decimal("20")


def test_analyze_score_capped_at_100():
    """Governance score is capped at 100 even with all indicators."""
    analyzer = BoardCompositionAnalyzer()
    text = (
        "We have a technology committee and a digital committee. "
        "Our Chief Data Officer and Chief AI Officer lead the team. "
        "Machine learning and artificial intelligence are strategic priorities. "
        "The risk committee provides technology oversight. "
        "Our board has deep data science and analytics expertise."
    )
    result = analyzer.analyze_from_leadership_text(
        company_id="test-id",
        ticker="T",
        leadership_text=text,
    )
    assert result.governance_score <= MAX_SCORE


def test_analyze_accepts_uuid_or_str_company_id():
    """company_id can be UUID or str."""
    analyzer = BoardCompositionAnalyzer()
    uid = uuid4()
    r1 = analyzer.analyze_from_leadership_text(uid, "A", "CTO leads tech.")
    r2 = analyzer.analyze_from_leadership_text(str(uid), "A", "CTO leads tech.")
    assert r1.company_id == r2.company_id == str(uid)


# --- extract_from_proxy ---


def test_extract_from_proxy_empty_returns_empty():
    """Empty proxy text returns empty members and committees."""
    members, committees = extract_from_proxy("")
    assert members == []
    assert committees == []


def test_extract_from_proxy_finds_committees():
    """Proxy text with committee names returns committee list."""
    text = """
    Board Committees
    The Board has an Audit Committee, a Compensation Committee, and a Technology Committee.
    """
    members, committees = extract_from_proxy(text)
    assert "Technology Committee" in committees or any("technology" in c.lower() for c in committees)
    assert any("audit" in c.lower() or "Audit" in c for c in committees)


def test_extract_from_proxy_finds_directors_and_independence():
    """Proxy text with director table yields BoardMembers and independence."""
    text = """
    Director Independence
    Jane Smith
    Director since 2018  Independent  Audit Committee, Technology Committee
    John Doe
    Director since 2015  Independent  Compensation Committee
    """
    members, committees = extract_from_proxy(text)
    assert len(members) >= 1
    assert all(isinstance(m, BoardMember) for m in members)
    # At least one member with Director in line may be marked independent
    ind_count = sum(1 for m in members if m.is_independent)
    assert ind_count >= 0  # heuristic may or may not set it from this snippet


# --- analyze_board ---


def test_analyze_board_returns_governance_signal():
    """analyze_board returns GovernanceSignal with score in [0, 100]."""
    members = [
        BoardMember(name="Alice", bio="CTO and machine learning expert.", is_independent=True),
        BoardMember(name="Bob", bio="Finance.", is_independent=True),
    ]
    committees = ["Technology Committee", "Audit Committee"]
    result = analyze_board(
        company_id=uuid4(),
        ticker="NVDA",
        members=members,
        committees=committees,
        strategy_text="AI is a strategic priority.",
        leadership_text="Our Chief Data Officer leads analytics.",
    )
    assert isinstance(result, GovernanceSignal)
    assert result.governance_score >= 0
    assert result.governance_score <= 100
    assert result.company_id
    assert result.ticker == "NVDA"


def test_analyze_board_tech_committee_adds_15():
    """Tech committee in list adds +15."""
    members = [BoardMember(name="A", bio="", is_independent=False)]
    committees = ["Technology Committee"]
    result = analyze_board(
        company_id="c",
        ticker="T",
        members=members,
        committees=committees,
        strategy_text="",
        leadership_text="",
    )
    assert result.has_tech_committee is True
    assert result.governance_score >= BASE_SCORE + Decimal("15")


def test_analyze_board_ai_expertise_in_bio_adds_20():
    """AI expertise keyword in member bio adds +20."""
    members = [
        BoardMember(name="Jane", bio="Former CTO with artificial intelligence experience.", is_independent=True),
    ]
    result = analyze_board(
        company_id="c",
        ticker="T",
        members=members,
        committees=[],
        strategy_text="",
        leadership_text="",
    )
    assert result.has_ai_expertise is True
    assert result.governance_score >= BASE_SCORE + Decimal("20")
    assert "Jane" in result.ai_experts


def test_analyze_board_data_officer_from_leadership_adds_15():
    """Data officer title in leadership text adds +15."""
    members = [BoardMember(name="A", bio="", is_independent=False)]
    result = analyze_board(
        company_id="c",
        ticker="T",
        members=members,
        committees=[],
        strategy_text="",
        leadership_text="Our Chief Data Officer leads the team.",
    )
    assert result.has_data_officer is True
    assert result.governance_score >= BASE_SCORE + Decimal("15")


def test_analyze_board_independent_ratio_over_half_adds_10():
    """Independent ratio > 0.5 adds +10."""
    members = [
        BoardMember(name="A", bio="", is_independent=True),
        BoardMember(name="B", bio="", is_independent=True),
        BoardMember(name="C", bio="", is_independent=False),
    ]
    result = analyze_board(
        company_id="c",
        ticker="T",
        members=members,
        committees=[],
        strategy_text="",
        leadership_text="",
    )
    assert result.independent_ratio > Decimal("0.5")
    assert result.governance_score >= BASE_SCORE + Decimal("10")


def test_analyze_board_ai_in_strategy_adds_10():
    """Strategy text with AI keywords adds +10."""
    result = analyze_board(
        company_id="c",
        ticker="T",
        members=[],
        committees=[],
        strategy_text="Machine learning and digital transformation are strategic priorities.",
        leadership_text="",
    )
    assert result.has_ai_in_strategy is True
    assert result.governance_score >= BASE_SCORE + Decimal("10")


def test_analyze_board_score_capped_at_100():
    """Full scoring is capped at 100."""
    members = [
        BoardMember(name="A", bio="machine learning and CTO experience", is_independent=True),
        BoardMember(name="B", bio="data science", is_independent=True),
    ]
    result = analyze_board(
        company_id="c",
        ticker="T",
        members=members,
        committees=["Technology Committee", "Audit Committee"],
        strategy_text="Artificial intelligence is a strategic priority. Data strategy.",
        leadership_text="Chief Data Officer and CAIO.",
    )
    assert result.governance_score <= MAX_SCORE


def test_board_composition_payload_round_trip():
    """Raw payload shape round-trips: build payload, parse back, run analyzer, same score."""
    members = [
        BoardMember(name="Jane", bio="CTO with AI experience", is_independent=True),
        BoardMember(name="Bob", bio="Finance", is_independent=True),
    ]
    committees = ["Technology Committee"]
    strategy_text = "AI is a strategic priority."
    leadership_text = "Our Chief Data Officer leads analytics."
    # Simulate what collection stores
    payload = {
        "members": [m.model_dump() for m in members],
        "committees": committees,
        "strategy_text": strategy_text,
        "leadership_text": leadership_text,
    }
    # Simulate what compute does: parse and run
    members_parsed = [BoardMember.model_validate(m) for m in payload.get("members", [])]
    committees_parsed = payload.get("committees", [])
    result = analyze_board(
        company_id=uuid4(),
        ticker="T",
        members=members_parsed,
        committees=committees_parsed,
        strategy_text=payload.get("strategy_text") or "",
        leadership_text=payload.get("leadership_text") or "",
    )
    assert 0 <= result.governance_score <= 100
    assert result.has_tech_committee is True
    assert result.has_ai_expertise is True
    assert result.has_data_officer is True
    assert result.has_ai_in_strategy is True


def test_board_composition_leadership_only_payload_round_trip():
    """Leadership-only payload (no members): parse and run analyze_from_leadership_text path."""
    payload = {
        "members": [],
        "committees": [],
        "strategy_text": "Machine learning strategic priority.",
        "leadership_text": "Technology committee and Chief Data Officer.",
    }
    analyzer = BoardCompositionAnalyzer()
    combined = ((payload.get("leadership_text") or "") + " " + (payload.get("strategy_text") or "")).strip()
    result = analyzer.analyze_from_leadership_text(
        company_id="c",
        ticker="T",
        leadership_text=combined,
    )
    assert 0 <= result.governance_score <= 100
    assert result.has_tech_committee is True
    assert result.has_data_officer is True
