"""Column effective length, radius of gyration, and slenderness."""

from enum import Enum
from math import isfinite, sqrt

from column_analysis.sections import SectionProperties


class EndCondition(str, Enum):
    """Idealized column end conditions supported by the project."""

    PINNED_PINNED = "pinned-pinned"
    FIXED_FIXED = "fixed-fixed"
    FIXED_FREE = "fixed-free"
    FIXED_PINNED = "fixed-pinned"


_END_CONDITION_FACTORS = {
    EndCondition.PINNED_PINNED: 1.0,
    EndCondition.FIXED_FIXED: 0.5,
    EndCondition.FIXED_FREE: 2.0,
    EndCondition.FIXED_PINNED: 0.699,
}


def _validate_positive_finite(name: str, value: float) -> None:
    """Require a finite, positive numeric input."""
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive value.")


def effective_length_factor(end_condition: EndCondition | str) -> float:
    """Return K for an idealized end condition.

    The fixed-pinned factor, 0.699, is an approximation. Real supports may
    not behave exactly like these idealized conditions.
    """
    try:
        resolved_condition = EndCondition(end_condition)
    except (TypeError, ValueError):
        supported_conditions = ", ".join(condition.value for condition in EndCondition)
        raise ValueError(
            f"Unsupported end condition {end_condition!r}. Choose from: {supported_conditions}."
        ) from None

    return _END_CONDITION_FACTORS[resolved_condition]


def effective_length(length_m: float, end_condition: EndCondition | str) -> float:
    """Calculate effective length ``Le = K * L`` in metres."""
    _validate_positive_finite("length_m", length_m)

    effective_length_m = effective_length_factor(end_condition) * length_m
    _validate_positive_finite("effective_length_m", effective_length_m)
    return effective_length_m


def radius_of_gyration(section: SectionProperties) -> float:
    """Return the least radius of gyration in metres for a section.

    The section's minimum second moment of area is used, so a rectangular
    section is evaluated about its weaker axis.
    """
    _validate_positive_finite("area_m2", section.area_m2)
    _validate_positive_finite(
        "minimum_second_moment_m4", section.minimum_second_moment_m4
    )

    radius_of_gyration_m = sqrt(section.minimum_second_moment_m4 / section.area_m2)
    _validate_positive_finite("radius_of_gyration_m", radius_of_gyration_m)
    return radius_of_gyration_m


def slenderness_ratio(effective_length_m: float, radius_of_gyration_m: float) -> float:
    """Calculate the dimensionless slenderness ratio ``lambda = Le / k``."""
    _validate_positive_finite("effective_length_m", effective_length_m)
    _validate_positive_finite("radius_of_gyration_m", radius_of_gyration_m)

    ratio = effective_length_m / radius_of_gyration_m
    _validate_positive_finite("slenderness_ratio", ratio)
    return ratio