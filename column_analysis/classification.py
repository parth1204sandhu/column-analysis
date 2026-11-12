"""Material-dependent, configurable column classification screening."""

import json
from dataclasses import dataclass
from enum import Enum
from math import isfinite, pi, sqrt
from pathlib import Path


_CLASSIFICATION_PATH = Path(__file__).with_name("classification_criteria.json")


class ColumnClass(str, Enum):
    """Slenderness-based column classification labels."""

    SHORT = "Short"
    INTERMEDIATE = "Intermediate"
    LONG = "Long"


@dataclass(frozen=True)
class ColumnClassificationCriteria:
    """Model configuration, formulas, assumptions, and source."""

    model: str
    description: str
    short_euler_stress_to_yield_ratio: float
    intermediate_euler_stress_to_yield_ratio: float
    short_boundary_equation: str
    short_boundary_derivation: str
    intermediate_boundary_equation: str
    intermediate_boundary_derivation: str
    units: dict[str, str]
    assumptions: tuple[str, ...]
    reference: str
    reference_url: str


@dataclass(frozen=True)
class ColumnClassification:
    """Display-ready result, ranges, and rationale."""

    classification: ColumnClass | None
    slenderness_ratio: float | None
    short_max_slenderness_ratio: float | None
    intermediate_max_slenderness_ratio: float | None
    applicable_range: str
    explanation: str
    reference: str
    reference_url: str


def load_column_classification_criteria() -> ColumnClassificationCriteria:
    """Load and validate the separate classification model configuration."""
    data = json.loads(_CLASSIFICATION_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError(
            f"{_CLASSIFICATION_PATH} must use classification criteria schema version 1."
        )
    short = data.get("short_boundary")
    intermediate = data.get("intermediate_upper_boundary")
    units = data.get("units")
    assumptions = data.get("assumptions")
    if not all(isinstance(item, dict) for item in (short, intermediate, units)):
        raise ValueError("Classification criteria need boundary and units objects.")
    if (
        not isinstance(assumptions, list)
        or not assumptions
        or any(not isinstance(item, str) or not item.strip() for item in assumptions)
    ):
        raise ValueError("Classification criteria need non-empty textual assumptions.")

    short_ratio = _positive_number(
        short.get("euler_stress_to_yield_ratio"),
        "short_boundary.euler_stress_to_yield_ratio",
    )
    intermediate_ratio = _positive_number(
        intermediate.get("euler_stress_to_yield_ratio"),
        "intermediate_upper_boundary.euler_stress_to_yield_ratio",
    )
    if intermediate_ratio >= short_ratio:
        raise ValueError(
            "The intermediate boundary stress ratio must be less than the short boundary ratio."
        )

    resolved_units = {
        key: _required_text(units, key)
        for key in ("slenderness_ratio", "youngs_modulus", "yield_stress")
    }
    return ColumnClassificationCriteria(
        model=_required_text(data, "model"),
        description=_required_text(data, "description"),
        short_euler_stress_to_yield_ratio=short_ratio,
        intermediate_euler_stress_to_yield_ratio=intermediate_ratio,
        short_boundary_equation=_required_text(short, "equation"),
        short_boundary_derivation=_required_text(short, "derivation"),
        intermediate_boundary_equation=_required_text(intermediate, "equation"),
        intermediate_boundary_derivation=_required_text(intermediate, "derivation"),
        units=resolved_units,
        assumptions=tuple(assumptions),
        reference=_required_text(data, "reference"),
        reference_url=_required_https_url(data, "reference_url"),
    )


def classify_column(
    slenderness_ratio: float | None,
    criteria: ColumnClassificationCriteria,
    *,
    youngs_modulus_pa: float | None,
    yield_stress_pa: float | None,
) -> ColumnClassification:
    """Classify by material-dependent elastic-Euler stress/yield comparisons.

    The lower boundary is where Euler elastic critical stress reaches yield.
    The upper boundary uses the configured classical Johnson/Euler transition.
    Yield is a theoretical screening input only, not crushing capacity.
    """
    if slenderness_ratio is None or not _is_positive_finite(slenderness_ratio):
        return _unavailable(
            slenderness_ratio if _is_finite_number(slenderness_ratio) else None,
            "A finite positive slenderness ratio is required.",
            criteria,
        )
    if youngs_modulus_pa is None or not _is_positive_finite(youngs_modulus_pa):
        return _unavailable(
            float(slenderness_ratio),
            "A verified, finite positive Young's modulus is required by the configured criterion.",
            criteria,
        )
    if yield_stress_pa is None or not _is_positive_finite(yield_stress_pa):
        return _unavailable(
            float(slenderness_ratio),
            "A verified, finite positive yield stress for the selected material condition is "
            "required by the configured criterion.",
            criteria,
        )

    ratio = float(slenderness_ratio)
    modulus = float(youngs_modulus_pa)
    yield_stress = float(yield_stress_pa)
    short_maximum = pi * sqrt(
        modulus
        / (criteria.short_euler_stress_to_yield_ratio * yield_stress)
    )
    intermediate_maximum = pi * sqrt(
        modulus
        / (
            criteria.intermediate_euler_stress_to_yield_ratio
            * yield_stress
        )
    )
    if not isfinite(short_maximum) or not isfinite(intermediate_maximum):
        return _unavailable(
            ratio,
            "The configured material properties produced non-finite classification limits.",
            criteria,
        )

    if ratio <= short_maximum:
        category = ColumnClass.SHORT
        applicable_range = f"0 < lambda <= {short_maximum:.6g}"
        explanation = (
            f"The Euler elastic critical stress is at least the configured yield limit "
            f"through lambda = {short_maximum:.6g}; yielding/crushing behavior is expected "
            "to govern before ideal elastic buckling."
        )
    elif ratio <= intermediate_maximum:
        category = ColumnClass.INTERMEDIATE
        applicable_range = (
            f"{short_maximum:.6g} < lambda <= {intermediate_maximum:.6g}"
        )
        explanation = (
            f"The Euler stress has fallen below the yield limit but remains at or above "
            "one half of it; this configured elastic-yield screening band represents "
            "combined inelastic compression and buckling behavior."
        )
    else:
        category = ColumnClass.LONG
        applicable_range = f"lambda > {intermediate_maximum:.6g}"
        explanation = (
            f"The Euler stress is below one half of the yield limit beyond "
            f"lambda = {intermediate_maximum:.6g}; elastic buckling is the governing "
            "classification regime in this model."
        )

    return ColumnClassification(
        classification=category,
        slenderness_ratio=ratio,
        short_max_slenderness_ratio=short_maximum,
        intermediate_max_slenderness_ratio=intermediate_maximum,
        applicable_range=applicable_range,
        explanation=explanation,
        reference=criteria.reference,
        reference_url=criteria.reference_url,
    )


def _unavailable(
    slenderness_ratio: float | None,
    explanation: str,
    criteria: ColumnClassificationCriteria,
) -> ColumnClassification:
    return ColumnClassification(
        classification=None,
        slenderness_ratio=slenderness_ratio,
        short_max_slenderness_ratio=None,
        intermediate_max_slenderness_ratio=None,
        applicable_range="Unavailable",
        explanation=explanation,
        reference=criteria.reference,
        reference_url=criteria.reference_url,
    )


def _positive_number(value: object, name: str) -> float:
    if not _is_positive_finite(value):
        raise ValueError(f"{name} must be a positive finite number.")
    return float(value)


def _required_text(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Classification criteria need non-empty {key!r}.")
    return value


def _required_https_url(data: dict, key: str) -> str:
    value = _required_text(data, key)
    if not value.startswith("https://"):
        raise ValueError(f"Classification criteria need an HTTPS {key!r}.")
    return value


def _is_finite_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return isfinite(float(value))
    except OverflowError:
        return False


def _is_positive_finite(value: object) -> bool:
    return _is_finite_number(value) and float(value) > 0
