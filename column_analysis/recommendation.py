"""Deterministic theory applicability checks using explicit reference criteria."""

import json
from dataclasses import dataclass
from math import isfinite, pi, sqrt
from pathlib import Path

from column_analysis.validation import ApplicabilityStatus, TheoryName, validate_positive_finite


_CRITERIA_PATH = Path(__file__).with_name("applicability_criteria.json")
_RANKINE_FORMULA_CONVENTION = (
    "P_R = sigma_c * A / (1 + a * (Le / k)^2)"
)


@dataclass(frozen=True)
class ApplicabilityCriteria:
    """Configurable ranges, conventions, and references for theory selection."""

    transition_rule: str
    transition_reference: str
    transition_reference_url: str
    johnson_minimum_slenderness_ratio: float | None
    johnson_range_reference: str | None
    johnson_range_reference_url: str | None
    rankine_minimum_slenderness_ratio: float | None
    rankine_maximum_slenderness_ratio: float | None
    rankine_constant_dimensionless: float | None
    rankine_constant_convention: str
    rankine_reference: str | None
    rankine_reference_url: str | None
    preferred_theory_order: tuple[TheoryName, ...]


@dataclass(frozen=True)
class TheoryReview:
    """Applicability and rationale for one candidate theory."""

    theory: TheoryName
    status: ApplicabilityStatus
    explanation: str
    missing_inputs: tuple[str, ...]
    supporting_reference: str
    reference_url: str | None


@dataclass(frozen=True)
class TheoryRecommendation:
    """Recommendation and the engineering inputs used to assess it."""

    recommended_theory: TheoryName | None
    explanation: str
    slenderness_ratio: float
    material_properties: dict[str, float | None]
    theory_reviews: tuple[TheoryReview, ...]
    candidate_theories: tuple[TheoryName, ...]
    euler_johnson_transition_ratio: float | None
    applied_load_kn: float | None
    critical_loads_n: dict[TheoryName, float | None]


def load_applicability_criteria() -> ApplicabilityCriteria:
    """Load and validate the explicit local theory criteria and references."""
    data = json.loads(_CRITERIA_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError(
            f"{_CRITERIA_PATH} must use applicability criteria schema version 1."
        )

    euler_johnson = data.get("euler_johnson")
    rankine = data.get("rankine_gordon")
    if not isinstance(euler_johnson, dict) or not isinstance(rankine, dict):
        raise ValueError("Applicability criteria need euler_johnson and rankine_gordon objects.")

    transition_rule = euler_johnson.get("transition_rule")
    if transition_rule != "euler_stress_equals_half_yield":
        raise ValueError(f"Unsupported Euler/Johnson transition rule {transition_rule!r}.")

    transition_reference = _required_text(euler_johnson, "transition_reference")
    transition_reference_url = _required_url(euler_johnson, "transition_reference_url")
    johnson_minimum = _optional_nonnegative(
        euler_johnson.get("johnson_minimum_slenderness_ratio"),
        "johnson_minimum_slenderness_ratio",
    )
    johnson_reference = _optional_text(euler_johnson.get("johnson_range_reference"))
    johnson_url = _optional_url(euler_johnson.get("johnson_range_reference_url"))
    if (johnson_minimum is None) != (johnson_reference is None) or (
        johnson_minimum is None
    ) != (johnson_url is None):
        raise ValueError(
            "A configured Johnson lower bound must include its reference and HTTPS URL."
        )

    rankine_minimum = _optional_nonnegative(
        rankine.get("minimum_slenderness_ratio"),
        "Rankine minimum_slenderness_ratio",
    )
    rankine_maximum = _optional_positive(
        rankine.get("maximum_slenderness_ratio"),
        "Rankine maximum_slenderness_ratio",
    )
    rankine_constant = _optional_positive(
        rankine.get("constant_dimensionless"),
        "Rankine constant_dimensionless",
    )
    rankine_convention = _required_text(rankine, "constant_convention")
    if rankine_convention != _RANKINE_FORMULA_CONVENTION:
        raise ValueError(
            "Rankine constant_convention must match the formula implemented by this project."
        )
    rankine_reference = _optional_text(rankine.get("reference"))
    rankine_url = _optional_url(rankine.get("reference_url"))
    rankine_fields = (
        rankine_minimum,
        rankine_maximum,
        rankine_constant,
        rankine_reference,
        rankine_url,
    )
    if any(field is not None for field in rankine_fields):
        if any(field is None for field in rankine_fields):
            raise ValueError(
                "Rankine criteria require both range bounds, a dimensionless constant, "
                "and its reference with HTTPS URL."
            )
        if rankine_maximum <= rankine_minimum:
            raise ValueError("Rankine maximum slenderness must exceed its minimum.")

    preference_values = data.get("preferred_theory_order", [])
    if not isinstance(preference_values, list):
        raise ValueError("preferred_theory_order must be a list.")
    try:
        preference = tuple(TheoryName(value) for value in preference_values)
    except (TypeError, ValueError):
        raise ValueError("preferred_theory_order contains an unsupported theory.") from None
    if len(set(preference)) != len(preference):
        raise ValueError("preferred_theory_order cannot contain duplicate theories.")

    return ApplicabilityCriteria(
        transition_rule=transition_rule,
        transition_reference=transition_reference,
        transition_reference_url=transition_reference_url,
        johnson_minimum_slenderness_ratio=johnson_minimum,
        johnson_range_reference=johnson_reference,
        johnson_range_reference_url=johnson_url,
        rankine_minimum_slenderness_ratio=rankine_minimum,
        rankine_maximum_slenderness_ratio=rankine_maximum,
        rankine_constant_dimensionless=rankine_constant,
        rankine_constant_convention=rankine_convention,
        rankine_reference=rankine_reference,
        rankine_reference_url=rankine_url,
        preferred_theory_order=preference,
    )


def _required_text(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Applicability criteria need a non-empty {key!r}.")
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Optional applicability references must be non-empty text or null.")
    return value


def _required_url(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.startswith("https://"):
        raise ValueError(f"Applicability criteria need an HTTPS {key!r}.")
    return value


def _optional_url(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.startswith("https://"):
        raise ValueError("Optional applicability source URLs must use HTTPS or be null.")
    return value


def _optional_positive(value: object, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a positive finite number or null.")
    validate_positive_finite(name, float(value), "dimensionless")
    return float(value)


def _optional_nonnegative(value: object, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a non-negative finite number or null.")
    resolved = float(value)
    if not isfinite(resolved) or resolved < 0:
        raise ValueError(f"{name} must be a non-negative finite number or null.")
    return resolved


def _validate_criteria(criteria: ApplicabilityCriteria) -> None:
    if criteria.transition_rule != "euler_stress_equals_half_yield":
        raise ValueError(f"Unsupported Euler/Johnson transition rule {criteria.transition_rule!r}.")
    if not criteria.transition_reference.strip() or not criteria.transition_reference_url.startswith(
        "https://"
    ):
        raise ValueError("Euler/Johnson transition criteria need a named HTTPS reference.")
    if criteria.johnson_minimum_slenderness_ratio is not None:
        if (
            not isfinite(criteria.johnson_minimum_slenderness_ratio)
            or criteria.johnson_minimum_slenderness_ratio < 0
        ):
            raise ValueError(
                "johnson_minimum_slenderness_ratio must be finite and non-negative."
            )
        if (
            not criteria.johnson_range_reference
            or not criteria.johnson_range_reference_url
            or not criteria.johnson_range_reference_url.startswith("https://")
        ):
            raise ValueError(
                "A configured Johnson lower bound needs a named HTTPS reference."
            )
    elif (
        criteria.johnson_range_reference is not None
        or criteria.johnson_range_reference_url is not None
    ):
        raise ValueError("Johnson lower-bound references require a configured lower bound.")

    rankine_values = (
        criteria.rankine_minimum_slenderness_ratio,
        criteria.rankine_maximum_slenderness_ratio,
        criteria.rankine_constant_dimensionless,
        criteria.rankine_reference,
        criteria.rankine_reference_url,
    )
    if any(value is not None for value in rankine_values):
        if any(value is None for value in rankine_values):
            raise ValueError(
                "Rankine criteria need both range bounds, a constant, and a named HTTPS reference."
            )
        validate_positive_finite(
            "rankine_maximum_slenderness_ratio",
            criteria.rankine_maximum_slenderness_ratio,
            "dimensionless",
        )
        if (
            not isfinite(criteria.rankine_minimum_slenderness_ratio)
            or criteria.rankine_minimum_slenderness_ratio < 0
            or criteria.rankine_maximum_slenderness_ratio
            <= criteria.rankine_minimum_slenderness_ratio
        ):
            raise ValueError("Rankine slenderness bounds must be finite and increasing.")
        validate_positive_finite(
            "rankine_constant_dimensionless",
            criteria.rankine_constant_dimensionless,
            "dimensionless",
        )
        if (
            not criteria.rankine_reference.strip()
            or not criteria.rankine_reference_url.startswith("https://")
            or criteria.rankine_constant_convention != _RANKINE_FORMULA_CONVENTION
        ):
            raise ValueError(
                "Rankine criteria need a named HTTPS reference and this project's exact formula convention."
            )
    elif criteria.rankine_constant_convention != _RANKINE_FORMULA_CONVENTION:
        raise ValueError(
            "Rankine constant_convention must match the formula implemented by this project."
        )

    if len(set(criteria.preferred_theory_order)) != len(criteria.preferred_theory_order):
        raise ValueError("preferred_theory_order cannot contain duplicate theories.")


def recommend_theory(
    slenderness_ratio: float,
    *,
    youngs_modulus_gpa: float | None,
    compressive_strength_mpa: float | None,
    rankine_constant_dimensionless: float | None,
    yield_stress_mpa: float | None,
    applied_load_kn: float | None = None,
    critical_loads_n: dict[TheoryName, float | None] | None = None,
    criteria: ApplicabilityCriteria | None = None,
) -> TheoryRecommendation:
    """Evaluate every theory independently without comparing predicted loads.

    The Euler/Johnson transition is derived from the cited criterion that
    Euler critical stress equals half the material yield strength. Johnson
    is not recommended unless its separate lower-range criterion has also
    been configured. Rankine requires a referenced range and exact matching
    constant/convention in the local criteria file.
    """
    validate_positive_finite("slenderness_ratio", slenderness_ratio, "dimensionless")
    for name, value, unit in (
        ("youngs_modulus_gpa", youngs_modulus_gpa, "GPa"),
        ("compressive_strength_mpa", compressive_strength_mpa, "MPa"),
        ("rankine_constant_dimensionless", rankine_constant_dimensionless, "dimensionless"),
        ("yield_stress_mpa", yield_stress_mpa, "MPa"),
        ("applied_load_kn", applied_load_kn, "kN"),
    ):
        if value is not None:
            validate_positive_finite(name, value, unit)

    resolved_criteria = criteria or load_applicability_criteria()
    _validate_criteria(resolved_criteria)
    transition_ratio = None
    transition_missing = tuple(
        label
        for label, value in (
            ("Young's modulus E", youngs_modulus_gpa),
            ("yield stress sigma_y", yield_stress_mpa),
        )
        if value is None
    )
    if not transition_missing:
        transition_ratio = sqrt(
            2 * pi**2 * (youngs_modulus_gpa * 1e9) / (yield_stress_mpa * 1e6)
        )

    reviews: dict[TheoryName, TheoryReview] = {}
    candidates: list[TheoryName] = []

    if transition_missing:
        reviews[TheoryName.EULER] = TheoryReview(
            TheoryName.EULER,
            ApplicabilityStatus.INPUT_REQUIRED,
            "Cannot check Euler's slender-column range against the configured transition.",
            transition_missing,
            resolved_criteria.transition_reference,
            resolved_criteria.transition_reference_url,
        )
    elif slenderness_ratio >= transition_ratio:
        candidates.append(TheoryName.EULER)
        reviews[TheoryName.EULER] = TheoryReview(
            TheoryName.EULER,
            ApplicabilityStatus.APPLICABLE,
            (
                f"Slenderness {slenderness_ratio:.6g} is at or above the configured "
                f"Euler/Johnson transition {transition_ratio:.6g}; Euler's elastic "
                "buckling assumptions are the matching range under this criterion. "
                "This presumes a straight, prismatic member under concentric axial "
                "compression with the selected idealized end restraints."
            ),
            (),
            resolved_criteria.transition_reference,
            resolved_criteria.transition_reference_url,
        )
    else:
        reviews[TheoryName.EULER] = TheoryReview(
            TheoryName.EULER,
            ApplicabilityStatus.OUT_OF_RANGE,
            (
                f"Slenderness {slenderness_ratio:.6g} is below the Euler/Johnson "
                f"transition {transition_ratio:.6g}; Euler is outside the configured "
                "long-column range."
            ),
            (),
            resolved_criteria.transition_reference,
            resolved_criteria.transition_reference_url,
        )

    if transition_missing:
        reviews[TheoryName.JOHNSON] = TheoryReview(
            TheoryName.JOHNSON,
            ApplicabilityStatus.INPUT_REQUIRED,
            "Cannot check Johnson's intermediate-column range against the configured transition.",
            transition_missing,
            resolved_criteria.transition_reference,
            resolved_criteria.transition_reference_url,
        )
    elif slenderness_ratio >= transition_ratio:
        reviews[TheoryName.JOHNSON] = TheoryReview(
            TheoryName.JOHNSON,
            ApplicabilityStatus.OUT_OF_RANGE,
            (
                f"Slenderness {slenderness_ratio:.6g} is at or above the configured "
                f"Euler/Johnson transition {transition_ratio:.6g}; Johnson is outside "
                "its configured intermediate-column range."
            ),
            (),
            resolved_criteria.transition_reference,
            resolved_criteria.transition_reference_url,
        )
    elif resolved_criteria.johnson_minimum_slenderness_ratio is None:
        reviews[TheoryName.JOHNSON] = TheoryReview(
            TheoryName.JOHNSON,
            ApplicabilityStatus.CRITERION_NOT_CONFIGURED,
            (
                "The cited reference supplies the Euler/Johnson upper transition but not "
                "a lower boundary distinguishing Johnson intermediate columns from "
                "short compression members. Configure that lower bound and its reference "
                "before recommending Johnson."
            ),
            ("Johnson lower slenderness boundary and its source",),
            resolved_criteria.transition_reference,
            resolved_criteria.transition_reference_url,
        )
    elif (
        resolved_criteria.johnson_minimum_slenderness_ratio
        <= slenderness_ratio
        < transition_ratio
    ):
        if youngs_modulus_gpa is not None and yield_stress_mpa is not None:
            candidates.append(TheoryName.JOHNSON)
        reviews[TheoryName.JOHNSON] = TheoryReview(
            TheoryName.JOHNSON,
            ApplicabilityStatus.APPLICABLE,
            (
                f"Slenderness {slenderness_ratio:.6g} is within the configured Johnson "
                f"range [{resolved_criteria.johnson_minimum_slenderness_ratio:.6g}, "
                f"{transition_ratio:.6g}); E and yield stress are available. This is the "
                "classical theoretical Johnson range, not a certification of short-column "
                "behavior. Very low slenderness may be crushing-dominated; no separate "
                "numerical crushing crossover is configured. Check verified compressive "
                "strength separately. The model presumes a straight, prismatic member under "
                "concentric axial compression with the selected idealized end restraints."
            ),
            (),
            resolved_criteria.johnson_range_reference or "Configured Johnson range",
            resolved_criteria.johnson_range_reference_url,
        )
    else:
        reviews[TheoryName.JOHNSON] = TheoryReview(
            TheoryName.JOHNSON,
            ApplicabilityStatus.OUT_OF_RANGE,
            (
                f"Slenderness {slenderness_ratio:.6g} is below the configured Johnson "
                f"lower boundary {resolved_criteria.johnson_minimum_slenderness_ratio:.6g}; "
                "this is the short-column/crushing-dominated region. Check the member "
                "separately against a verified compressive/crushing strength."
            ),
            (),
            resolved_criteria.johnson_range_reference or "Configured Johnson range",
            resolved_criteria.johnson_range_reference_url,
        )

    rankine_configured = (
        resolved_criteria.rankine_minimum_slenderness_ratio is not None
        and resolved_criteria.rankine_maximum_slenderness_ratio is not None
        and resolved_criteria.rankine_constant_dimensionless is not None
        and resolved_criteria.rankine_reference is not None
        and resolved_criteria.rankine_reference_url is not None
    )
    rankine_missing: list[str] = []
    if compressive_strength_mpa is None:
        rankine_missing.append("compressive/crushing strength sigma_c")
    if rankine_constant_dimensionless is None:
        rankine_missing.append("Rankine constant a")
    if not rankine_configured:
        rankine_missing.append(
            "configured Rankine range, constant convention, and reference"
        )
    if not rankine_configured:
        reviews[TheoryName.RANKINE] = TheoryReview(
            TheoryName.RANKINE,
            (
                ApplicabilityStatus.INPUT_REQUIRED
                if compressive_strength_mpa is None or rankine_constant_dimensionless is None
                else ApplicabilityStatus.CRITERION_NOT_CONFIGURED
            ),
            (
                "Rankine-Gordon cannot be recommended without the configured range, "
                "a documented constant/convention, a matching supplied constant, and "
                "compressive strength."
            ),
            tuple(rankine_missing),
            "Rankine criteria are not configured in applicability_criteria.json.",
            None,
        )
    elif rankine_missing:
        if (
            rankine_constant_dimensionless is not None
            and rankine_constant_dimensionless
            != resolved_criteria.rankine_constant_dimensionless
        ):
            rankine_missing.append(
                "Rankine constant a matching the configured reference"
            )
        reviews[TheoryName.RANKINE] = TheoryReview(
            TheoryName.RANKINE,
            ApplicabilityStatus.INPUT_REQUIRED,
            "Rankine-Gordon needs compressive/crushing strength and the configured constant.",
            tuple(rankine_missing),
            resolved_criteria.rankine_reference,
            resolved_criteria.rankine_reference_url,
        )
    elif rankine_constant_dimensionless != resolved_criteria.rankine_constant_dimensionless:
        reviews[TheoryName.RANKINE] = TheoryReview(
            TheoryName.RANKINE,
            ApplicabilityStatus.INPUT_REQUIRED,
            "The supplied Rankine constant does not match the value in the configured reference criteria.",
            ("Rankine constant a matching the configured reference",),
            resolved_criteria.rankine_reference,
            resolved_criteria.rankine_reference_url,
        )
    elif (
        resolved_criteria.rankine_minimum_slenderness_ratio
        <= slenderness_ratio
        <= resolved_criteria.rankine_maximum_slenderness_ratio
    ):
        candidates.append(TheoryName.RANKINE)
        reviews[TheoryName.RANKINE] = TheoryReview(
            TheoryName.RANKINE,
            ApplicabilityStatus.APPLICABLE,
            (
                f"Slenderness {slenderness_ratio:.6g} is within the configured Rankine "
                f"range [{resolved_criteria.rankine_minimum_slenderness_ratio:.6g}, "
                f"{resolved_criteria.rankine_maximum_slenderness_ratio:.6g}]. "
                f"Configured convention: {resolved_criteria.rankine_constant_convention}"
            ),
            (),
            resolved_criteria.rankine_reference,
            resolved_criteria.rankine_reference_url,
        )
    else:
        reviews[TheoryName.RANKINE] = TheoryReview(
            TheoryName.RANKINE,
            ApplicabilityStatus.OUT_OF_RANGE,
            (
                f"Slenderness {slenderness_ratio:.6g} is outside the configured Rankine "
                f"range [{resolved_criteria.rankine_minimum_slenderness_ratio:.6g}, "
                f"{resolved_criteria.rankine_maximum_slenderness_ratio:.6g}]."
            ),
            (),
            resolved_criteria.rankine_reference,
            resolved_criteria.rankine_reference_url,
        )

    selected_theory = None
    if len(candidates) == 1:
        selected_theory = candidates[0]
    elif len(candidates) > 1:
        selected_theory = next(
            (
                theory
                for theory in resolved_criteria.preferred_theory_order
                if theory in candidates
            ),
            None,
        )

    if selected_theory is not None:
        explanation = (
            f"{selected_theory.value} is selected from the configured applicability "
            "criteria, not by comparing predicted loads. This is not a safety determination."
        )
        if len(candidates) > 1:
            explanation += (
                " Other applicable candidates: "
                + ", ".join(candidate.value for candidate in candidates if candidate != selected_theory)
                + ". The configured theory preference order resolves the overlap."
            )
    elif candidates:
        explanation = (
            "More than one theory meets its configured criteria, but no reference-backed "
            "preference resolves the overlap: "
            + ", ".join(theory.value for theory in candidates)
            + ". Configure a course-specific preference order."
        )
    else:
        explanation = (
            "Insufficient information to recommend. No theory has both the required "
            "material data and a fully configured, matching applicability criterion."
        )

    resolved_loads = dict(critical_loads_n or {})
    return TheoryRecommendation(
        recommended_theory=selected_theory,
        explanation=explanation,
        slenderness_ratio=slenderness_ratio,
        material_properties={
            "youngs_modulus_gpa": youngs_modulus_gpa,
            "compressive_strength_mpa": compressive_strength_mpa,
            "rankine_constant_dimensionless": rankine_constant_dimensionless,
            "yield_stress_mpa": yield_stress_mpa,
        },
        theory_reviews=tuple(reviews[theory] for theory in TheoryName),
        candidate_theories=tuple(candidates),
        euler_johnson_transition_ratio=transition_ratio,
        applied_load_kn=applied_load_kn,
        critical_loads_n=resolved_loads,
    )
