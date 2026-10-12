"""Data generation for critical-load versus slenderness plots."""

from collections.abc import Iterable

from column_analysis.properties import radius_of_gyration
from column_analysis.sections import SectionProperties
from column_analysis.theories import (
    euler_critical_load,
    johnson_critical_load,
    rankine_critical_load,
)
from column_analysis.validation import validate_engineering_inputs, validate_positive_finite


def build_slenderness_curve_data(
    slenderness_ratios: Iterable[float],
    section_properties: SectionProperties,
    *,
    youngs_modulus_pa: float | None = None,
    compressive_strength_pa: float | None = None,
    rankine_constant_dimensionless: float | None = None,
    yield_stress_pa: float | None = None,
) -> dict[str, list[float | None]]:
    """Calculate available theory loads for each requested slenderness value.

    The effective length for each point is obtained from ``Le = lambda * k``.
    All critical-load calculations are delegated to the existing theory
    functions. Missing material inputs produce ``None`` values, and
    Johnson points without a positive physical result are also ``None``.
    """
    ratio_values = tuple(slenderness_ratios)
    if not ratio_values:
        raise ValueError("Provide at least one slenderness ratio for the graph.")
    for ratio in ratio_values:
        validate_positive_finite("slenderness_ratio", ratio, "dimensionless")

    supplied_inputs = {
        name: value
        for name, value in (
            ("youngs_modulus_pa", youngs_modulus_pa),
            ("compressive_strength_pa", compressive_strength_pa),
            ("rankine_constant_dimensionless", rankine_constant_dimensionless),
            ("yield_stress_pa", yield_stress_pa),
        )
        if value is not None
    }
    if supplied_inputs:
        validate_engineering_inputs(supplied_inputs)

    radius_of_gyration_m = radius_of_gyration(section_properties)
    curve_data: dict[str, list[float | None]] = {
        "Euler": [],
        "Rankine-Gordon": [],
        "Johnson": [],
    }

    for ratio in ratio_values:
        effective_length_m = ratio * radius_of_gyration_m
        validate_positive_finite("effective_length_m", effective_length_m, "m")

        if youngs_modulus_pa is None:
            curve_data["Euler"].append(None)
        else:
            curve_data["Euler"].append(
                euler_critical_load(
                    youngs_modulus_pa,
                    section_properties.minimum_second_moment_m4,
                    effective_length_m,
                )
            )

        if compressive_strength_pa is None or rankine_constant_dimensionless is None:
            curve_data["Rankine-Gordon"].append(None)
        else:
            curve_data["Rankine-Gordon"].append(
                rankine_critical_load(
                    compressive_strength_pa,
                    section_properties.area_m2,
                    rankine_constant_dimensionless,
                    effective_length_m,
                    radius_of_gyration_m,
                )
            )

        if youngs_modulus_pa is None or yield_stress_pa is None:
            curve_data["Johnson"].append(None)
        else:
            try:
                johnson_load_n = johnson_critical_load(
                    yield_stress_pa,
                    youngs_modulus_pa,
                    section_properties.area_m2,
                    effective_length_m,
                    radius_of_gyration_m,
                )
            except (ValueError, OverflowError):
                curve_data["Johnson"].append(None)
            else:
                curve_data["Johnson"].append(johnson_load_n)

    return curve_data