import pytest

from column_analysis.theories import (
    euler_critical_load,
    johnson_critical_load,
    rankine_critical_load,
)


def test_euler_critical_load_matches_independent_hand_calculation() -> None:
    # pi^2 * (200 GPa * 1e-6 m^4) / (2 m)^2
    expected_load_n = 493_480.2200544679

    load_n = euler_critical_load(
        youngs_modulus_pa=200_000_000_000.0,
        minimum_second_moment_m4=1e-6,
        effective_length_m=2.0,
    )

    assert load_n == pytest.approx(expected_load_n)


def test_euler_result_uses_si_inputs_and_returns_newtons() -> None:
    load_n = euler_critical_load(
        youngs_modulus_pa=100_000_000_000.0,
        minimum_second_moment_m4=1e-8,
        effective_length_m=1.0,
    )

    assert load_n == pytest.approx(9_869.604401089358)


def test_euler_load_increases_proportionally_with_modulus() -> None:
    base_load_n = euler_critical_load(100e9, 2e-6, 3.0)
    doubled_modulus_load_n = euler_critical_load(200e9, 2e-6, 3.0)

    assert doubled_modulus_load_n == pytest.approx(2 * base_load_n)


def test_doubling_effective_length_reduces_euler_load_to_one_quarter() -> None:
    original_load_n = euler_critical_load(200e9, 1e-6, 2.0)
    doubled_length_load_n = euler_critical_load(200e9, 1e-6, 4.0)

    assert doubled_length_load_n == pytest.approx(original_load_n / 4)


@pytest.mark.parametrize("youngs_modulus_pa", [0.0, -1.0, float("nan"), float("inf")])
def test_euler_rejects_invalid_youngs_modulus(youngs_modulus_pa: float) -> None:
    with pytest.raises(ValueError, match="youngs_modulus_pa must be a finite, strictly positive value in Pa"):
        euler_critical_load(youngs_modulus_pa, 1e-6, 1.0)


@pytest.mark.parametrize(
    "minimum_second_moment_m4",
    [0.0, -1.0, float("nan"), float("inf")],
)
def test_euler_rejects_invalid_second_moment(minimum_second_moment_m4: float) -> None:
    with pytest.raises(
        ValueError,
        match=r"minimum_second_moment_m4 must be a finite, strictly positive value in m\^4",
    ):
        euler_critical_load(200e9, minimum_second_moment_m4, 1.0)


@pytest.mark.parametrize("effective_length_m", [0.0, -1.0, float("nan"), float("inf")])
def test_euler_rejects_invalid_effective_length(effective_length_m: float) -> None:
    with pytest.raises(ValueError, match="effective_length_m must be a finite, strictly positive value in m"):
        euler_critical_load(200e9, 1e-6, effective_length_m)


def test_rankine_critical_load_matches_hand_calculation_in_newtons() -> None:
    # sigma_c * A = 1,000,000 N; Le / k = 10; denominator = 1 + 0.001 * 10^2 = 1.1.
    expected_load_n = 1_000_000 / 1.1

    load_n = rankine_critical_load(
        compressive_strength_pa=100_000_000.0,
        area_m2=0.01,
        rankine_constant_dimensionless=0.001,
        effective_length_m=2.0,
        least_radius_of_gyration_m=0.2,
    )

    assert load_n == pytest.approx(expected_load_n)


def test_rankine_load_increases_with_area_when_other_inputs_are_fixed() -> None:
    load_for_base_area_n = rankine_critical_load(100e6, 0.01, 0.001, 2.0, 0.2)
    load_for_double_area_n = rankine_critical_load(100e6, 0.02, 0.001, 2.0, 0.2)

    assert load_for_double_area_n == pytest.approx(2 * load_for_base_area_n)


def test_rankine_load_decreases_as_slenderness_increases() -> None:
    load_at_lower_slenderness_n = rankine_critical_load(100e6, 0.01, 0.001, 2.0, 0.2)
    load_at_higher_slenderness_n = rankine_critical_load(100e6, 0.01, 0.001, 4.0, 0.2)

    assert load_at_higher_slenderness_n < load_at_lower_slenderness_n


@pytest.mark.parametrize(
    ("parameter_name", "unit"),
    [
        ("compressive_strength_pa", "Pa"),
        ("area_m2", "m^2"),
        ("rankine_constant_dimensionless", "dimensionless"),
        ("effective_length_m", "m"),
        ("least_radius_of_gyration_m", "m"),
    ],
)
@pytest.mark.parametrize("invalid_value", [0.0, -1.0, float("nan"), float("inf")])
def test_rankine_rejects_invalid_inputs(
    parameter_name: str,
    unit: str,
    invalid_value: float,
) -> None:
    inputs = {
        "compressive_strength_pa": 100e6,
        "area_m2": 0.01,
        "rankine_constant_dimensionless": 0.001,
        "effective_length_m": 2.0,
        "least_radius_of_gyration_m": 0.2,
    }
    inputs[parameter_name] = invalid_value

    with pytest.raises(ValueError) as error:
        rankine_critical_load(**inputs)

    assert str(error.value) == (
        f"{parameter_name} must be a finite, strictly positive value in {unit}."
    )


def test_johnson_critical_load_matches_hand_calculation() -> None:
    # Le / k = 2*pi, so the reduction fraction is sigma_y / E = 0.001.
    # Thus sigma_cr = 199.8 MPa and P_J = 0.01 m^2 * 199.8 MPa.
    expected_load_n = 1_998_000.0

    load_n = johnson_critical_load(
        yield_stress_pa=200_000_000.0,
        youngs_modulus_pa=200_000_000_000.0,
        area_m2=0.01,
        effective_length_m=2 * 3.141592653589793,
        least_radius_of_gyration_m=1.0,
    )

    assert load_n == pytest.approx(expected_load_n)


def test_johnson_load_is_area_times_critical_stress() -> None:
    area_m2 = 0.01
    load_n = johnson_critical_load(200e6, 200e9, area_m2, 2 * 3.141592653589793, 1.0)

    assert load_n / area_m2 == pytest.approx(199_800_000.0)


def test_johnson_load_increases_proportionally_with_area() -> None:
    load_for_base_area_n = johnson_critical_load(200e6, 200e9, 0.01, 2 * 3.141592653589793, 1.0)
    load_for_double_area_n = johnson_critical_load(200e6, 200e9, 0.02, 2 * 3.141592653589793, 1.0)

    assert load_for_double_area_n == pytest.approx(2 * load_for_base_area_n)


def test_johnson_load_decreases_as_length_increases_while_positive() -> None:
    load_at_shorter_length_n = johnson_critical_load(200e6, 200e9, 0.01, 2.0, 0.1)
    load_at_longer_length_n = johnson_critical_load(200e6, 200e9, 0.01, 4.0, 0.1)

    assert load_at_shorter_length_n > 0
    assert load_at_longer_length_n > 0
    assert load_at_longer_length_n < load_at_shorter_length_n


@pytest.mark.parametrize(
    ("parameter_name", "unit"),
    [
        ("yield_stress_pa", "Pa"),
        ("youngs_modulus_pa", "Pa"),
        ("area_m2", "m^2"),
        ("effective_length_m", "m"),
        ("least_radius_of_gyration_m", "m"),
    ],
)
@pytest.mark.parametrize("invalid_value", [0.0, -1.0, float("nan"), float("inf")])
def test_johnson_rejects_invalid_inputs(
    parameter_name: str,
    unit: str,
    invalid_value: float,
) -> None:
    inputs = {
        "yield_stress_pa": 200e6,
        "youngs_modulus_pa": 200e9,
        "area_m2": 0.01,
        "effective_length_m": 1.0,
        "least_radius_of_gyration_m": 0.1,
    }
    inputs[parameter_name] = invalid_value

    with pytest.raises(ValueError) as error:
        johnson_critical_load(**inputs)

    assert str(error.value) == (
        f"{parameter_name} must be a finite, strictly positive value in {unit}."
    )


def test_johnson_rejects_non_positive_critical_stress() -> None:
    with pytest.raises(
        ValueError,
        match="Johnson critical stress is non-positive or non-finite",
    ):
        johnson_critical_load(
            yield_stress_pa=250e6,
            youngs_modulus_pa=200e9,
            area_m2=0.01,
            effective_length_m=2.0,
            least_radius_of_gyration_m=0.01,
        )