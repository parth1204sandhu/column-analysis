"""Syllabus-approved column theory calculations."""

from math import isfinite, pi


def _validate_positive_finite(name: str, value: float, unit: str) -> None:
    """Require a finite, strictly positive input with the given unit."""
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite, strictly positive value in {unit}.")


def euler_critical_load(
    youngs_modulus_pa: float,
    minimum_second_moment_m4: float,
    effective_length_m: float,
) -> float:
    """Calculate Euler's critical buckling load in newtons.

    Uses ``P_E = pi^2 * E * I_min / Le^2`` with Young's modulus in Pa,
    minimum second moment of area in m^4, and effective length in metres.
    Euler's formula assumes an ideal, sufficiently slender elastic column
    and has limitations. This function calculates the formula only; it does
    not decide whether those applicability assumptions are met.
    """
    _validate_positive_finite("youngs_modulus_pa", youngs_modulus_pa, "Pa")
    _validate_positive_finite(
        "minimum_second_moment_m4", minimum_second_moment_m4, "m^4"
    )
    _validate_positive_finite("effective_length_m", effective_length_m, "m")

    critical_load_n = (
        pi**2 * youngs_modulus_pa * minimum_second_moment_m4 / effective_length_m**2
    )
    _validate_positive_finite("euler_critical_load_n", critical_load_n, "N")
    return critical_load_n


def rankine_critical_load(
    compressive_strength_pa: float,
    area_m2: float,
    rankine_constant_dimensionless: float,
    effective_length_m: float,
    least_radius_of_gyration_m: float,
) -> float:
    """Calculate Rankine-Gordon critical load in newtons.

    Uses ``P_R = sigma_c * A / (1 + a * (Le / k)^2)`` with compressive
    strength in Pa, area in m^2, effective length and least radius of
    gyration in metres. For this form, ``a`` must be dimensionless because
    ``Le / k`` is dimensionless. Supply the empirical constant explicitly
    from the selected course or reference; no universal value is assumed.
    If that reference uses a different convention or notation, confirm it
    before applying this function.
    """
    _validate_positive_finite("compressive_strength_pa", compressive_strength_pa, "Pa")
    _validate_positive_finite("area_m2", area_m2, "m^2")
    _validate_positive_finite(
        "rankine_constant_dimensionless", rankine_constant_dimensionless, "dimensionless"
    )
    _validate_positive_finite("effective_length_m", effective_length_m, "m")
    _validate_positive_finite(
        "least_radius_of_gyration_m", least_radius_of_gyration_m, "m"
    )

    slenderness_ratio = effective_length_m / least_radius_of_gyration_m
    denominator = 1 + rankine_constant_dimensionless * slenderness_ratio**2
    critical_load_n = compressive_strength_pa * area_m2 / denominator
    _validate_positive_finite("rankine_critical_load_n", critical_load_n, "N")
    return critical_load_n


def johnson_critical_load(
    yield_stress_pa: float,
    youngs_modulus_pa: float,
    area_m2: float,
    effective_length_m: float,
    least_radius_of_gyration_m: float,
) -> float:
    """Calculate Johnson's parabolic critical load in newtons.

    Uses the course-confirmed form ``sigma_cr = sigma_y * (1 -
    (sigma_y / (4 * pi^2 * E)) * (Le / k)^2)`` and ``P_J = A * sigma_cr``.
    Inputs use SI units: yield stress and Young's modulus in Pa, area in
    m^2, and effective length and least radius of gyration in metres. The
    formula assumes the supplied yield stress definition and does not
    classify applicability; no universal slenderness boundary is applied.
    """
    _validate_positive_finite("yield_stress_pa", yield_stress_pa, "Pa")
    _validate_positive_finite("youngs_modulus_pa", youngs_modulus_pa, "Pa")
    _validate_positive_finite("area_m2", area_m2, "m^2")
    _validate_positive_finite("effective_length_m", effective_length_m, "m")
    _validate_positive_finite(
        "least_radius_of_gyration_m", least_radius_of_gyration_m, "m"
    )

    slenderness_ratio = effective_length_m / least_radius_of_gyration_m
    reduction_fraction = (
        yield_stress_pa / (4 * pi**2 * youngs_modulus_pa)
    ) * slenderness_ratio**2
    critical_stress_pa = yield_stress_pa * (1 - reduction_fraction)

    if not isfinite(critical_stress_pa) or critical_stress_pa <= 0:
        raise ValueError(
            "Johnson critical stress is non-positive or non-finite; "
            "the formula is outside its meaningful range for these inputs."
        )

    critical_load_n = area_m2 * critical_stress_pa
    _validate_positive_finite("johnson_critical_load_n", critical_load_n, "N")
    return critical_load_n