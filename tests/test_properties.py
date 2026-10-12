from math import sqrt

import pytest

from column_analysis.properties import (
    EndCondition,
    effective_length,
    effective_length_factor,
    radius_of_gyration,
    slenderness_ratio,
)
from column_analysis.sections import SectionProperties, rectangular_section, solid_circular_section


@pytest.mark.parametrize(
    ("end_condition", "expected_factor"),
    [
        ("pinned-pinned", 1.0),
        ("fixed-fixed", 0.5),
        ("fixed-free", 2.0),
        ("fixed-pinned", 0.699),
    ],
)
def test_effective_length_factor_for_each_end_condition(
    end_condition: str,
    expected_factor: float,
) -> None:
    assert effective_length_factor(end_condition) == pytest.approx(expected_factor)


@pytest.mark.parametrize(
    ("end_condition", "expected_effective_length_m"),
    [
        ("pinned-pinned", 3.0),
        ("fixed-fixed", 1.5),
        ("fixed-free", 6.0),
        ("fixed-pinned", 2.097),
    ],
)
def test_effective_length_applies_end_condition_factor(
    end_condition: str,
    expected_effective_length_m: float,
) -> None:
    assert effective_length(3.0, end_condition) == pytest.approx(expected_effective_length_m)


def test_effective_length_accepts_end_condition_enum() -> None:
    assert effective_length(2.0, EndCondition.FIXED_FIXED) == pytest.approx(1.0)


def test_circular_radius_of_gyration_is_in_metres() -> None:
    properties = solid_circular_section(diameter_m=0.08)

    assert radius_of_gyration(properties) == pytest.approx(0.02)


def test_rectangular_radius_uses_weaker_axis() -> None:
    width_m = 0.04
    height_m = 0.08
    properties = rectangular_section(width_m=width_m, height_m=height_m)

    assert properties.weaker_axis == "y"
    assert radius_of_gyration(properties) == pytest.approx(width_m / sqrt(12))


def test_slenderness_ratio_is_dimensionless() -> None:
    assert slenderness_ratio(effective_length_m=2.0, radius_of_gyration_m=0.01) == pytest.approx(200.0)


def test_effective_length_rejects_unsupported_end_condition() -> None:
    with pytest.raises(ValueError, match="Unsupported end condition"):
        effective_length(1.0, "free-free")


@pytest.mark.parametrize("length_m", [0.0, -1.0, float("nan"), float("inf")])
def test_effective_length_rejects_invalid_length(length_m: float) -> None:
    with pytest.raises(ValueError, match="length_m must be a finite positive value"):
        effective_length(length_m, "pinned-pinned")


@pytest.mark.parametrize(
    ("area_m2", "minimum_second_moment_m4", "invalid_name"),
    [
        (0.0, 1.0, "area_m2"),
        (-1.0, 1.0, "area_m2"),
        (float("nan"), 1.0, "area_m2"),
        (float("inf"), 1.0, "area_m2"),
        (1.0, 0.0, "minimum_second_moment_m4"),
        (1.0, -1.0, "minimum_second_moment_m4"),
        (1.0, float("nan"), "minimum_second_moment_m4"),
        (1.0, float("inf"), "minimum_second_moment_m4"),
    ],
)
def test_radius_of_gyration_rejects_invalid_section_properties(
    area_m2: float,
    minimum_second_moment_m4: float,
    invalid_name: str,
) -> None:
    section = SectionProperties(
        area_m2=area_m2,
        second_moment_x_m4=1.0,
        second_moment_y_m4=1.0,
        minimum_second_moment_m4=minimum_second_moment_m4,
        weaker_axis="x",
    )

    with pytest.raises(ValueError, match=f"{invalid_name} must be a finite positive value"):
        radius_of_gyration(section)


@pytest.mark.parametrize(
    ("effective_length_m", "radius_of_gyration_m", "invalid_name"),
    [
        (0.0, 1.0, "effective_length_m"),
        (-1.0, 1.0, "effective_length_m"),
        (float("nan"), 1.0, "effective_length_m"),
        (float("inf"), 1.0, "effective_length_m"),
        (1.0, 0.0, "radius_of_gyration_m"),
        (1.0, -1.0, "radius_of_gyration_m"),
        (1.0, float("nan"), "radius_of_gyration_m"),
        (1.0, float("inf"), "radius_of_gyration_m"),
    ],
)
def test_slenderness_ratio_rejects_invalid_inputs(
    effective_length_m: float,
    radius_of_gyration_m: float,
    invalid_name: str,
) -> None:
    with pytest.raises(ValueError, match=f"{invalid_name} must be a finite positive value"):
        slenderness_ratio(effective_length_m, radius_of_gyration_m)