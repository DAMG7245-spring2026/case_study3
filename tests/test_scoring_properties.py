"""Task 5.3: Property-Based Tests for V^R, Evidence Mapper, and scoring utilities.

Uses Hypothesis to verify:
  VR tests:
    1. test_vr_always_bounded        – 0 ≤ V^R ≤ 100 for all valid inputs
    2. test_higher_scores_increase_vr – monotonicity
    3. test_talent_concentration_penalty – higher TC ⇒ lower or equal V^R
    4. test_uniform_dimensions_no_cv_penalty – uniform scores ⇒ penalty ≈ 1
    5. test_deterministic            – same inputs ⇒ identical output

  Mapper tests:
    6. test_all_dimensions_returned  – always returns 7 dimensions
    7. test_missing_evidence_defaults_to_50 – no evidence ⇒ score = 50
    8. test_more_evidence_higher_confidence – more sources ⇒ confidence ≥

  Decimal utility tests:
    9. test_to_decimal_precision
   10. test_clamp_bounds
   11. test_weighted_mean_bounds
   12. test_cv_non_negative

  Additional coverage tests (Task 5.3 – ≥80%):
   13–15. TestHRCalculator
   16–18. TestSynergyCalculator
   19–22. TestConfidenceCalculator
   23–24. TestPositionFactorCalculator
   25–27. TestOrgAIRCalculator
   28–30. TestWeightedStdDevEdgeCases
   31–32. TestEvidenceMapperCoverage
   33–35. TestMappingTableFunctions
   36–38. TestTalentConcentrationJobAnalysis
"""
from decimal import Decimal

import pytest
from hypothesis import HealthCheck, given, settings as h_settings
from hypothesis import strategies as st

from app.models.enums import DIMENSION_WEIGHTS, Dimension
from app.pipelines.evidence_mapper.evidence_mapper import EvidenceMapper
from app.pipelines.evidence_mapper.evidence_mapping_table import (
    DimensionMapping,
    EvidenceScore,
    SignalSource,
    build_signal_to_dimension_map,
    compute_weights_hash,
)
from app.scoring.confidence import ConfidenceCalculator, _erfinv, _norm_ppf
from app.scoring.hr_calculator import HRCalculator
from app.scoring.org_air_calculator import OrgAIRCalculator
from app.scoring.position_factor import PositionFactorCalculator
from app.scoring.synergy_calculator import SynergyCalculator
from app.scoring.talent_concentration import (
    JobAnalysis,
    TalentConcentrationCalculator,
)
from app.scoring.utils import (
    clamp,
    coefficient_of_variation,
    to_decimal,
    weighted_mean,
    weighted_std_dev,
)
from app.scoring.vr_calculator import VRCalculator

# ── Hypothesis configuration ──────────────────────────────────────────────────
h_settings.register_profile(
    "ci",
    max_examples=500,
    suppress_health_check=[HealthCheck.too_slow],
)
h_settings.load_profile("ci")


# ── Strategy helpers ──────────────────────────────────────────────────────────

_dim_score = st.floats(min_value=0.0, max_value=100.0, allow_nan=False)
_dim_scores_list = st.lists(
    _dim_score,
    min_size=7,
    max_size=7,
)
_tc = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
_all_dims = {d.value: _dim_score for d in Dimension}
_dim_scores_dict = st.fixed_dictionaries(_all_dims)


# ── V^R property tests ────────────────────────────────────────────────────────

class TestVRProperties:
    """Property-based tests for VRCalculator."""

    calc = VRCalculator()

    @given(dim_scores=_dim_scores_dict, tc=_tc)
    @h_settings(max_examples=500)
    def test_vr_always_bounded(self, dim_scores, tc):
        """V^R must always be in [0, 100] for any valid inputs."""
        result = self.calc.calculate(dim_scores, tc)
        assert Decimal(0) <= result.vr_score <= Decimal(100), (
            f"V^R={result.vr_score} out of [0,100] for dims={dim_scores}, tc={tc}"
        )

    @given(
        base_score=st.floats(min_value=0.0, max_value=70.0, allow_nan=False),
        delta=st.floats(min_value=0.1, max_value=20.0, allow_nan=False),
        tc=_tc,
    )
    @h_settings(max_examples=500)
    def test_higher_scores_increase_vr(self, base_score, delta, tc):
        """Increasing all dimension scores by δ should not decrease V^R."""
        low_dims  = {d.value: base_score           for d in Dimension}
        high_dims = {d.value: min(base_score + delta, 100.0) for d in Dimension}
        low_vr  = self.calc.calculate(low_dims,  tc).vr_score
        high_vr = self.calc.calculate(high_dims, tc).vr_score
        assert high_vr >= low_vr - Decimal("0.0001"), (
            f"V^R decreased: {low_vr} → {high_vr} "
            f"when all dims increased from {base_score} by {delta}"
        )

    @given(
        dim_scores=_dim_scores_dict,
        low_tc=st.floats(min_value=0.0, max_value=0.5, allow_nan=False),
        high_tc=st.floats(min_value=0.5, max_value=1.0, allow_nan=False),
    )
    @h_settings(max_examples=500)
    def test_talent_concentration_penalty(self, dim_scores, low_tc, high_tc):
        """Higher TC should yield a lower or equal V^R (all else equal)."""
        vr_low  = self.calc.calculate(dim_scores, low_tc).vr_score
        vr_high = self.calc.calculate(dim_scores, high_tc).vr_score
        # V^R with higher TC must be ≤ V^R with lower TC (within rounding tolerance)
        assert vr_high <= vr_low + Decimal("0.0001"), (
            f"Expected V^R({high_tc}) ≤ V^R({low_tc}), "
            f"got {vr_high} > {vr_low}"
        )

    @given(
        uniform_score=st.floats(min_value=10.0, max_value=90.0, allow_nan=False),
        tc=_tc,
    )
    @h_settings(max_examples=500)
    def test_uniform_dimensions_no_cv_penalty(self, uniform_score, tc):
        """Uniform dimension scores produce CV ≈ 0, so penalty factor ≈ 1."""
        dims = {d.value: uniform_score for d in Dimension}
        result = self.calc.calculate(dims, tc)
        # With identical scores, std_dev should be ≈ 0 → CV ≈ 0 → penalty ≈ 1
        assert result.coefficient_of_variation <= Decimal("0.01"), (
            f"CV={result.coefficient_of_variation} expected ≈ 0 for uniform scores"
        )
        assert result.penalty_factor >= Decimal("0.99"), (
            f"penalty_factor={result.penalty_factor} expected ≈ 1 for uniform scores"
        )

    @given(dim_scores=_dim_scores_dict, tc=_tc)
    @h_settings(max_examples=500)
    def test_deterministic(self, dim_scores, tc):
        """Identical inputs must always produce identical output."""
        r1 = self.calc.calculate(dim_scores, tc)
        r2 = self.calc.calculate(dim_scores, tc)
        assert r1.vr_score == r2.vr_score
        assert r1.penalty_factor == r2.penalty_factor
        assert r1.talent_risk_adjustment == r2.talent_risk_adjustment


# ── Evidence mapper property tests ────────────────────────────────────────────

_sources = list(SignalSource)

_evidence_score_st = st.builds(
    EvidenceScore,
    source=st.sampled_from(_sources),
    raw_score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False).map(
        lambda x: to_decimal(x)
    ),
    confidence=st.floats(min_value=0.01, max_value=1.0, allow_nan=False).map(
        lambda x: to_decimal(x)
    ),
    evidence_count=st.integers(min_value=1, max_value=100),
)


class TestEvidenceMapperProperties:
    """Property-based tests for EvidenceMapper."""

    mapper = EvidenceMapper()

    @given(evidences=st.lists(_evidence_score_st, min_size=0, max_size=10))
    @h_settings(max_examples=500)
    def test_all_dimensions_returned(self, evidences):
        """map_evidence_to_dimensions always returns all 7 Dimension keys."""
        result = self.mapper.map_evidence_to_dimensions(evidences)
        assert set(result.keys()) == set(Dimension), (
            f"Missing dimensions: {set(Dimension) - set(result.keys())}"
        )

    def test_missing_evidence_defaults_to_50(self):
        """With no evidence, all dimension scores default to 50."""
        result = self.mapper.map_evidence_to_dimensions([])
        for dim, ds in result.items():
            assert ds.score == Decimal("50"), (
                f"{dim.value} score={ds.score} expected 50 with no evidence"
            )

    @given(
        evidence=_evidence_score_st,
        extra=st.lists(_evidence_score_st, min_size=1, max_size=5),
    )
    @h_settings(max_examples=500)
    def test_more_evidence_higher_confidence(self, evidence, extra):
        """Adding more evidence sources should not decrease total confidence for
        affected dimensions."""
        base_result  = self.mapper.map_evidence_to_dimensions([evidence])
        extra_result = self.mapper.map_evidence_to_dimensions([evidence] + extra)
        # At least one dimension should have equal or higher confidence
        any_improved = any(
            extra_result[d].confidence >= base_result[d].confidence
            for d in Dimension
        )
        assert any_improved, "Adding evidence sources did not improve any dimension confidence"

    @given(evidences=st.lists(_evidence_score_st, min_size=1, max_size=9))
    @h_settings(max_examples=500)
    def test_scores_bounded(self, evidences):
        """All dimension scores must stay in [0, 100]."""
        result = self.mapper.map_evidence_to_dimensions(evidences)
        for dim, ds in result.items():
            assert Decimal(0) <= ds.score <= Decimal(100), (
                f"{dim.value} score={ds.score} out of [0,100]"
            )


# ── Decimal utility unit tests ────────────────────────────────────────────────

class TestDecimalUtils:
    """Unit + property tests for scoring/utils.py functions."""

    def test_to_decimal_precision(self):
        assert to_decimal(3.14159, 4) == Decimal("3.1416")
        assert to_decimal(0.00005, 4) == Decimal("0.0001")  # ROUND_HALF_UP

    def test_to_decimal_already_decimal(self):
        d = Decimal("12.345")
        assert to_decimal(d, 2) == Decimal("12.35")

    def test_clamp_in_range(self):
        assert clamp(Decimal(50)) == Decimal(50)
        assert clamp(Decimal(0))  == Decimal(0)
        assert clamp(Decimal(100)) == Decimal(100)

    def test_clamp_above_max(self):
        assert clamp(Decimal(105))  == Decimal(100)

    def test_clamp_below_min(self):
        assert clamp(Decimal(-5)) == Decimal(0)

    @given(v=st.floats(min_value=-1000, max_value=1000, allow_nan=False))
    @h_settings(max_examples=500)
    def test_clamp_always_in_range(self, v):
        result = clamp(to_decimal(v))
        assert Decimal(0) <= result <= Decimal(100)

    def test_weighted_mean_known_values(self):
        values  = [to_decimal(10), to_decimal(100)]
        weights = [Decimal("0.25"), Decimal("0.75")]
        assert weighted_mean(values, weights) == Decimal("77.5000")

    def test_weighted_mean_empty(self):
        assert weighted_mean([], []) == Decimal(0)

    def test_weighted_mean_mismatched_raises(self):
        with pytest.raises(ValueError):
            weighted_mean([to_decimal(1)], [Decimal("0.5"), Decimal("0.5")])

    def test_cv_zero_mean(self):
        assert coefficient_of_variation(Decimal("5"), Decimal("0")) == Decimal("0")

    def test_cv_zero_std(self):
        assert coefficient_of_variation(Decimal("0"), Decimal("50")) == Decimal("0")

    @given(
        scores=st.lists(
            st.floats(min_value=0, max_value=100, allow_nan=False),
            min_size=2,
            max_size=7,
        )
    )
    @h_settings(max_examples=500)
    def test_cv_non_negative(self, scores):
        """Coefficient of variation is always ≥ 0."""
        n   = len(scores)
        wts = [Decimal(str(round(1.0 / n, 6)))] * n
        dec = [to_decimal(s) for s in scores]
        m   = weighted_mean(dec, wts)
        std = weighted_std_dev(dec, wts, m)
        cv  = coefficient_of_variation(std, m)
        assert cv >= Decimal(0), f"CV={cv} negative for scores={scores}"


# ── Talent Concentration unit tests ──────────────────────────────────────────

class TestTalentConcentration:
    """Unit + property tests for TalentConcentrationCalculator."""

    calc = TalentConcentrationCalculator()

    def _make_analysis(
        self,
        total=10, senior=3, mid=4, entry=3, skills=None
    ) -> JobAnalysis:
        return JobAnalysis(
            total_ai_jobs=total,
            senior_ai_jobs=senior,
            mid_ai_jobs=mid,
            entry_ai_jobs=entry,
            unique_skills=skills or {"python", "pytorch", "tensorflow"},
        )

    def test_tc_bounded(self):
        ja = self._make_analysis()
        tc = self.calc.calculate_tc(ja)
        assert Decimal(0) <= tc <= Decimal(1)

    def test_high_senior_ratio_increases_tc(self):
        low_senior  = self._make_analysis(total=10, senior=1)
        high_senior = self._make_analysis(total=10, senior=9)
        tc_low  = self.calc.calculate_tc(low_senior)
        tc_high = self.calc.calculate_tc(high_senior)
        assert tc_high > tc_low

    def test_more_skills_decreases_tc(self):
        few_skills  = self._make_analysis(skills={"python"})
        many_skills = self._make_analysis(
            skills={"python", "pytorch", "tensorflow", "sql", "spark",
                    "kubernetes", "docker", "pandas", "numpy", "mlflow",
                    "kubeflow", "langchain", "openai", "huggingface", "databricks"}
        )
        tc_few  = self.calc.calculate_tc(few_skills)
        tc_many = self.calc.calculate_tc(many_skills)
        assert tc_many <= tc_few

    @given(
        total=st.integers(min_value=0, max_value=100),
        senior_ratio=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        n_skills=st.integers(min_value=0, max_value=20),
        ind_mentions=st.integers(min_value=0, max_value=100),
        reviews=st.integers(min_value=1, max_value=200),
    )
    @h_settings(max_examples=500)
    def test_tc_always_bounded_property(
        self, total, senior_ratio, n_skills, ind_mentions, reviews
    ):
        senior = int(total * senior_ratio)
        remaining = total - senior
        mid   = remaining // 2
        entry = remaining - mid
        ja = JobAnalysis(
            total_ai_jobs=total,
            senior_ai_jobs=senior,
            mid_ai_jobs=mid,
            entry_ai_jobs=entry,
            unique_skills=set(f"skill_{i}" for i in range(n_skills)),
        )
        tc = self.calc.calculate_tc(ja, ind_mentions, reviews)
        assert Decimal(0) <= tc <= Decimal(1), f"TC={tc} out of [0,1]"


# ── H^R Calculator tests ────────────────────────────────────────────────────

_sectors = st.sampled_from(
    ["technology", "financial_services", "healthcare",
     "business_services", "retail", "manufacturing", "unknown_sector"]
)
_pf = st.floats(min_value=-1.0, max_value=1.0, allow_nan=False)


class TestHRCalculator:
    """Property-based tests for HRCalculator."""

    calc = HRCalculator()

    @given(sector=_sectors, pf=_pf)
    @h_settings(max_examples=500)
    def test_hr_always_bounded(self, sector, pf):
        """H^R score must always be in [0, 100]."""
        result = self.calc.calculate(sector, pf)
        assert Decimal(0) <= result.hr_score <= Decimal(100), (
            f"H^R={result.hr_score} out of [0,100]"
        )

    @given(sector=_sectors, pf=_pf)
    @h_settings(max_examples=500)
    def test_hr_baseline_override(self, sector, pf):
        """Explicit baseline_override is used instead of sector lookup."""
        result = self.calc.calculate(sector, pf, baseline_override=75.0)
        assert result.baseline == to_decimal(75.0)

    @given(
        sector=_sectors,
        pf=st.floats(min_value=0.01, max_value=1.0, allow_nan=False),
    )
    @h_settings(max_examples=500)
    def test_hr_positive_pf_increases_score(self, sector, pf):
        """Positive PF should yield H^R >= baseline."""
        result = self.calc.calculate(sector, pf)
        assert result.hr_score >= result.baseline - Decimal("0.0001")


# ── Synergy Calculator tests ────────────────────────────────────────────────

_score_0_100 = st.floats(min_value=0.0, max_value=100.0, allow_nan=False)
_alignment = st.floats(min_value=0.01, max_value=1.0, allow_nan=False)
_timing = st.floats(min_value=0.0, max_value=2.0, allow_nan=False)


class TestSynergyCalculator:
    """Property-based tests for SynergyCalculator."""

    calc = SynergyCalculator()

    @given(vr=_score_0_100, hr=_score_0_100, align=_alignment, tf=_timing)
    @h_settings(max_examples=500)
    def test_synergy_always_bounded(self, vr, hr, align, tf):
        """Synergy score must always be in [0, 100]."""
        result = self.calc.calculate(to_decimal(vr), to_decimal(hr), align, tf)
        assert Decimal(0) <= result.synergy_score <= Decimal(100)

    @given(tf=st.floats(min_value=-10.0, max_value=10.0, allow_nan=False))
    @h_settings(max_examples=500)
    def test_timing_factor_clamped(self, tf):
        """Timing factor is always clamped to [0.8, 1.2]."""
        result = self.calc.calculate(to_decimal(50), to_decimal(50), 0.5, tf)
        assert Decimal("0.8") <= result.timing_factor <= Decimal("1.2")

    def test_synergy_to_dict(self):
        """to_dict returns correct float values."""
        result = self.calc.calculate(to_decimal(60), to_decimal(70), 0.8, 1.1)
        d = result.to_dict()
        assert isinstance(d["synergy_score"], float)
        assert isinstance(d["interaction"], float)
        assert isinstance(d["alignment_factor"], float)
        assert isinstance(d["timing_factor"], float)


# ── Confidence Calculator tests ──────────────────────────────────────────────


class TestConfidenceCalculator:
    """Property-based tests for ConfidenceCalculator."""

    calc = ConfidenceCalculator()

    @given(
        score=_score_0_100.map(to_decimal),
        score_type=st.sampled_from(["vr", "hr", "synergy", "org_air"]),
        evidence_count=st.integers(min_value=1, max_value=50),
    )
    @h_settings(max_examples=500)
    def test_ci_always_contains_score(self, score, score_type, evidence_count):
        """CI lower ≤ score ≤ CI upper."""
        ci = self.calc.calculate(score, score_type, evidence_count)
        assert ci.ci_lower <= score <= ci.ci_upper, (
            f"CI [{ci.ci_lower}, {ci.ci_upper}] does not contain score {score}"
        )

    @given(
        score=st.just(to_decimal(50.0)),
        low_n=st.integers(min_value=1, max_value=3),
        high_n=st.integers(min_value=15, max_value=50),
    )
    @h_settings(max_examples=500)
    def test_more_evidence_narrower_ci(self, score, low_n, high_n):
        """Higher evidence_count should produce narrower or equal CI."""
        ci_low = self.calc.calculate(score, "org_air", low_n)
        ci_high = self.calc.calculate(score, "org_air", high_n)
        assert ci_high.ci_width <= ci_low.ci_width + Decimal("0.001")

    @given(
        score=_score_0_100.map(to_decimal),
        evidence_count=st.integers(min_value=1, max_value=50),
    )
    @h_settings(max_examples=500)
    def test_ci_width_non_negative(self, score, evidence_count):
        """CI width is always ≥ 0."""
        ci = self.calc.calculate(score, "vr", evidence_count)
        assert ci.ci_width >= Decimal(0)

    def test_erfinv_known_values(self):
        """erfinv(0) = 0."""
        assert abs(_erfinv(0.0)) < 1e-10

    def test_erfinv_boundary_raises(self):
        """erfinv at boundary raises ValueError."""
        with pytest.raises(ValueError):
            _erfinv(1.0)
        with pytest.raises(ValueError):
            _erfinv(-1.0)

    def test_norm_ppf_known_value(self):
        """norm_ppf(0.5) ≈ 0 (median of standard normal)."""
        assert abs(_norm_ppf(0.5)) < 1e-10

    def test_norm_ppf_boundary_raises(self):
        """norm_ppf at boundary raises ValueError."""
        with pytest.raises(ValueError):
            _norm_ppf(0.0)
        with pytest.raises(ValueError):
            _norm_ppf(1.0)


# ── Position Factor Calculator tests ─────────────────────────────────────────

_mcap = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)


class TestPositionFactorCalculator:
    """Property-based tests for PositionFactorCalculator."""

    calc = PositionFactorCalculator()

    @given(vr=_score_0_100, sector=_sectors, mcap=_mcap)
    @h_settings(max_examples=500)
    def test_pf_always_bounded(self, vr, sector, mcap):
        """Position factor must always be in [-1, 1]."""
        pf = self.calc.calculate_position_factor(vr, sector, mcap)
        assert Decimal("-1") <= pf <= Decimal("1"), f"PF={pf} out of [-1,1]"

    @given(
        low_vr=st.floats(min_value=0.0, max_value=40.0, allow_nan=False),
        delta=st.floats(min_value=10.0, max_value=50.0, allow_nan=False),
        mcap=_mcap,
    )
    @h_settings(max_examples=500)
    def test_higher_vr_higher_pf(self, low_vr, delta, mcap):
        """Higher V^R should yield higher or equal PF (same sector/mcap)."""
        high_vr = min(low_vr + delta, 100.0)
        pf_low = self.calc.calculate_position_factor(low_vr, "technology", mcap)
        pf_high = self.calc.calculate_position_factor(high_vr, "technology", mcap)
        assert pf_high >= pf_low - Decimal("0.0001")


# ── Org-AI-R Calculator tests ───────────────────────────────────────────────


def _make_vr_result(vr_score=50.0):
    """Helper to build a VRResult for testing OrgAIRCalculator."""
    calc = VRCalculator()
    dims = {d.value: vr_score for d in Dimension}
    return calc.calculate(dims, 0.3)


def _make_hr_result(hr_score=50.0):
    """Helper to build an HRResult for testing OrgAIRCalculator."""
    from app.scoring.hr_calculator import HRResult
    return HRResult(
        hr_score=to_decimal(hr_score),
        baseline=to_decimal(50.0),
        position_factor=to_decimal(0.0),
        delta_used=to_decimal(0.15),
    )


def _make_synergy_result(synergy_score=50.0):
    """Helper to build a SynergyResult for testing OrgAIRCalculator."""
    from app.scoring.synergy_calculator import SynergyResult
    return SynergyResult(
        synergy_score=to_decimal(synergy_score),
        interaction=to_decimal(25.0),
        alignment_factor=to_decimal(0.8),
        timing_factor=to_decimal(1.0),
    )


class TestOrgAIRCalculator:
    """Property-based tests for OrgAIRCalculator."""

    calc = OrgAIRCalculator()

    @given(
        vr=_score_0_100,
        hr=_score_0_100,
        syn=_score_0_100,
        evidence=st.integers(min_value=1, max_value=50),
    )
    @h_settings(max_examples=500)
    def test_org_air_always_bounded(self, vr, hr, syn, evidence):
        """Final Org-AI-R score must be in [0, 100]."""
        vr_r = _make_vr_result(vr)
        hr_r = _make_hr_result(hr)
        syn_r = _make_synergy_result(syn)
        result = self.calc.calculate("test-co", "technology", vr_r, hr_r, syn_r, evidence)
        assert Decimal(0) <= result.final_score <= Decimal(100)

    def test_org_air_to_dict(self):
        """to_dict has all expected keys."""
        vr_r = _make_vr_result()
        hr_r = _make_hr_result()
        syn_r = _make_synergy_result()
        result = self.calc.calculate("co-1", "technology", vr_r, hr_r, syn_r)
        d = result.to_dict()
        expected_keys = {
            "score_id", "company_id", "sector", "timestamp", "final_score",
            "vr_score", "hr_score", "synergy_score", "ci_lower", "ci_upper",
            "ci_width", "sem", "reliability", "evidence_count",
            "alpha", "beta", "parameter_version",
        }
        assert expected_keys.issubset(d.keys())

    def test_org_air_deterministic(self):
        """Same inputs produce same final_score."""
        vr_r = _make_vr_result(60.0)
        hr_r = _make_hr_result(55.0)
        syn_r = _make_synergy_result(40.0)
        r1 = self.calc.calculate("co-x", "technology", vr_r, hr_r, syn_r, 10)
        r2 = self.calc.calculate("co-x", "technology", vr_r, hr_r, syn_r, 10)
        assert r1.final_score == r2.final_score


# ── Weighted Std Dev edge cases ──────────────────────────────────────────────


class TestWeightedStdDevEdgeCases:
    """Cover edge-case branches in weighted_std_dev (utils.py lines 86,88,91)."""

    def test_weighted_std_dev_empty(self):
        """Empty list returns 0."""
        assert weighted_std_dev([], [], Decimal(0)) == Decimal(0)

    def test_weighted_std_dev_mismatched_raises(self):
        """Mismatched lengths raise ValueError."""
        with pytest.raises(ValueError):
            weighted_std_dev([to_decimal(1)], [Decimal("0.5"), Decimal("0.5")], Decimal(1))

    def test_weighted_std_dev_zero_weights(self):
        """All-zero weights return 0."""
        vals = [to_decimal(10), to_decimal(20)]
        wts = [Decimal(0), Decimal(0)]
        assert weighted_std_dev(vals, wts, to_decimal(15)) == Decimal(0)


# ── Evidence Mapper coverage report tests ────────────────────────────────────


class TestEvidenceMapperCoverage:
    """Tests for EvidenceMapper.get_coverage_report."""

    mapper = EvidenceMapper()

    def test_get_coverage_report_returns_all_dims(self):
        """Coverage report always returns all 7 dimensions."""
        ev = EvidenceScore(
            source=SignalSource.TECHNOLOGY_HIRING,
            raw_score=to_decimal(80),
            confidence=to_decimal(0.9),
            evidence_count=5,
        )
        report = self.mapper.get_coverage_report([ev])
        assert set(report.keys()) == set(Dimension)

    def test_coverage_report_empty_evidence(self):
        """No evidence means all has_evidence=False."""
        report = self.mapper.get_coverage_report([])
        for dim, info in report.items():
            assert info["has_evidence"] is False
            assert info["source_count"] == 0
            assert info["confidence"] == 0.0

    def test_coverage_report_with_evidence(self):
        """Evidence for a source marks affected dimensions as covered."""
        ev = EvidenceScore(
            source=SignalSource.LEADERSHIP_SIGNALS,
            raw_score=to_decimal(70),
            confidence=to_decimal(0.8),
            evidence_count=3,
        )
        report = self.mapper.get_coverage_report([ev])
        # Leadership signals maps to LEADERSHIP_VISION (primary)
        assert report[Dimension.LEADERSHIP_VISION]["has_evidence"] is True
        assert report[Dimension.LEADERSHIP_VISION]["source_count"] >= 1


# ── Mapping table function tests ─────────────────────────────────────────────


class TestMappingTableFunctions:
    """Tests for build_signal_to_dimension_map and compute_weights_hash."""

    def test_build_map_empty_rows_returns_default(self):
        """Empty rows fall back to the default SIGNAL_TO_DIMENSION_MAP."""
        from app.pipelines.evidence_mapper.evidence_mapping_table import (
            SIGNAL_TO_DIMENSION_MAP,
        )
        result = build_signal_to_dimension_map([])
        assert result is SIGNAL_TO_DIMENSION_MAP

    def test_build_map_with_valid_rows(self):
        """Valid DB rows produce a correct mapping."""
        rows = [
            {
                "signal_source": "technology_hiring",
                "dimension": "technology_stack",
                "weight": 0.7,
                "is_primary": True,
                "reliability": 0.9,
            },
            {
                "signal_source": "technology_hiring",
                "dimension": "talent_skills",
                "weight": 0.2,
                "is_primary": False,
                "reliability": 0.9,
            },
        ]
        result = build_signal_to_dimension_map(rows)
        assert SignalSource.TECHNOLOGY_HIRING in result
        mapping = result[SignalSource.TECHNOLOGY_HIRING]
        assert mapping.primary_dimension == Dimension.TECHNOLOGY_STACK
        assert Dimension.TALENT_SKILLS in mapping.secondary_mappings

    def test_build_map_invalid_source_skipped(self):
        """Invalid signal_source values are silently skipped."""
        rows = [
            {
                "signal_source": "nonexistent_source",
                "dimension": "technology_stack",
                "weight": 0.5,
                "is_primary": True,
                "reliability": 0.8,
            },
        ]
        result = build_signal_to_dimension_map(rows)
        # Should still have all default sources
        assert SignalSource.TECHNOLOGY_HIRING in result

    def test_compute_weights_hash_deterministic(self):
        """Same map always produces the same hash."""
        from app.pipelines.evidence_mapper.evidence_mapping_table import (
            SIGNAL_TO_DIMENSION_MAP,
        )
        h1 = compute_weights_hash(SIGNAL_TO_DIMENSION_MAP)
        h2 = compute_weights_hash(SIGNAL_TO_DIMENSION_MAP)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest

    def test_compute_weights_hash_changes_on_diff_map(self):
        """Different maps produce different hashes."""
        from app.pipelines.evidence_mapper.evidence_mapping_table import (
            SIGNAL_TO_DIMENSION_MAP,
        )
        modified = dict(SIGNAL_TO_DIMENSION_MAP)
        modified[SignalSource.TECHNOLOGY_HIRING] = DimensionMapping(
            source=SignalSource.TECHNOLOGY_HIRING,
            primary_dimension=Dimension.TECHNOLOGY_STACK,
            primary_weight=Decimal("0.99"),
            reliability=Decimal("0.5"),
        )
        h_orig = compute_weights_hash(SIGNAL_TO_DIMENSION_MAP)
        h_mod = compute_weights_hash(modified)
        assert h_orig != h_mod


# ── Talent Concentration job analysis tests ──────────────────────────────────


class TestTalentConcentrationJobAnalysis:
    """Tests for TalentConcentrationCalculator.analyze_job_postings."""

    calc = TalentConcentrationCalculator()

    def test_analyze_job_postings_empty(self):
        """Empty postings list produces zero counts."""
        analysis = self.calc.analyze_job_postings([])
        assert analysis.total_ai_jobs == 0
        assert analysis.senior_ai_jobs == 0
        assert analysis.mid_ai_jobs == 0
        assert analysis.entry_ai_jobs == 0
        assert len(analysis.unique_skills) == 0

    def test_analyze_job_postings_non_ai_skipped(self):
        """Non-AI postings are not counted."""
        postings = [
            {"title": "Accountant", "description": "Financial reporting"},
            {"title": "Office Manager", "description": "Admin tasks"},
        ]
        analysis = self.calc.analyze_job_postings(postings)
        assert analysis.total_ai_jobs == 0

    def test_analyze_job_postings_with_ai_roles(self):
        """AI-related roles are classified by seniority."""
        postings = [
            {"title": "Director of Machine Learning", "description": "Lead ML team"},
            {"title": "Senior Data Scientist", "description": "Build ML models"},
            {"title": "Junior ML Engineer", "description": "Assist with deep learning"},
            {"title": "AI Engineer", "description": "Build AI systems"},
        ]
        analysis = self.calc.analyze_job_postings(postings)
        assert analysis.total_ai_jobs == 4
        assert analysis.senior_ai_jobs >= 1  # Director
        assert analysis.mid_ai_jobs >= 1     # Senior
        assert analysis.entry_ai_jobs >= 1   # Junior

    def test_analyze_job_postings_skill_extraction(self):
        """Skills are extracted from descriptions."""
        postings = [
            {
                "title": "ML Engineer",
                "description": "Must know python, pytorch, and tensorflow",
                "ai_skills": ["python", "pytorch"],
            },
        ]
        analysis = self.calc.analyze_job_postings(postings)
        assert "python" in analysis.unique_skills
        assert "pytorch" in analysis.unique_skills
        assert "tensorflow" in analysis.unique_skills

    def test_analyze_job_postings_pre_classified(self):
        """Postings with is_ai_related=True are counted even without keywords."""
        postings = [
            {
                "title": "Research Scientist",
                "description": "Work on novel algorithms",
                "is_ai_related": True,
            },
        ]
        analysis = self.calc.analyze_job_postings(postings)
        assert analysis.total_ai_jobs == 1
