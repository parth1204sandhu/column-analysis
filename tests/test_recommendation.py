from dataclasses import replace

import pytest

from column_analysis.recommendation import (
    load_applicability_criteria,
    recommend_theory,
)
from column_analysis.validation import ApplicabilityStatus, TheoryName


def _configured_criteria(
    *,
    johnson_minimum: float | None = 20.0,
    rankine_range: tuple[float, float] | None = None,
    rankine_constant: float | None = None,
    preference: tuple[TheoryName, ...] = (),
):
    criteria = load_applicability_criteria()
    return replace(
        criteria,
        johnson_minimum_slenderness_ratio=johnson_minimum,
        johnson_range_reference=(
            "Test-only configured course criterion"
            if johnson_minimum is not None
            else None
        ),
        johnson_range_reference_url=(
            "https://example.org/johnson-range"
            if johnson_minimum is not None
            else None
        ),
        rankine_minimum_slenderness_ratio=(
            rankine_range[0] if rankine_range is not None else None
        ),
        rankine_maximum_slenderness_ratio=(
            rankine_range[1] if rankine_range is not None else None
        ),
        rankine_constant_dimensionless=rankine_constant,
        rankine_reference=(
            "Test-only configured Rankine course criterion"
            if rankine_range is not None
            else None
        ),
        rankine_reference_url=(
            "https://example.org/rankine-range"
            if rankine_range is not None
            else None
        ),
        preferred_theory_order=preference,
    )


def _complete_inputs(**overrides):
    inputs = {
        "youngs_modulus_gpa": 200.0,
        "compressive_strength_mpa": 250.0,
        "rankine_constant_dimensionless": 0.001,
        "yield_stress_mpa": 250.0,
    }
    inputs.update(overrides)
    return inputs


def test_configured_transition_recommends_euler_for_long_columns() -> None:
    result = recommend_theory(
        200.0,
        **_complete_inputs(),
        criteria=_configured_criteria(),
    )

    reviews = {review.theory: review for review in result.theory_reviews}
    assert result.recommended_theory is TheoryName.EULER
    assert result.candidate_theories == (TheoryName.EULER,)
    assert result.euler_johnson_transition_ratio == pytest.approx(125.663706)
    assert reviews[TheoryName.EULER].status is ApplicabilityStatus.APPLICABLE
    assert reviews[TheoryName.JOHNSON].status is ApplicabilityStatus.OUT_OF_RANGE
    assert "not by comparing predicted loads" in result.explanation


def test_configured_johnson_range_recommends_intermediate_columns() -> None:
    result = recommend_theory(
        80.0,
        **_complete_inputs(),
        criteria=_configured_criteria(),
    )

    reviews = {review.theory: review for review in result.theory_reviews}
    assert result.recommended_theory is TheoryName.JOHNSON
    assert reviews[TheoryName.JOHNSON].status is ApplicabilityStatus.APPLICABLE
    assert "Test-only configured course criterion" == reviews[TheoryName.JOHNSON].supporting_reference


def test_default_johnson_criterion_recommends_at_slenderness_60() -> None:
    criteria = load_applicability_criteria()
    result = recommend_theory(
        60.0,
        **_complete_inputs(),
        criteria=criteria,
    )

    review = next(
        review for review in result.theory_reviews if review.theory is TheoryName.JOHNSON
    )
    assert criteria.johnson_minimum_slenderness_ratio == 0.0
    assert result.recommended_theory is TheoryName.JOHNSON
    assert review.status is ApplicabilityStatus.APPLICABLE
    assert "not a certification of short-column behavior" in review.explanation
    assert "verified compressive strength separately" in review.explanation


def test_short_column_is_not_mislabeled_when_criteria_have_a_lower_boundary() -> None:
    result = recommend_theory(
        10.0,
        **_complete_inputs(),
        criteria=_configured_criteria(johnson_minimum=20.0),
    )

    reviews = {review.theory: review for review in result.theory_reviews}
    assert result.recommended_theory is None
    assert "Insufficient information to recommend" in result.explanation
    assert reviews[TheoryName.JOHNSON].status is ApplicabilityStatus.OUT_OF_RANGE


def test_johnson_is_not_recommended_without_a_sourced_lower_boundary() -> None:
    result = recommend_theory(
        80.0,
        **_complete_inputs(),
        criteria=_configured_criteria(johnson_minimum=None),
    )

    review = next(
        review for review in result.theory_reviews if review.theory is TheoryName.JOHNSON
    )
    assert result.recommended_theory is None
    assert review.status is ApplicabilityStatus.CRITERION_NOT_CONFIGURED
    assert review.missing_inputs == (
        "Johnson lower slenderness boundary and its source",
    )


def test_missing_material_properties_are_named_for_each_theory() -> None:
    result = recommend_theory(
        200.0,
        youngs_modulus_gpa=None,
        compressive_strength_mpa=None,
        rankine_constant_dimensionless=None,
        yield_stress_mpa=None,
        criteria=_configured_criteria(),
    )

    reviews = {review.theory: review for review in result.theory_reviews}
    assert result.recommended_theory is None
    assert reviews[TheoryName.EULER].missing_inputs == (
        "Young's modulus E",
        "yield stress sigma_y",
    )
    assert reviews[TheoryName.JOHNSON].missing_inputs == (
        "Young's modulus E",
        "yield stress sigma_y",
    )
    assert "compressive/crushing strength sigma_c" in reviews[TheoryName.RANKINE].missing_inputs
    assert "Rankine constant a" in reviews[TheoryName.RANKINE].missing_inputs


def test_rankine_needs_reference_criteria_and_matching_constant() -> None:
    default_criteria = _configured_criteria()
    unconfigured = recommend_theory(
        10.0,
        **_complete_inputs(),
        criteria=default_criteria,
    )
    unconfigured_reviews = {
        review.theory: review for review in unconfigured.theory_reviews
    }
    assert unconfigured_reviews[TheoryName.RANKINE].status is (
        ApplicabilityStatus.CRITERION_NOT_CONFIGURED
    )

    criteria = _configured_criteria(
        rankine_range=(1.0, 50.0),
        rankine_constant=0.001,
    )
    result = recommend_theory(
        10.0,
        **_complete_inputs(),
        criteria=criteria,
    )
    reviews = {review.theory: review for review in result.theory_reviews}
    assert result.recommended_theory is TheoryName.RANKINE
    assert reviews[TheoryName.RANKINE].status is ApplicabilityStatus.APPLICABLE

    mismatch = recommend_theory(
        10.0,
        **_complete_inputs(rankine_constant_dimensionless=0.002),
        criteria=criteria,
    )
    mismatch_review = next(
        review
        for review in mismatch.theory_reviews
        if review.theory is TheoryName.RANKINE
    )
    assert mismatch_review.status is ApplicabilityStatus.INPUT_REQUIRED
    assert "matching the configured reference" in mismatch_review.missing_inputs[0]


def test_overlapping_candidates_need_explicit_reference_preference() -> None:
    criteria = _configured_criteria(
        rankine_range=(50.0, 100.0),
        rankine_constant=0.001,
    )
    result = recommend_theory(80.0, **_complete_inputs(), criteria=criteria)
    assert result.recommended_theory is None
    assert result.candidate_theories == (TheoryName.JOHNSON, TheoryName.RANKINE)
    assert "no reference-backed preference" in result.explanation

    preferred = _configured_criteria(
        rankine_range=(50.0, 100.0),
        rankine_constant=0.001,
        preference=(TheoryName.JOHNSON, TheoryName.RANKINE),
    )
    preferred_result = recommend_theory(
        80.0,
        **_complete_inputs(),
        criteria=preferred,
        critical_loads_n={
            TheoryName.JOHNSON: 100_000.0,
            TheoryName.RANKINE: 200_000.0,
        },
        applied_load_kn=150.0,
    )
    assert preferred_result.recommended_theory is TheoryName.JOHNSON
    assert preferred_result.critical_loads_n[TheoryName.JOHNSON] == 100_000.0
    assert preferred_result.applied_load_kn == 150.0


def test_invalid_rankine_constant_is_rejected() -> None:
    with pytest.raises(ValueError, match="rankine_constant_dimensionless must be"):
        recommend_theory(
            80.0,
            **_complete_inputs(rankine_constant_dimensionless=0.0),
            criteria=_configured_criteria(),
        )


@pytest.mark.parametrize(
    ("slenderness_ratio", "youngs_modulus_gpa"),
    [(0.0, 200.0), (-1.0, 200.0), (float("nan"), 200.0), (40.0, 0.0)],
)
def test_recommendation_rejects_non_positive_or_non_finite_inputs(
    slenderness_ratio: float,
    youngs_modulus_gpa: float,
) -> None:
    with pytest.raises(ValueError):
        recommend_theory(
            slenderness_ratio,
            **_complete_inputs(youngs_modulus_gpa=youngs_modulus_gpa),
        )


def test_reference_criteria_load_with_mathematical_johnson_lower_range_and_unconfigured_rankine() -> None:
    criteria = load_applicability_criteria()

    assert criteria.transition_rule == "euler_stress_equals_half_yield"
    assert criteria.transition_reference_url.endswith("#slenderness-ratio")
    assert criteria.johnson_minimum_slenderness_ratio == 0.0
    assert "mathematical lower limit" in criteria.johnson_range_reference
    assert criteria.johnson_range_reference_url.endswith("#intermediate-columns")
    assert criteria.rankine_minimum_slenderness_ratio is None
    assert criteria.rankine_constant_dimensionless is None
    assert criteria.rankine_constant_convention.startswith("P_R =")
