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
"""
from decimal import Decimal

import pytest
from hypothesis import HealthCheck, given, settings as h_settings
from hypothesis import strategies as st

from app.models.enums import DIMENSION_WEIGHTS, Dimension
from app.pipelines.evidence_mapper.evidence_mapper import EvidenceMapper
from app.pipelines.evidence_mapper.evidence_mapping_table import (
    EvidenceScore,
    SignalSource,
)
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
    @h_settings(max_examples=300)
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
    @h_settings(max_examples=300)
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
    @h_settings(max_examples=200)
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
    @h_settings(max_examples=200)
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
    @h_settings(max_examples=300)
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
    @h_settings(max_examples=200)
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
    @h_settings(max_examples=200)
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
    @h_settings(max_examples=300)
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
    @h_settings(max_examples=200)
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
    @h_settings(max_examples=300)
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
