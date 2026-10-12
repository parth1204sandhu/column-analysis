from math import pi

import pytest

from column_analysis.sections import rectangular_section, solid_circular_section


def test_solid_circular_section_uses_si_units_and_formula() -> None:
    diameter_m = 0.1

    properties = solid_circular_section(diameter_m)

    assert properties.area_m2 == pytest.approx(pi * diameter_m**2 / 4)
    expected_second_moment_m4 = pi * diameter_m**4 / 64
    assert properties.second_moment_x_m4 == pytest.approx(expected_second_moment_m4)
    assert properties.second_moment_y_m4 == pytest.approx(expected_second_moment_m4)
    assert properties.minimum_second_moment_m4 == pytest.approx(expected_second_moment_m4)
    assert properties.weaker_axis == "both"


def test_rectangular_section_calculates_both_axes_and_selects_weaker_axis() -> None:
    width_m = 0.04
    height_m = 0.08

    properties = rectangular_section(width_m, height_m)

    assert properties.area_m2 == pytest.approx(width_m * height_m)
    assert properties.second_moment_x_m4 == pytest.approx(width_m * height_m**3 / 12)
    assert properties.second_moment_y_m4 == pytest.approx(height_m * width_m**3 / 12)
    assert properties.minimum_second_moment_m4 == pytest.approx(properties.second_moment_y_m4)
    assert properties.weaker_axis == "y"


def test_square_section_has_equal_second_moments() -> None:
    properties = rectangular_section(width_m=0.05, height_m=0.05)

    assert properties.second_moment_x_m4 == pytest.approx(properties.second_moment_y_m4)
    assert properties.minimum_second_moment_m4 == pytest.approx(properties.second_moment_x_m4)
    assert properties.weaker_axis == "both"


@pytest.mark.parametrize("diameter_m", [0.0, -0.1, float("inf"), float("nan")])
def test_solid_circular_section_rejects_invalid_diameter(diameter_m: float) -> None:
    with pytest.raises(ValueError, match="diameter_m must be a finite positive value in metres"):
        solid_circular_section(diameter_m)


@pytest.mark.parametrize(
    ("width_m", "height_m", "invalid_dimension"),
    [
        (0.0, 0.1, "width_m"),
        (-0.1, 0.1, "width_m"),
        (0.1, 0.0, "height_m"),
        (0.1, -0.1, "height_m"),
        (float("inf"), 0.1, "width_m"),
        (0.1, float("nan"), "height_m"),
    ],
)
def test_rectangular_section_rejects_invalid_dimensions(
    width_m: float,
    height_m: float,
    invalid_dimension: str,
) -> None:
    with pytest.raises(ValueError, match=f"{invalid_dimension} must be a finite positive value in metres"):
        rectangular_section(width_m, height_m)