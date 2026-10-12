import pytest

from column_analysis.validation import (
    ApplicabilityStatus,
    TheoryName,
    assess_theory_applicability,
    validate_engineering_inputs,
)


VALID_INPUTS = {
    "column_length_m": 2.0,
    "effective_length_m": 2.0,
    "area_m2": 0.01,
    "minimum_second_moment_m4": 1e-6,
    "youngs_modulus_pa": 200e9,
    "yield_stress_pa": 250e6,
    "compressive_strength_pa": 250e6,
    "least_radius_of_gyration_m": 0.01,
    "factor_of_safety": 2.0,
    "rankine_constant_dimensionless": 0.001,
}


def test_validate_engineering_inputs_accepts_valid_si_values() -> None:
    validate_engineering_inputs(VALID_INPUTS)


@pytest.mark.parametrize(
    ("input_name", "unit"),
    [
        ("column_length_m", "m"),
        ("effective_length_m", "m"),
        ("area_m2", "m^2"),
        ("minimum_second_moment_m4", "m^4"),
        ("youngs_modulus_pa", "Pa"),
        ("yield_stress_pa", "Pa"),
        ("compressive_strength_pa", "Pa"),
        ("least_radius_of_gyration_m", "m"),
        ("factor_of_safety", "dimensionless"),
        ("rankine_constant_dimensionless", "dimensionless"),
    ],
)
@pytest.mark.parametrize("invalid_value", [0.0, -1.0, float("nan"), float("inf")])
def test_validate_engineering_inputs_rejects_invalid_values(
    input_name: str,
    unit: str,
    invalid_value: float,
) -> None:
    inputs = dict(VALID_INPUTS)
    inputs[input_name] = invalid_value

    with pytest.raises(ValueError) as error:
        validate_engineering_inputs(inputs)

    assert str(error.value) == (
        f"{input_name} must be a finite, strictly positive value in {unit}."
    )


def test_validate_engineering_inputs_rejects_unknown_names() -> None:
    with pytest.raises(ValueError, match="Unsupported engineering input 'unknown_value'"):
        validate_engineering_inputs({"unknown_value": 1.0})


def test_validate_engineering_inputs_rejects_empty_mapping() -> None:
    with pytest.raises(ValueError, match="Provide at least one engineering input"):
        validate_engineering_inputs({})


def test_euler_assessment_explains_assumptions_and_missing_criterion() -> None:
    assessment = assess_theory_applicability(TheoryName.EULER)

    assert assessment.status is ApplicabilityStatus.CRITERION_NOT_CONFIGURED
    assert "sufficiently slender" in assessment.message
    assert "elastic" in assessment.message
    assert "idealized end conditions" in assessment.message
    assert "criterion is not configured" in assessment.message


def test_johnson_assessment_explains_intended_region_and_missing_criterion() -> None:
    assessment = assess_theory_applicability("Johnson")

    assert assessment.status is ApplicabilityStatus.CRITERION_NOT_CONFIGURED
    assert "lower-slenderness" in assessment.message
    assert "intermediate-column" in assessment.message
    assert "range is not configured" in assessment.message


def test_rankine_assessment_requires_empirical_constant() -> None:
    assessment = assess_theory_applicability("Rankine")

    assert assessment.status is ApplicabilityStatus.INPUT_REQUIRED
    assert "crushing and buckling" in assessment.message
    assert "empirical Rankine constant" in assessment.message
    assert "no default" in assessment.message


def test_rankine_assessment_with_constant_remains_provisional() -> None:
    assessment = assess_theory_applicability(
        "Rankine",
        rankine_constant_dimensionless=0.001,
    )

    assert assessment.status is ApplicabilityStatus.PROVISIONAL
    assert "Verify the supplied empirical constant" in assessment.message
    assert "does not certify applicability" in assessment.message


def test_rankine_assessment_rejects_invalid_constant() -> None:
    with pytest.raises(ValueError, match="rankine_constant_dimensionless must be"):
        assess_theory_applicability("Rankine", rankine_constant_dimensionless=0.0)


def test_assessment_rejects_unknown_theory() -> None:
    with pytest.raises(ValueError, match="Unsupported theory 'Johnson modified'"):
        assess_theory_applicability("Johnson modified")