from collections.abc import Callable
from math import pi

import pytest

from column_analysis.sections import (
    angle_section,
    channel_section,
    hollow_circular_section,
    hollow_rectangular_section,
    i_section,
    rectangular_section,
    solid_circular_section,
    t_section,
)


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


def test_solid_circular_section_rejects_dimensions_with_underflowed_properties() -> None:
    with pytest.raises(ValueError, match="area_m2 must be a finite positive value"):
        solid_circular_section(1e-200)


def test_rectangular_section_rejects_dimensions_with_underflowed_properties() -> None:
    with pytest.raises(ValueError, match="area_m2 must be a finite positive value"):
        rectangular_section(1e-200, 1e-200)


@pytest.mark.parametrize(
    ("constructor", "dimensions", "property_name"),
    [
        (solid_circular_section, (1e-100,), "second_moment_m4"),
        (rectangular_section, (1e-100, 1e-100), "second_moment_x_m4"),
    ],
)
def test_solid_sections_reject_underflowed_inertia_with_nonzero_area(
    constructor: Callable[..., object],
    dimensions: tuple[float, ...],
    property_name: str,
) -> None:
    with pytest.raises(ValueError, match=f"{property_name} must be a finite positive value"):
        constructor(*dimensions)


@pytest.mark.parametrize(
    ("constructor", "dimensions"),
    [
        (solid_circular_section, (1e100,)),
        (rectangular_section, (1e100, 1e100)),
    ],
)
def test_solid_sections_reject_properties_outside_numeric_range(
    constructor: Callable[..., object],
    dimensions: tuple[float, ...],
) -> None:
    with pytest.raises(ValueError, match="exceed the supported numeric range"):
        constructor(*dimensions)


def test_hollow_circular_section_matches_annulus_formulas_and_centroid() -> None:
    outer_diameter_m = 0.08
    inner_diameter_m = 0.06

    properties = hollow_circular_section(outer_diameter_m, inner_diameter_m)

    expected_area_m2 = pi * (outer_diameter_m**2 - inner_diameter_m**2) / 4
    expected_second_moment_m4 = (
        pi * (outer_diameter_m**4 - inner_diameter_m**4) / 64
    )
    assert properties.area_m2 == pytest.approx(expected_area_m2)
    assert properties.centroid_x_m == pytest.approx(outer_diameter_m / 2)
    assert properties.centroid_y_m == pytest.approx(outer_diameter_m / 2)
    assert properties.second_moment_x_m4 == pytest.approx(expected_second_moment_m4)
    assert properties.second_moment_y_m4 == pytest.approx(expected_second_moment_m4)
    assert properties.minimum_second_moment_m4 == pytest.approx(expected_second_moment_m4)
    assert properties.weaker_axis == "both"


def test_hollow_rectangular_section_matches_rectangle_subtraction_formulas() -> None:
    outer_width_m = 0.08
    outer_height_m = 0.12
    wall_thickness_m = 0.005
    inner_width_m = outer_width_m - 2 * wall_thickness_m
    inner_height_m = outer_height_m - 2 * wall_thickness_m

    properties = hollow_rectangular_section(
        outer_width_m,
        outer_height_m,
        wall_thickness_m,
    )

    expected_area_m2 = (
        outer_width_m * outer_height_m - inner_width_m * inner_height_m
    )
    expected_second_moment_x_m4 = (
        outer_width_m * outer_height_m**3
        - inner_width_m * inner_height_m**3
    ) / 12
    expected_second_moment_y_m4 = (
        outer_height_m * outer_width_m**3
        - inner_height_m * inner_width_m**3
    ) / 12
    assert properties.area_m2 == pytest.approx(expected_area_m2)
    assert properties.centroid_x_m == pytest.approx(outer_width_m / 2)
    assert properties.centroid_y_m == pytest.approx(outer_height_m / 2)
    assert properties.second_moment_x_m4 == pytest.approx(expected_second_moment_x_m4)
    assert properties.second_moment_y_m4 == pytest.approx(expected_second_moment_y_m4)
    assert properties.minimum_second_moment_m4 == pytest.approx(
        expected_second_moment_y_m4
    )
    assert properties.weaker_axis == "y"


def test_square_hollow_rectangular_section_has_equal_second_moments() -> None:
    properties = hollow_rectangular_section(
        outer_width_m=0.1,
        outer_height_m=0.1,
        wall_thickness_m=0.01,
    )

    assert properties.second_moment_x_m4 == pytest.approx(properties.second_moment_y_m4)
    assert properties.minimum_second_moment_m4 == pytest.approx(
        properties.second_moment_x_m4
    )
    assert properties.weaker_axis == "both"


def test_i_section_matches_hand_calculated_composite_reference() -> None:
    overall_depth_m = 0.2
    flange_width_m = 0.1
    web_thickness_m = 0.01
    flange_thickness_m = 0.015
    web_height_m = overall_depth_m - 2 * flange_thickness_m
    flange_area_m2 = flange_width_m * flange_thickness_m
    web_area_m2 = web_thickness_m * web_height_m
    expected_area_m2 = 2 * flange_area_m2 + web_area_m2
    expected_centroid_x_m = flange_width_m / 2
    expected_centroid_y_m = (
        flange_area_m2 * (flange_thickness_m / 2)
        + web_area_m2 * (overall_depth_m / 2)
        + flange_area_m2 * (overall_depth_m - flange_thickness_m / 2)
    ) / expected_area_m2
    flange_offset_m = overall_depth_m / 2 - flange_thickness_m / 2
    expected_second_moment_x_m4 = (
        web_thickness_m * web_height_m**3 / 12
        + 2
        * (
            flange_width_m * flange_thickness_m**3 / 12
            + flange_area_m2 * flange_offset_m**2
        )
    )
    expected_second_moment_y_m4 = (
        web_height_m * web_thickness_m**3 / 12
        + 2 * flange_thickness_m * flange_width_m**3 / 12
    )

    properties = i_section(
        overall_depth_m,
        flange_width_m,
        web_thickness_m,
        flange_thickness_m,
    )

    assert expected_area_m2 == pytest.approx(0.0047)
    assert expected_second_moment_x_m4 == pytest.approx(2.9819166666666667e-5)
    assert expected_second_moment_y_m4 == pytest.approx(2.514166666666667e-6)
    assert properties.area_m2 == pytest.approx(expected_area_m2)
    assert properties.centroid_x_m == pytest.approx(expected_centroid_x_m)
    assert properties.centroid_y_m == pytest.approx(expected_centroid_y_m)
    assert properties.centroid_y_m == pytest.approx(overall_depth_m / 2)
    assert properties.second_moment_x_m4 == pytest.approx(expected_second_moment_x_m4)
    assert properties.second_moment_y_m4 == pytest.approx(expected_second_moment_y_m4)
    assert properties.minimum_second_moment_m4 == pytest.approx(
        expected_second_moment_y_m4
    )
    assert properties.weaker_axis == "y"


def test_channel_section_matches_composite_reference_and_has_zero_product_inertia() -> None:
    overall_depth_m = 0.2
    flange_width_m = 0.08
    web_thickness_m = 0.01
    flange_thickness_m = 0.015
    extension_width_m = flange_width_m - web_thickness_m
    web_area_m2 = web_thickness_m * overall_depth_m
    flange_area_m2 = extension_width_m * flange_thickness_m
    expected_area_m2 = web_area_m2 + 2 * flange_area_m2
    expected_centroid_x_m = (
        web_area_m2 * (web_thickness_m / 2)
        + 2 * flange_area_m2 * ((flange_width_m + web_thickness_m) / 2)
    ) / expected_area_m2
    flange_offset_m = (overall_depth_m - flange_thickness_m) / 2
    expected_second_moment_x_m4 = (
        web_thickness_m * overall_depth_m**3 / 12
        + 2
        * (
            extension_width_m * flange_thickness_m**3 / 12
            + flange_area_m2 * flange_offset_m**2
        )
    )
    expected_second_moment_y_m4 = (
        overall_depth_m * web_thickness_m**3 / 12
        + web_area_m2 * (web_thickness_m / 2 - expected_centroid_x_m) ** 2
        + 2
        * (
            flange_thickness_m * extension_width_m**3 / 12
            + flange_area_m2
            * (
                (flange_width_m + web_thickness_m) / 2
                - expected_centroid_x_m
            )
            ** 2
        )
    )

    properties = channel_section(
        overall_depth_m,
        flange_width_m,
        web_thickness_m,
        flange_thickness_m,
    )

    assert expected_area_m2 == pytest.approx(0.0041)
    assert expected_centroid_x_m == pytest.approx(0.02548780487804878)
    assert expected_second_moment_x_m4 == pytest.approx(2.467416666666667e-5)
    assert expected_second_moment_y_m4 == pytest.approx(2.5131910569105694e-6)
    assert properties.area_m2 == pytest.approx(expected_area_m2)
    assert properties.centroid_x_m == pytest.approx(expected_centroid_x_m)
    assert properties.centroid_y_m == pytest.approx(overall_depth_m / 2)
    assert properties.second_moment_x_m4 == pytest.approx(expected_second_moment_x_m4)
    assert properties.second_moment_y_m4 == pytest.approx(expected_second_moment_y_m4)
    assert properties.product_of_inertia_xy_m4 == pytest.approx(0.0, abs=1e-18)
    assert properties.principal_second_moment_1_m4 == pytest.approx(
        expected_second_moment_x_m4
    )
    assert properties.principal_second_moment_2_m4 == pytest.approx(
        expected_second_moment_y_m4
    )
    assert properties.minimum_second_moment_m4 == pytest.approx(
        properties.principal_second_moment_2_m4
    )
    assert properties.weaker_axis == "y"


def test_angle_section_matches_signed_composite_reference_and_principal_moments() -> None:
    horizontal_leg_m = 0.08
    vertical_leg_m = 0.1
    thickness_m = 0.01
    components = (
        (thickness_m * vertical_leg_m, thickness_m / 2, vertical_leg_m / 2, thickness_m, vertical_leg_m, 1),
        (horizontal_leg_m * thickness_m, horizontal_leg_m / 2, thickness_m / 2, horizontal_leg_m, thickness_m, 1),
        (thickness_m**2, thickness_m / 2, thickness_m / 2, thickness_m, thickness_m, -1),
    )
    expected_area_m2 = sum(sign * area for area, _, _, _, _, sign in components)
    expected_centroid_x_m = sum(
        sign * area * x for area, x, _, _, _, sign in components
    ) / expected_area_m2
    expected_centroid_y_m = sum(
        sign * area * y for area, _, y, _, _, sign in components
    ) / expected_area_m2
    expected_second_moment_x_m4 = sum(
        sign
        * (
            width * height**3 / 12
            + area * (y - expected_centroid_y_m) ** 2
        )
        for area, _, y, width, height, sign in components
    )
    expected_second_moment_y_m4 = sum(
        sign
        * (
            height * width**3 / 12
            + area * (x - expected_centroid_x_m) ** 2
        )
        for area, x, _, width, height, sign in components
    )
    expected_product_of_inertia_xy_m4 = sum(
        sign
        * area
        * (x - expected_centroid_x_m)
        * (y - expected_centroid_y_m)
        for area, x, y, _, _, sign in components
    )
    principal_average_m4 = (
        expected_second_moment_x_m4 + expected_second_moment_y_m4
    ) / 2
    principal_radius_m4 = (
        ((expected_second_moment_x_m4 - expected_second_moment_y_m4) / 2) ** 2
        + expected_product_of_inertia_xy_m4**2
    ) ** 0.5
    expected_principal_1_m4 = principal_average_m4 + principal_radius_m4
    expected_principal_2_m4 = principal_average_m4 - principal_radius_m4

    properties = angle_section(horizontal_leg_m, vertical_leg_m, thickness_m)

    assert expected_area_m2 == pytest.approx(0.0017)
    assert expected_centroid_x_m == pytest.approx(0.02147058823529412)
    assert expected_centroid_y_m == pytest.approx(0.03147058823529412)
    assert expected_second_moment_x_m4 == pytest.approx(1.6729901960784318e-6)
    assert expected_second_moment_y_m4 == pytest.approx(9.529901960784315e-7)
    assert expected_product_of_inertia_xy_m4 == pytest.approx(-7.411764705882353e-7)
    assert properties.area_m2 == pytest.approx(expected_area_m2)
    assert properties.centroid_x_m == pytest.approx(expected_centroid_x_m)
    assert properties.centroid_y_m == pytest.approx(expected_centroid_y_m)
    assert properties.second_moment_x_m4 == pytest.approx(expected_second_moment_x_m4)
    assert properties.second_moment_y_m4 == pytest.approx(expected_second_moment_y_m4)
    assert properties.product_of_inertia_xy_m4 == pytest.approx(
        expected_product_of_inertia_xy_m4
    )
    assert properties.product_of_inertia_xy_m4 < 0
    assert properties.principal_second_moment_1_m4 == pytest.approx(
        expected_principal_1_m4
    )
    assert properties.principal_second_moment_2_m4 == pytest.approx(
        expected_principal_2_m4
    )
    assert properties.minimum_second_moment_m4 == pytest.approx(
        expected_principal_2_m4
    )
    assert properties.minimum_second_moment_m4 < min(
        properties.second_moment_x_m4,
        properties.second_moment_y_m4,
    )
    assert properties.weaker_axis == "principal"


def test_t_section_matches_composite_reference_and_has_zero_product_inertia() -> None:
    overall_depth_m = 0.18
    flange_width_m = 0.09
    web_thickness_m = 0.01
    flange_thickness_m = 0.015
    web_height_m = overall_depth_m - flange_thickness_m
    web_area_m2 = web_thickness_m * web_height_m
    flange_area_m2 = flange_width_m * flange_thickness_m
    expected_area_m2 = web_area_m2 + flange_area_m2
    expected_centroid_y_m = (
        web_area_m2 * (web_height_m / 2)
        + flange_area_m2 * (overall_depth_m - flange_thickness_m / 2)
    ) / expected_area_m2
    expected_second_moment_x_m4 = (
        web_thickness_m * web_height_m**3 / 12
        + web_area_m2 * (web_height_m / 2 - expected_centroid_y_m) ** 2
        + flange_width_m * flange_thickness_m**3 / 12
        + flange_area_m2
        * (
            overall_depth_m
            - flange_thickness_m / 2
            - expected_centroid_y_m
        )
        ** 2
    )
    expected_second_moment_y_m4 = (
        web_height_m * web_thickness_m**3 / 12
        + flange_thickness_m * flange_width_m**3 / 12
    )

    properties = t_section(
        overall_depth_m,
        flange_width_m,
        web_thickness_m,
        flange_thickness_m,
    )

    assert expected_area_m2 == pytest.approx(0.003)
    assert expected_centroid_y_m == pytest.approx(0.123)
    assert expected_second_moment_x_m4 == pytest.approx(9.783e-6)
    assert expected_second_moment_y_m4 == pytest.approx(9.25e-7)
    assert properties.area_m2 == pytest.approx(expected_area_m2)
    assert properties.centroid_x_m == pytest.approx(flange_width_m / 2)
    assert properties.centroid_y_m == pytest.approx(expected_centroid_y_m)
    assert properties.second_moment_x_m4 == pytest.approx(expected_second_moment_x_m4)
    assert properties.second_moment_y_m4 == pytest.approx(expected_second_moment_y_m4)
    assert properties.product_of_inertia_xy_m4 == pytest.approx(0.0, abs=1e-18)
    assert properties.principal_second_moment_1_m4 == pytest.approx(
        expected_second_moment_x_m4
    )
    assert properties.principal_second_moment_2_m4 == pytest.approx(
        expected_second_moment_y_m4
    )
    assert properties.minimum_second_moment_m4 == pytest.approx(
        properties.principal_second_moment_2_m4
    )
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


@pytest.mark.parametrize(
    ("outer_diameter_m", "inner_diameter_m", "invalid_dimension"),
    [
        (0.0, 0.02, "outer_diameter_m"),
        (0.05, 0.0, "inner_diameter_m"),
        (-0.05, 0.02, "outer_diameter_m"),
        (0.05, -0.02, "inner_diameter_m"),
        (float("inf"), 0.02, "outer_diameter_m"),
        (0.05, float("nan"), "inner_diameter_m"),
    ],
)
def test_hollow_circular_section_rejects_invalid_dimensions(
    outer_diameter_m: float,
    inner_diameter_m: float,
    invalid_dimension: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=f"{invalid_dimension} must be a finite positive value in metres",
    ):
        hollow_circular_section(outer_diameter_m, inner_diameter_m)


@pytest.mark.parametrize(
    ("outer_diameter_m", "inner_diameter_m"),
    [(0.05, 0.05), (0.04, 0.05)],
)
def test_hollow_circular_section_rejects_impossible_diameter_relationship(
    outer_diameter_m: float,
    inner_diameter_m: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="outer_diameter_m must be greater than inner_diameter_m",
    ):
        hollow_circular_section(outer_diameter_m, inner_diameter_m)


@pytest.mark.parametrize(
    ("outer_width_m", "outer_height_m", "wall_thickness_m", "invalid_dimension"),
    [
        (0.0, 0.1, 0.01, "outer_width_m"),
        (0.1, 0.0, 0.01, "outer_height_m"),
        (0.1, 0.1, 0.0, "wall_thickness_m"),
        (-0.1, 0.1, 0.01, "outer_width_m"),
        (0.1, float("inf"), 0.01, "outer_height_m"),
        (0.1, 0.1, float("nan"), "wall_thickness_m"),
    ],
)
def test_hollow_rectangular_section_rejects_invalid_dimensions(
    outer_width_m: float,
    outer_height_m: float,
    wall_thickness_m: float,
    invalid_dimension: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=f"{invalid_dimension} must be a finite positive value in metres",
    ):
        hollow_rectangular_section(
            outer_width_m,
            outer_height_m,
            wall_thickness_m,
        )

@pytest.mark.parametrize(
    ("outer_width_m", "outer_height_m", "wall_thickness_m", "invalid_dimension"),
    [
        (0.02, 0.1, 0.01, "outer_width_m"),
        (0.1, 0.02, 0.01, "outer_height_m"),
        (0.02, 0.02, 0.01, "outer_width_m"),
    ],
)
def test_hollow_rectangular_section_rejects_impossible_wall_thickness(
    outer_width_m: float,
    outer_height_m: float,
    wall_thickness_m: float,
    invalid_dimension: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=f"{invalid_dimension} must be greater than twice wall_thickness_m",
    ):
        hollow_rectangular_section(
            outer_width_m,
            outer_height_m,
            wall_thickness_m,
        )


@pytest.mark.parametrize(
    ("overall_depth_m", "flange_width_m", "web_thickness_m", "flange_thickness_m", "invalid_dimension"),
    [
        (0.0, 0.1, 0.01, 0.01, "overall_depth_m"),
        (0.2, 0.0, 0.01, 0.01, "flange_width_m"),
        (0.2, 0.1, 0.0, 0.01, "web_thickness_m"),
        (0.2, 0.1, 0.01, 0.0, "flange_thickness_m"),
        (-0.2, 0.1, 0.01, 0.01, "overall_depth_m"),
        (0.2, float("inf"), 0.01, 0.01, "flange_width_m"),
        (0.2, 0.1, float("nan"), 0.01, "web_thickness_m"),
        (0.2, 0.1, 0.01, float("inf"), "flange_thickness_m"),
    ],
)
def test_i_section_rejects_non_positive_or_non_finite_dimensions(
    overall_depth_m: float,
    flange_width_m: float,
    web_thickness_m: float,
    flange_thickness_m: float,
    invalid_dimension: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=f"{invalid_dimension} must be a finite positive value in metres",
    ):
        i_section(
            overall_depth_m,
            flange_width_m,
            web_thickness_m,
            flange_thickness_m,
        )


@pytest.mark.parametrize(
    (
        "overall_depth_m",
        "flange_width_m",
        "web_thickness_m",
        "flange_thickness_m",
        "message",
    ),
    [
        (0.2, 0.01, 0.01, 0.01, "web_thickness_m must be less than flange_width_m"),
        (0.2, 0.02, 0.03, 0.01, "web_thickness_m must be less than flange_width_m"),
        (
            0.02,
            0.1,
            0.01,
            0.01,
            "twice flange_thickness_m must be less than overall_depth_m",
        ),
        (
            0.02,
            0.1,
            0.01,
            0.02,
            "twice flange_thickness_m must be less than overall_depth_m",
        ),
    ],
)
def test_i_section_rejects_impossible_dimension_relationships(
    overall_depth_m: float,
    flange_width_m: float,
    web_thickness_m: float,
    flange_thickness_m: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        i_section(
            overall_depth_m,
            flange_width_m,
            web_thickness_m,
            flange_thickness_m,
        )


@pytest.mark.parametrize(
    ("dimension_index", "dimension_name"),
    [
        (0, "overall_depth_m"),
        (1, "flange_width_m"),
        (2, "web_thickness_m"),
        (3, "flange_thickness_m"),
    ],
)
@pytest.mark.parametrize("invalid_value", [0.0, -0.01, float("nan"), float("inf")])
def test_channel_section_rejects_invalid_dimensions(
    dimension_index: int,
    dimension_name: str,
    invalid_value: float,
) -> None:
    dimensions = [0.2, 0.08, 0.01, 0.015]
    dimensions[dimension_index] = invalid_value

    with pytest.raises(
        ValueError,
        match=f"{dimension_name} must be a finite positive value in metres",
    ):
        channel_section(*dimensions)


@pytest.mark.parametrize(
    ("overall_depth_m", "flange_width_m", "web_thickness_m", "flange_thickness_m", "message"),
    [
        (0.2, 0.01, 0.01, 0.01, "web_thickness_m must be less than flange_width_m"),
        (0.2, 0.02, 0.03, 0.01, "web_thickness_m must be less than flange_width_m"),
        (
            0.02,
            0.1,
            0.01,
            0.01,
            "twice flange_thickness_m must be less than overall_depth_m",
        ),
    ],
)
def test_channel_section_rejects_impossible_dimensions(
    overall_depth_m: float,
    flange_width_m: float,
    web_thickness_m: float,
    flange_thickness_m: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        channel_section(
            overall_depth_m,
            flange_width_m,
            web_thickness_m,
            flange_thickness_m,
        )


@pytest.mark.parametrize(
    ("dimension_index", "dimension_name"),
    [
        (0, "horizontal_leg_m"),
        (1, "vertical_leg_m"),
        (2, "thickness_m"),
    ],
)
@pytest.mark.parametrize("invalid_value", [0.0, -0.01, float("nan"), float("inf")])
def test_angle_section_rejects_invalid_dimensions(
    dimension_index: int,
    dimension_name: str,
    invalid_value: float,
) -> None:
    dimensions = [0.08, 0.1, 0.01]
    dimensions[dimension_index] = invalid_value

    with pytest.raises(
        ValueError,
        match=f"{dimension_name} must be a finite positive value in metres",
    ):
        angle_section(*dimensions)


@pytest.mark.parametrize(
    ("horizontal_leg_m", "vertical_leg_m", "thickness_m", "message"),
    [
        (0.01, 0.1, 0.01, "thickness_m must be less than horizontal_leg_m"),
        (0.1, 0.01, 0.01, "thickness_m must be less than vertical_leg_m"),
        (0.02, 0.1, 0.03, "thickness_m must be less than horizontal_leg_m"),
        (0.1, 0.02, 0.03, "thickness_m must be less than vertical_leg_m"),
    ],
)
def test_angle_section_rejects_impossible_leg_thickness(
    horizontal_leg_m: float,
    vertical_leg_m: float,
    thickness_m: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        angle_section(horizontal_leg_m, vertical_leg_m, thickness_m)


@pytest.mark.parametrize(
    ("dimension_index", "dimension_name"),
    [
        (0, "overall_depth_m"),
        (1, "flange_width_m"),
        (2, "web_thickness_m"),
        (3, "flange_thickness_m"),
    ],
)
@pytest.mark.parametrize("invalid_value", [0.0, -0.01, float("nan"), float("inf")])
def test_t_section_rejects_invalid_dimensions(
    dimension_index: int,
    dimension_name: str,
    invalid_value: float,
) -> None:
    dimensions = [0.18, 0.09, 0.01, 0.015]
    dimensions[dimension_index] = invalid_value

    with pytest.raises(
        ValueError,
        match=f"{dimension_name} must be a finite positive value in metres",
    ):
        t_section(*dimensions)


@pytest.mark.parametrize(
    ("overall_depth_m", "flange_width_m", "web_thickness_m", "flange_thickness_m", "message"),
    [
        (0.2, 0.01, 0.01, 0.01, "web_thickness_m must be less than flange_width_m"),
        (0.2, 0.02, 0.03, 0.01, "web_thickness_m must be less than flange_width_m"),
        (
            0.02,
            0.1,
            0.01,
            0.01,
            "twice flange_thickness_m must be less than overall_depth_m",
        ),
    ],
)
def test_t_section_rejects_impossible_dimensions(
    overall_depth_m: float,
    flange_width_m: float,
    web_thickness_m: float,
    flange_thickness_m: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        t_section(
            overall_depth_m,
            flange_width_m,
            web_thickness_m,
            flange_thickness_m,
        )