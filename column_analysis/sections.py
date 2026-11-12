"""Cross-section geometry and properties using SI units."""

from dataclasses import dataclass
from math import fsum, isfinite, pi, sqrt


@dataclass(frozen=True)
class SectionProperties:
    """Geometric section properties in SI units.

    The centroid coordinates use a lower-left bounding-box origin, with x
    horizontal and y vertical. ``Ixy`` is defined as the integral of
    ``(x - centroid_x) * (y - centroid_y)`` over the section. The x and y
    values are centroidal second moments of area in m^4.
    """

    area_m2: float
    second_moment_x_m4: float
    second_moment_y_m4: float
    minimum_second_moment_m4: float
    weaker_axis: str
    centroid_x_m: float = 0.0
    centroid_y_m: float = 0.0
    product_of_inertia_xy_m4: float = 0.0

    @property
    def principal_second_moment_1_m4(self) -> float:
        """Return the larger principal second moment of area in m^4."""
        return _principal_second_moments(
            self.second_moment_x_m4,
            self.second_moment_y_m4,
            self.product_of_inertia_xy_m4,
        )[0]

    @property
    def principal_second_moment_2_m4(self) -> float:
        """Return the smaller principal second moment of area in m^4."""
        return _principal_second_moments(
            self.second_moment_x_m4,
            self.second_moment_y_m4,
            self.product_of_inertia_xy_m4,
        )[1]


def _principal_second_moments(
    second_moment_x_m4: float,
    second_moment_y_m4: float,
    product_of_inertia_xy_m4: float,
) -> tuple[float, float]:
    """Return principal moments in descending order for the documented Ixy sign."""
    average = (second_moment_x_m4 + second_moment_y_m4) / 2
    radius = sqrt(
        ((second_moment_x_m4 - second_moment_y_m4) / 2) ** 2
        + product_of_inertia_xy_m4**2
    )
    return average + radius, average - radius


def _validate_dimension(name: str, dimension_m: float) -> None:
    """Require a finite, positive dimension given in metres."""
    if not isfinite(dimension_m) or dimension_m <= 0:
        raise ValueError(f"{name} must be a finite positive value in metres.")


def _validate_section_property(name: str, value: float, unit: str) -> None:
    """Require a calculated section property to be finite and positive."""
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive value in {unit}.")


def _section_from_centroidal_moments(
    area_m2: float,
    centroid_x_m: float,
    centroid_y_m: float,
    second_moment_x_m4: float,
    second_moment_y_m4: float,
    product_of_inertia_xy_m4: float,
) -> SectionProperties:
    """Build section properties and select the weaker principal moment."""
    _validate_section_property("area_m2", area_m2, "m^2")
    _validate_section_property("second_moment_x_m4", second_moment_x_m4, "m^4")
    _validate_section_property("second_moment_y_m4", second_moment_y_m4, "m^4")
    if not isfinite(product_of_inertia_xy_m4):
        raise ValueError("product_of_inertia_xy_m4 must be finite.")

    (
        principal_second_moment_1_m4,
        principal_second_moment_2_m4,
    ) = _principal_second_moments(
        second_moment_x_m4,
        second_moment_y_m4,
        product_of_inertia_xy_m4,
    )
    _validate_section_property(
        "principal_second_moment_1_m4",
        principal_second_moment_1_m4,
        "m^4",
    )
    _validate_section_property(
        "principal_second_moment_2_m4",
        principal_second_moment_2_m4,
        "m^4",
    )

    if product_of_inertia_xy_m4 != 0:
        weaker_axis = "principal"
    elif second_moment_x_m4 < second_moment_y_m4:
        weaker_axis = "x"
    elif second_moment_y_m4 < second_moment_x_m4:
        weaker_axis = "y"
    else:
        weaker_axis = "both"

    return SectionProperties(
        area_m2=area_m2,
        second_moment_x_m4=second_moment_x_m4,
        second_moment_y_m4=second_moment_y_m4,
        minimum_second_moment_m4=principal_second_moment_2_m4,
        weaker_axis=weaker_axis,
        centroid_x_m=centroid_x_m,
        centroid_y_m=centroid_y_m,
        product_of_inertia_xy_m4=product_of_inertia_xy_m4,
    )


def _composite_rectangular_section(
    components: tuple[tuple[float, float, float, float, float], ...],
) -> SectionProperties:
    """Calculate section properties from signed rectangular components.

    Each component is ``(x_left, y_bottom, width, height, area_sign)``.
    Negative signs represent removed overlap areas.
    """
    resolved_components = tuple(
        (
            area_sign * width_m * height_m,
            x_left_m + width_m / 2,
            y_bottom_m + height_m / 2,
            width_m,
            height_m,
            area_sign,
        )
        for x_left_m, y_bottom_m, width_m, height_m, area_sign in components
    )
    area_m2 = fsum(component[0] for component in resolved_components)
    _validate_section_property("area_m2", area_m2, "m^2")

    centroid_x_m = fsum(
        component[0] * component[1] for component in resolved_components
    ) / area_m2
    centroid_y_m = fsum(
        component[0] * component[2] for component in resolved_components
    ) / area_m2
    second_moment_x_m4 = fsum(
        area_sign
        * (
            width_m * height_m**3 / 12
            + width_m * height_m * (component_y_m - centroid_y_m) ** 2
        )
        for _, _, component_y_m, width_m, height_m, area_sign in resolved_components
    )
    second_moment_y_m4 = fsum(
        area_sign
        * (
            height_m * width_m**3 / 12
            + width_m * height_m * (component_x_m - centroid_x_m) ** 2
        )
        for _, component_x_m, _, width_m, height_m, area_sign in resolved_components
    )
    product_of_inertia_xy_m4 = fsum(
        area_sign
        * width_m
        * height_m
        * (component_x_m - centroid_x_m)
        * (component_y_m - centroid_y_m)
        for (
            _,
            component_x_m,
            component_y_m,
            width_m,
            height_m,
            area_sign,
        ) in resolved_components
    )

    return _section_from_centroidal_moments(
        area_m2,
        centroid_x_m,
        centroid_y_m,
        second_moment_x_m4,
        second_moment_y_m4,
        product_of_inertia_xy_m4,
    )


def solid_circular_section(diameter_m: float) -> SectionProperties:
    """Calculate properties for a solid circle with diameter in metres."""
    _validate_dimension("diameter_m", diameter_m)

    try:
        area_m2 = pi * diameter_m**2 / 4
        second_moment_m4 = pi * diameter_m**4 / 64
    except OverflowError as error:
        raise ValueError(
            "Solid circular section properties exceed the supported numeric range."
        ) from error
    if not isfinite(area_m2) or not isfinite(second_moment_m4):
        raise ValueError(
            "Solid circular section properties exceed the supported numeric range."
        )
    _validate_section_property("area_m2", area_m2, "m^2")
    _validate_section_property("second_moment_m4", second_moment_m4, "m^4")

    return SectionProperties(
        area_m2=area_m2,
        second_moment_x_m4=second_moment_m4,
        second_moment_y_m4=second_moment_m4,
        minimum_second_moment_m4=second_moment_m4,
        weaker_axis="both",
        centroid_x_m=diameter_m / 2,
        centroid_y_m=diameter_m / 2,
    )


def hollow_circular_section(
    outer_diameter_m: float,
    inner_diameter_m: float,
) -> SectionProperties:
    """Calculate properties for a hollow circular section in metres."""
    _validate_dimension("outer_diameter_m", outer_diameter_m)
    _validate_dimension("inner_diameter_m", inner_diameter_m)
    if outer_diameter_m <= inner_diameter_m:
        raise ValueError(
            "outer_diameter_m must be greater than inner_diameter_m."
        )

    area_m2 = pi * (outer_diameter_m**2 - inner_diameter_m**2) / 4
    second_moment_m4 = (
        pi * (outer_diameter_m**4 - inner_diameter_m**4) / 64
    )
    _validate_section_property("area_m2", area_m2, "m^2")
    _validate_section_property("second_moment_x_m4", second_moment_m4, "m^4")

    return SectionProperties(
        area_m2=area_m2,
        second_moment_x_m4=second_moment_m4,
        second_moment_y_m4=second_moment_m4,
        minimum_second_moment_m4=second_moment_m4,
        weaker_axis="both",
        centroid_x_m=outer_diameter_m / 2,
        centroid_y_m=outer_diameter_m / 2,
    )


def rectangular_section(width_m: float, height_m: float) -> SectionProperties:
    """Calculate rectangular properties for width and height in metres.

    The width is along x and the height is along y. ``Ix`` is about the
    centroidal x-axis (parallel to the width), and ``Iy`` is about the
    centroidal y-axis (parallel to the height).
    """
    _validate_dimension("width_m", width_m)
    _validate_dimension("height_m", height_m)

    try:
        area_m2 = width_m * height_m
        second_moment_x_m4 = width_m * height_m**3 / 12
        second_moment_y_m4 = height_m * width_m**3 / 12
    except OverflowError as error:
        raise ValueError(
            "Rectangular section properties exceed the supported numeric range."
        ) from error
    if not all(
        isfinite(value)
        for value in (area_m2, second_moment_x_m4, second_moment_y_m4)
    ):
        raise ValueError(
            "Rectangular section properties exceed the supported numeric range."
        )
    _validate_section_property("area_m2", area_m2, "m^2")
    _validate_section_property("second_moment_x_m4", second_moment_x_m4, "m^4")
    _validate_section_property("second_moment_y_m4", second_moment_y_m4, "m^4")

    if second_moment_x_m4 < second_moment_y_m4:
        minimum_second_moment_m4 = second_moment_x_m4
        weaker_axis = "x"
    elif second_moment_y_m4 < second_moment_x_m4:
        minimum_second_moment_m4 = second_moment_y_m4
        weaker_axis = "y"
    else:
        minimum_second_moment_m4 = second_moment_x_m4
        weaker_axis = "both"

    return SectionProperties(
        area_m2=area_m2,
        second_moment_x_m4=second_moment_x_m4,
        second_moment_y_m4=second_moment_y_m4,
        minimum_second_moment_m4=minimum_second_moment_m4,
        weaker_axis=weaker_axis,
        centroid_x_m=width_m / 2,
        centroid_y_m=height_m / 2,
    )


def hollow_rectangular_section(
    outer_width_m: float,
    outer_height_m: float,
    wall_thickness_m: float,
) -> SectionProperties:
    """Calculate properties for a uniform-wall hollow rectangle in metres.

    The outer width is along x and the outer height is along y. The centered
    rectangular opening is subtracted from the outer rectangle.
    """
    _validate_dimension("outer_width_m", outer_width_m)
    _validate_dimension("outer_height_m", outer_height_m)
    _validate_dimension("wall_thickness_m", wall_thickness_m)
    if outer_width_m <= 2 * wall_thickness_m:
        raise ValueError(
            "outer_width_m must be greater than twice wall_thickness_m."
        )
    if outer_height_m <= 2 * wall_thickness_m:
        raise ValueError(
            "outer_height_m must be greater than twice wall_thickness_m."
        )

    inner_width_m = outer_width_m - 2 * wall_thickness_m
    inner_height_m = outer_height_m - 2 * wall_thickness_m
    area_m2 = outer_width_m * outer_height_m - inner_width_m * inner_height_m
    second_moment_x_m4 = (
        outer_width_m * outer_height_m**3
        - inner_width_m * inner_height_m**3
    ) / 12
    second_moment_y_m4 = (
        outer_height_m * outer_width_m**3
        - inner_height_m * inner_width_m**3
    ) / 12
    _validate_section_property("area_m2", area_m2, "m^2")
    _validate_section_property("second_moment_x_m4", second_moment_x_m4, "m^4")
    _validate_section_property("second_moment_y_m4", second_moment_y_m4, "m^4")

    if second_moment_x_m4 < second_moment_y_m4:
        minimum_second_moment_m4 = second_moment_x_m4
        weaker_axis = "x"
    elif second_moment_y_m4 < second_moment_x_m4:
        minimum_second_moment_m4 = second_moment_y_m4
        weaker_axis = "y"
    else:
        minimum_second_moment_m4 = second_moment_x_m4
        weaker_axis = "both"

    return SectionProperties(
        area_m2=area_m2,
        second_moment_x_m4=second_moment_x_m4,
        second_moment_y_m4=second_moment_y_m4,
        minimum_second_moment_m4=minimum_second_moment_m4,
        weaker_axis=weaker_axis,
        centroid_x_m=outer_width_m / 2,
        centroid_y_m=outer_height_m / 2,
    )


def i_section(
    overall_depth_m: float,
    flange_width_m: float,
    web_thickness_m: float,
    flange_thickness_m: float,
) -> SectionProperties:
    """Calculate properties for a symmetric I-section with dimensions in metres.

    The web is centered between two equal-width flanges. The web rectangle
    and the two flange rectangles are treated as non-overlapping components.
    """
    _validate_dimension("overall_depth_m", overall_depth_m)
    _validate_dimension("flange_width_m", flange_width_m)
    _validate_dimension("web_thickness_m", web_thickness_m)
    _validate_dimension("flange_thickness_m", flange_thickness_m)
    if web_thickness_m >= flange_width_m:
        raise ValueError("web_thickness_m must be less than flange_width_m.")
    if 2 * flange_thickness_m >= overall_depth_m:
        raise ValueError(
            "twice flange_thickness_m must be less than overall_depth_m."
        )

    web_height_m = overall_depth_m - 2 * flange_thickness_m
    flange_area_m2 = flange_width_m * flange_thickness_m
    web_area_m2 = web_thickness_m * web_height_m
    area_m2 = 2 * flange_area_m2 + web_area_m2
    flange_centroid_offset_m = (overall_depth_m - flange_thickness_m) / 2
    second_moment_x_m4 = (
        web_thickness_m * web_height_m**3 / 12
        + 2
        * (
            flange_width_m * flange_thickness_m**3 / 12
            + flange_area_m2 * flange_centroid_offset_m**2
        )
    )
    second_moment_y_m4 = (
        web_height_m * web_thickness_m**3 / 12
        + 2 * flange_thickness_m * flange_width_m**3 / 12
    )
    _validate_section_property("area_m2", area_m2, "m^2")
    _validate_section_property("second_moment_x_m4", second_moment_x_m4, "m^4")
    _validate_section_property("second_moment_y_m4", second_moment_y_m4, "m^4")

    if second_moment_x_m4 < second_moment_y_m4:
        minimum_second_moment_m4 = second_moment_x_m4
        weaker_axis = "x"
    elif second_moment_y_m4 < second_moment_x_m4:
        minimum_second_moment_m4 = second_moment_y_m4
        weaker_axis = "y"
    else:
        minimum_second_moment_m4 = second_moment_x_m4
        weaker_axis = "both"

    return SectionProperties(
        area_m2=area_m2,
        second_moment_x_m4=second_moment_x_m4,
        second_moment_y_m4=second_moment_y_m4,
        minimum_second_moment_m4=minimum_second_moment_m4,
        weaker_axis=weaker_axis,
        centroid_x_m=flange_width_m / 2,
        centroid_y_m=overall_depth_m / 2,
    )


def channel_section(
    overall_depth_m: float,
    flange_width_m: float,
    web_thickness_m: float,
    flange_thickness_m: float,
) -> SectionProperties:
    """Calculate properties for a channel opening to the right.

    The web occupies the left side of the bounding box, and the flange width
    is the overall section width. The section is symmetric about its
    horizontal centroidal axis, so its centroidal product of inertia is zero.
    """
    _validate_dimension("overall_depth_m", overall_depth_m)
    _validate_dimension("flange_width_m", flange_width_m)
    _validate_dimension("web_thickness_m", web_thickness_m)
    _validate_dimension("flange_thickness_m", flange_thickness_m)
    if web_thickness_m >= flange_width_m:
        raise ValueError("web_thickness_m must be less than flange_width_m.")
    if 2 * flange_thickness_m >= overall_depth_m:
        raise ValueError(
            "twice flange_thickness_m must be less than overall_depth_m."
        )

    flange_extension_width_m = flange_width_m - web_thickness_m
    web_area_m2 = web_thickness_m * overall_depth_m
    flange_area_m2 = flange_extension_width_m * flange_thickness_m
    area_m2 = web_area_m2 + 2 * flange_area_m2
    centroid_x_m = (
        web_area_m2 * (web_thickness_m / 2)
        + 2 * flange_area_m2 * ((flange_width_m + web_thickness_m) / 2)
    ) / area_m2
    centroid_y_m = overall_depth_m / 2
    flange_centroid_offset_m = (overall_depth_m - flange_thickness_m) / 2
    flange_extension_centroid_x_m = (flange_width_m + web_thickness_m) / 2
    second_moment_x_m4 = (
        web_thickness_m * overall_depth_m**3 / 12
        + 2
        * (
            flange_extension_width_m * flange_thickness_m**3 / 12
            + flange_area_m2 * flange_centroid_offset_m**2
        )
    )
    second_moment_y_m4 = (
        overall_depth_m * web_thickness_m**3 / 12
        + web_area_m2 * (web_thickness_m / 2 - centroid_x_m) ** 2
        + 2
        * (
            flange_thickness_m * flange_extension_width_m**3 / 12
            + flange_area_m2
            * (flange_extension_centroid_x_m - centroid_x_m) ** 2
        )
    )

    return _section_from_centroidal_moments(
        area_m2,
        centroid_x_m,
        centroid_y_m,
        second_moment_x_m4,
        second_moment_y_m4,
        0.0,
    )


def angle_section(
    horizontal_leg_m: float,
    vertical_leg_m: float,
    thickness_m: float,
) -> SectionProperties:
    """Calculate properties for an L-section with legs along the bottom and left.

    The horizontal leg extends right from the lower-left corner and the
    vertical leg extends upward. Their shared square is subtracted once.
    """
    _validate_dimension("horizontal_leg_m", horizontal_leg_m)
    _validate_dimension("vertical_leg_m", vertical_leg_m)
    _validate_dimension("thickness_m", thickness_m)
    if thickness_m >= horizontal_leg_m:
        raise ValueError(
            "thickness_m must be less than horizontal_leg_m."
        )
    if thickness_m >= vertical_leg_m:
        raise ValueError(
            "thickness_m must be less than vertical_leg_m."
        )

    return _composite_rectangular_section(
        (
            (0.0, 0.0, thickness_m, vertical_leg_m, 1.0),
            (0.0, 0.0, horizontal_leg_m, thickness_m, 1.0),
            (0.0, 0.0, thickness_m, thickness_m, -1.0),
        )
    )


def t_section(
    overall_depth_m: float,
    flange_width_m: float,
    web_thickness_m: float,
    flange_thickness_m: float,
) -> SectionProperties:
    """Calculate properties for a T-section with its flange at the top."""
    _validate_dimension("overall_depth_m", overall_depth_m)
    _validate_dimension("flange_width_m", flange_width_m)
    _validate_dimension("web_thickness_m", web_thickness_m)
    _validate_dimension("flange_thickness_m", flange_thickness_m)
    if web_thickness_m >= flange_width_m:
        raise ValueError("web_thickness_m must be less than flange_width_m.")
    if 2 * flange_thickness_m >= overall_depth_m:
        raise ValueError(
            "twice flange_thickness_m must be less than overall_depth_m."
        )

    web_height_m = overall_depth_m - flange_thickness_m
    web_area_m2 = web_thickness_m * web_height_m
    flange_area_m2 = flange_width_m * flange_thickness_m
    area_m2 = web_area_m2 + flange_area_m2
    centroid_x_m = flange_width_m / 2
    centroid_y_m = (
        web_area_m2 * (web_height_m / 2)
        + flange_area_m2 * (overall_depth_m - flange_thickness_m / 2)
    ) / area_m2
    second_moment_x_m4 = (
        web_thickness_m * web_height_m**3 / 12
        + web_area_m2 * (web_height_m / 2 - centroid_y_m) ** 2
        + flange_width_m * flange_thickness_m**3 / 12
        + flange_area_m2
        * (overall_depth_m - flange_thickness_m / 2 - centroid_y_m) ** 2
    )
    second_moment_y_m4 = (
        web_height_m * web_thickness_m**3 / 12
        + flange_thickness_m * flange_width_m**3 / 12
    )

    return _section_from_centroidal_moments(
        area_m2,
        centroid_x_m,
        centroid_y_m,
        second_moment_x_m4,
        second_moment_y_m4,
        0.0,
    )
