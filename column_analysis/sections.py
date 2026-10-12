"""Cross-section geometry and properties using SI units."""

from dataclasses import dataclass
from math import isfinite, pi


@dataclass(frozen=True)
class SectionProperties:
    """Geometric section properties in SI units.

    The x and y values are centroidal second moments of area in m^4.
    """

    area_m2: float
    second_moment_x_m4: float
    second_moment_y_m4: float
    minimum_second_moment_m4: float
    weaker_axis: str


def _validate_dimension(name: str, dimension_m: float) -> None:
    """Require a finite, positive dimension given in metres."""
    if not isfinite(dimension_m) or dimension_m <= 0:
        raise ValueError(f"{name} must be a finite positive value in metres.")


def solid_circular_section(diameter_m: float) -> SectionProperties:
    """Calculate properties for a solid circle with diameter in metres."""
    _validate_dimension("diameter_m", diameter_m)

    area_m2 = pi * diameter_m**2 / 4
    second_moment_m4 = pi * diameter_m**4 / 64

    return SectionProperties(
        area_m2=area_m2,
        second_moment_x_m4=second_moment_m4,
        second_moment_y_m4=second_moment_m4,
        minimum_second_moment_m4=second_moment_m4,
        weaker_axis="both",
    )


def rectangular_section(width_m: float, height_m: float) -> SectionProperties:
    """Calculate rectangular properties for width and height in metres.

    The width is along x and the height is along y. ``Ix`` is about the
    centroidal x-axis (parallel to the width), and ``Iy`` is about the
    centroidal y-axis (parallel to the height).
    """
    _validate_dimension("width_m", width_m)
    _validate_dimension("height_m", height_m)

    area_m2 = width_m * height_m
    second_moment_x_m4 = width_m * height_m**3 / 12
    second_moment_y_m4 = height_m * width_m**3 / 12

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
    )