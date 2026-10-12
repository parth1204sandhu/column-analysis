"""Input validation and provisional theory-applicability assessments."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from math import isfinite


_ENGINEERING_INPUT_UNITS = {
    "column_length_m": "m",
    "effective_length_m": "m",
    "area_m2": "m^2",
    "minimum_second_moment_m4": "m^4",
    "youngs_modulus_pa": "Pa",
    "yield_stress_pa": "Pa",
    "compressive_strength_pa": "Pa",
    "least_radius_of_gyration_m": "m",
    "factor_of_safety": "dimensionless",
    "rankine_constant_dimensionless": "dimensionless",
}


class TheoryName(str, Enum):
    """Column theories currently supported by this project."""

    EULER = "Euler"
    RANKINE = "Rankine"
    JOHNSON = "Johnson"


class ApplicabilityStatus(str, Enum):
    """A conservative summary that does not imply unverified applicability."""

    CRITERION_NOT_CONFIGURED = "criterion not configured"
    INPUT_REQUIRED = "input required"
    PROVISIONAL = "provisional"


@dataclass(frozen=True)
class TheoryApplicabilityAssessment:
    """Display-ready theory name, applicability status, and explanation."""

    theory: TheoryName
    status: ApplicabilityStatus
    message: str


def validate_positive_finite(name: str, value: float, unit: str) -> None:
    """Raise ``ValueError`` unless a value is finite and strictly positive."""
    try:
        if isfinite(value) and value > 0:
            return
    except TypeError:
        pass

    raise ValueError(f"{name} must be a finite, strictly positive value in {unit}.")


def validate_engineering_inputs(inputs: Mapping[str, float]) -> None:
    """Validate supplied engineering inputs using their expected SI units.

    Pass only values relevant to the selected calculation. Supported keys
    include lengths, area, minimum second moment, material properties,
    radius of gyration, factor of safety, and the dimensionless Rankine
    constant. Missing optional inputs are not inferred or defaulted.
    """
    if not inputs:
        raise ValueError("Provide at least one engineering input to validate.")

    for name, value in inputs.items():
        try:
            unit = _ENGINEERING_INPUT_UNITS[name]
        except KeyError:
            raise ValueError(f"Unsupported engineering input {name!r}.") from None

        validate_positive_finite(name, value, unit)


def assess_theory_applicability(
    theory: TheoryName | str,
    *,
    rankine_constant_dimensionless: float | None = None,
) -> TheoryApplicabilityAssessment:
    """Return theory assumptions and any missing course-specific criteria.

    No universal slenderness boundary is applied. Euler and Johnson stay
    unconfirmed until a course-specific criterion is configured. Rankine
    requires an explicit empirical constant; supplying one remains
    provisional until its value and convention are checked against the
    course reference.
    """
    try:
        resolved_theory = TheoryName(theory)
    except (TypeError, ValueError):
        supported_theories = ", ".join(item.value for item in TheoryName)
        raise ValueError(f"Unsupported theory {theory!r}. Choose from: {supported_theories}.") from None

    if resolved_theory is TheoryName.EULER:
        return TheoryApplicabilityAssessment(
            theory=resolved_theory,
            status=ApplicabilityStatus.CRITERION_NOT_CONFIGURED,
            message=(
                "Euler assumes a sufficiently slender, elastic column with idealized end "
                "conditions. The course-specific slenderness criterion is not configured, "
                "so applicability is not confirmed."
            ),
        )

    if resolved_theory is TheoryName.JOHNSON:
        return TheoryApplicabilityAssessment(
            theory=resolved_theory,
            status=ApplicabilityStatus.CRITERION_NOT_CONFIGURED,
            message=(
                "Johnson's parabolic formula is intended for the lower-slenderness, "
                "intermediate-column region. The course-specific range is not configured, "
                "so applicability is not confirmed."
            ),
        )

    if rankine_constant_dimensionless is None:
        return TheoryApplicabilityAssessment(
            theory=resolved_theory,
            status=ApplicabilityStatus.INPUT_REQUIRED,
            message=(
                "Rankine combines crushing and buckling effects. Supply the empirical "
                "Rankine constant using the course/reference's value and convention; "
                "no default is assumed."
            ),
        )

    validate_positive_finite(
        "rankine_constant_dimensionless",
        rankine_constant_dimensionless,
        "dimensionless",
    )
    return TheoryApplicabilityAssessment(
        theory=resolved_theory,
        status=ApplicabilityStatus.PROVISIONAL,
        message=(
            "Rankine combines crushing and buckling effects. Verify the supplied "
            "empirical constant and its convention against the course/reference; "
            "this assessment does not certify applicability."
        ),
    )