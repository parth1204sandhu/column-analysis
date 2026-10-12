import pytest

from column_analysis.graph_data import build_slenderness_curve_data
from column_analysis.sections import rectangular_section
from column_analysis.theories import euler_critical_load


def test_curve_data_uses_existing_theory_functions_and_decreases_with_slenderness() -> None:
    section = rectangular_section(width_m=0.05, height_m=0.1)
    ratios = [20.0, 40.0]

    curves = build_slenderness_curve_data(
        ratios,
        section,
        youngs_modulus_pa=200e9,
        compressive_strength_pa=250e6,
        rankine_constant_dimensionless=0.001,
        yield_stress_pa=250e6,
    )

    radius_m = 0.05 / (12**0.5)
    assert curves["Euler"][0] == pytest.approx(
        euler_critical_load(200e9, section.minimum_second_moment_m4, ratios[0] * radius_m)
    )
    assert curves["Euler"][1] < curves["Euler"][0]
    assert curves["Rankine-Gordon"][1] < curves["Rankine-Gordon"][0]
    assert curves["Johnson"][1] < curves["Johnson"][0]


def test_missing_material_inputs_only_omit_dependent_curves() -> None:
    section = rectangular_section(width_m=0.05, height_m=0.1)

    curves = build_slenderness_curve_data(
        [20.0, 40.0],
        section,
        compressive_strength_pa=250e6,
        rankine_constant_dimensionless=0.001,
    )

    assert curves["Euler"] == [None, None]
    assert all(value is not None for value in curves["Rankine-Gordon"])
    assert curves["Johnson"] == [None, None]


def test_non_positive_johnson_values_are_omitted_from_curve() -> None:
    section = rectangular_section(width_m=0.05, height_m=0.1)

    curves = build_slenderness_curve_data(
        [10.0, 1000.0],
        section,
        youngs_modulus_pa=200e9,
        yield_stress_pa=250e6,
    )

    assert curves["Johnson"][0] is not None
    assert curves["Johnson"][1] is None


@pytest.mark.parametrize("ratio", [0.0, -1.0, float("nan"), float("inf")])
def test_curve_data_rejects_invalid_slenderness_values(ratio: float) -> None:
    section = rectangular_section(width_m=0.05, height_m=0.1)

    with pytest.raises(ValueError, match="slenderness_ratio must be"):
        build_slenderness_curve_data([ratio], section)


def test_curve_data_rejects_empty_slenderness_range() -> None:
    section = rectangular_section(width_m=0.05, height_m=0.1)

    with pytest.raises(ValueError, match="at least one slenderness ratio"):
        build_slenderness_curve_data([], section)