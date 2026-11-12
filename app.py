from dataclasses import replace
from math import isfinite

import streamlit as st
import plotly.graph_objects as go

from column_analysis.classification import (
    ColumnClassification,
    classify_column,
    load_column_classification_criteria,
)
from column_analysis.graph_data import build_slenderness_curve_data
from column_analysis.materials import MaterialGrade, load_material_database
from column_analysis.properties import (
    EndCondition,
    effective_length,
    effective_length_factor,
    radius_of_gyration,
    slenderness_ratio,
)
from column_analysis.recommendation import (
    load_applicability_criteria,
    recommend_theory,
)
from column_analysis.sections import rectangular_section, solid_circular_section
from column_analysis.theories import (
    JohnsonOutOfRangeError,
    euler_critical_load,
    johnson_critical_load,
    rankine_critical_load,
)
from column_analysis.validation import (
    ApplicabilityStatus,
    TheoryName,
    validate_engineering_inputs,
    validate_positive_finite,
)


END_CONDITION_LABELS = {
    EndCondition.PINNED_PINNED: "Pinned-pinned",
    EndCondition.FIXED_FIXED: "Fixed-fixed",
    EndCondition.FIXED_FREE: "Fixed-free (cantilever)",
    EndCondition.FIXED_PINNED: "Fixed-pinned",
}

MATERIAL_DATABASE = load_material_database()
MATERIALS_BY_DISPLAY_NAME: dict[str, MaterialGrade] = {
    material.display_name: material for material in MATERIAL_DATABASE.values()
}
MATERIAL_OPTIONS = tuple(MATERIALS_BY_DISPLAY_NAME)
DEFAULT_MATERIAL_NAME = "Structural Steel"

MATERIAL_PROPERTY_LABELS = {
    "youngs_modulus_gpa": "Young's modulus E",
    "compressive_strength_mpa": "Compressive/crushing strength sigma_c",
    "yield_stress_mpa": "Yield stress sigma_y",
    "rankine_constant_dimensionless": "Rankine constant a",
}


def _apply_selected_material() -> None:
    """Populate properties and provenance when the selected material changes."""
    selected_name = st.session_state.get("material_selector", DEFAULT_MATERIAL_NAME)
    selected_material = MATERIALS_BY_DISPLAY_NAME.get(selected_name)
    property_sources: dict[str, str] = {}
    for property_name in MATERIAL_PROPERTY_LABELS:
        property_value = (
            selected_material.properties[property_name].value
            if selected_material is not None
            else None
        )
        st.session_state[property_name] = property_value
        property_sources[property_name] = (
            "database"
            if property_value is not None
            else "unavailable"
            if selected_material is not None
            else "custom"
        )
    st.session_state["material_property_sources"] = property_sources


def _mark_material_property_user_supplied(property_name: str) -> None:
    """Track a manual value separately from the selected database record."""
    property_sources = dict(st.session_state.get("material_property_sources", {}))
    property_sources[property_name] = "user"
    st.session_state["material_property_sources"] = property_sources


def optional_number_input(label: str, key: str, step: float = 1.0) -> float | None:
    """Render an empty numeric input so engineering values are never assumed."""
    return st.number_input(
        label,
        min_value=None,
        max_value=None,
        value=None,
        step=step,
        format="%.6g",
        placeholder="Enter a value",
        key=key,
        on_change=(
            _mark_material_property_user_supplied
            if key in MATERIAL_PROPERTY_LABELS
            else None
        ),
        args=(key,) if key in MATERIAL_PROPERTY_LABELS else (),
    )


_SUPERSCRIPT_DIGITS = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def format_engineering_value(value: float, unit: str) -> str:
    """Format values without truncation, using scientific notation when small or large."""
    if not isfinite(value):
        return f"Not finite {unit}"
    if value == 0:
        return f"0 {unit}"

    mantissa_text, exponent_text = f"{value:.3e}".split("e")
    exponent = int(exponent_text)
    if exponent < -3 or exponent >= 5:
        mantissa = f"{float(mantissa_text):.3f}".rstrip("0").rstrip(".")
        return f"{mantissa} × 10{str(exponent).translate(_SUPERSCRIPT_DIGITS)} {unit}"
    return f"{value:,.5g} {unit}"


def format_critical_load(load_n: float | None) -> str:
    """Format a calculated load in kN or mark it as not calculated."""
    if load_n is None:
        return "Not calculated"
    return format_engineering_value(load_n / 1000, "kN")


def render_column_classification(
    slenderness_ratio_value: float | None,
    *,
    youngs_modulus_pa: float | None = None,
    yield_stress_pa: float | None = None,
) -> ColumnClassification | None:
    """Render a separate slenderness classification without selecting a theory."""
    st.markdown("### Column Classification")
    try:
        classification_criteria = load_column_classification_criteria()
    except ValueError as error:
        st.metric("Classification", "Classification unavailable")
        st.caption(f"Classification criteria could not be loaded or validated: {error}")
        return None

    classification = classify_column(
        slenderness_ratio_value,
        classification_criteria,
        youngs_modulus_pa=youngs_modulus_pa,
        yield_stress_pa=yield_stress_pa,
    )
    classification_columns = st.columns(2)
    classification_columns[0].metric(
        "Classification",
        (
            classification.classification.value
            if classification.classification is not None
            else "Classification unavailable"
        ),
    )
    classification_columns[1].metric(
        "Current slenderness ratio",
        format_engineering_value(classification.slenderness_ratio, "dimensionless")
        if classification.slenderness_ratio is not None
        else "Not available",
    )
    st.write(f"**Applicable classification range:** {classification.applicable_range}")
    if classification.classification is None:
        st.warning(classification.explanation)
    else:
        st.success(
            f"**{classification.classification.value.upper()} COLUMN** — "
            f"{classification.explanation}"
        )
        st.caption(
            f"Reference: [{classification.reference}]({classification.reference_url}). "
            "Classification is a separate assessment; its material-dependent short-column "
            "limit also prevents recommending Johnson in the crushing-dominated range. "
            "It does not replace the independently configured Euler/Johnson transition or "
            "Rankine criteria."
        )
    with st.expander("Classification equations and assumptions"):
        st.markdown(
            f"- Short boundary: `{classification_criteria.short_boundary_equation}` "
            f"({classification_criteria.short_boundary_derivation})\n"
            f"- Intermediate/long boundary: "
            f"`{classification_criteria.intermediate_boundary_equation}` "
            f"({classification_criteria.intermediate_boundary_derivation})\n"
            f"- Units: slenderness `{classification_criteria.units['slenderness_ratio']}`, "
            f"E `{classification_criteria.units['youngs_modulus']}`, "
            f"yield stress `{classification_criteria.units['yield_stress']}`\n"
            + "\n".join(f"- {assumption}" for assumption in classification_criteria.assumptions)
        )
    return classification


st.set_page_config(
    page_title="Column Analysis Studio",
    layout="wide",
)
st.markdown(
    """
    <style>
    :root {
        --studio-bg: #0b1016;
        --studio-panel: #111a24;
        --studio-panel-raised: #15212d;
        --studio-border: #263544;
        --studio-blue: #35a5ff;
        --studio-blue-strong: #1687e8;
        --studio-text: #e8eef5;
        --studio-muted: #91a1b2;
    }
    .stApp {
        color: var(--studio-text);
        background:
            radial-gradient(ellipse at 14% 0%, rgba(32, 87, 132, 0.16), transparent 38%),
            var(--studio-bg);
    }
    [data-testid="stHeader"] { background: rgba(11, 16, 22, 0.88); }
    .block-container {
        max-width: 1440px;
        padding: 1.6rem 2.2rem 2.4rem;
    }
    h1 {
        color: #f3f7fb;
        font-size: 1.85rem !important;
        font-weight: 650 !important;
        margin: 0 0 0.12rem !important;
    }
    h2, h3 {
        color: #dce7f1;
        font-weight: 600 !important;
        margin: 0.72rem 0 0.28rem !important;
    }
    p, label, [data-testid="stMarkdownContainer"] { color: var(--studio-text); }
    div[data-testid="stVerticalBlock"] { gap: 0.62rem; }
    hr { border-color: var(--studio-border); margin: 0.42rem 0 !important; }
    [data-testid="stCaptionContainer"] p { color: var(--studio-muted); }
    [data-testid="stMetric"] {
        min-height: 6.1rem;
        padding: 0.9rem 1rem;
        background: linear-gradient(145deg, var(--studio-panel-raised), var(--studio-panel));
        border: 1px solid var(--studio-border);
        border-radius: 10px;
    }
    [data-testid="stMetricLabel"] p {
        color: var(--studio-muted);
        font-size: 0.82rem;
    }
    [data-testid="stMetricValue"] {
        color: #f3f7fb;
        font-size: 1.22rem;
        font-weight: 620;
    }
    [data-testid="stNumberInput"] input,
    [data-testid="stSelectbox"] [role="combobox"] {
        background-color: #0e1720;
        border-color: #304456;
        border-radius: 8px;
        color: var(--studio-text);
    }
    [data-testid="stCheckbox"] label { color: #d3dfeb; }
    [data-testid="stButton"] button[kind="primary"] {
        min-height: 2.75rem;
        padding: 0.55rem 1.45rem;
        color: #06111b;
        background: linear-gradient(100deg, var(--studio-blue-strong), var(--studio-blue));
        border: 1px solid #63b8ff;
        border-radius: 8px;
        font-weight: 650;
        box-shadow: 0 5px 18px rgba(20, 130, 220, 0.18);
    }
    [data-testid="stButton"] button[kind="primary"]:hover {
        border-color: #9bd4ff;
        background: #42aaff;
    }
    [data-testid="stAlert"] {
        border: 1px solid var(--studio-border);
        border-radius: 8px;
        background: #121c26;
    }
    [data-testid="stDataFrame"] {
        border: 1px solid var(--studio-border);
        border-radius: 9px;
        overflow: hidden;
    }
    [data-testid="stPlotlyChart"] {
        padding: 0.4rem 0.55rem 0.1rem;
        background: var(--studio-panel);
        border: 1px solid var(--studio-border);
        border-radius: 10px;
    }
    @media (max-width: 760px) {
        .block-container { padding: 1rem 1rem 1.6rem; }
        h1 { font-size: 1.55rem !important; }
        [data-testid="stMetric"] { min-height: 5.5rem; padding: 0.7rem; }
        [data-testid="stMetricValue"] { font-size: 1.05rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Column Analysis Studio")
st.caption("Column buckling analysis using Euler, Rankine and Johnson theories")
st.caption(
    "Educational analysis only—not an engineering-certified design check. "
    "Enter dimensions in mm; calculations use SI units internally."
)

st.divider()
st.subheader("Column Geometry")
section_type = st.selectbox(
    "Cross-section",
    options=("Solid circular", "Rectangular"),
    key="section_type",
)

diameter_mm = None
width_mm = None
height_mm = None
if section_type == "Solid circular":
    geometry_columns = st.columns(2)
    with geometry_columns[0]:
        diameter_mm = optional_number_input("Diameter (mm)", "diameter_mm")
    with geometry_columns[1]:
        column_length_mm = optional_number_input("Column length (mm)", "column_length_mm")
else:
    geometry_columns = st.columns(3)
    with geometry_columns[0]:
        width_mm = optional_number_input("Width (mm)", "width_mm")
    with geometry_columns[1]:
        height_mm = optional_number_input("Height (mm)", "height_mm")
    with geometry_columns[2]:
        column_length_mm = optional_number_input("Column length (mm)", "column_length_mm")

st.divider()
st.subheader("Material Properties")
if st.session_state.get("material_selector") not in MATERIALS_BY_DISPLAY_NAME:
    st.session_state["material_selector"] = DEFAULT_MATERIAL_NAME
    _apply_selected_material()
material_name = st.selectbox(
    "Material",
    options=MATERIAL_OPTIONS,
    key="material_selector",
    on_change=_apply_selected_material,
)
selected_material_grade = MATERIALS_BY_DISPLAY_NAME.get(material_name)

material_columns = st.columns(4)
with material_columns[0]:
    youngs_modulus_gpa = optional_number_input("Young's modulus E (GPa)", "youngs_modulus_gpa")
with material_columns[1]:
    compressive_strength_mpa = optional_number_input(
        "Compressive/crushing strength sigma_c (MPa)",
        "compressive_strength_mpa",
    )
with material_columns[2]:
    rankine_constant_dimensionless = optional_number_input(
        "Rankine constant a (dimensionless)",
        "rankine_constant_dimensionless",
        step=0.001,
    )
with material_columns[3]:
    yield_stress_mpa = optional_number_input(
        "Yield stress sigma_y (MPa)",
        "yield_stress_mpa",
    )

st.caption(
    "Euler, Rankine-Gordon, and Johnson predictions are calculated whenever their required "
    "valid inputs are available. Rankine requires a sourced compressive strength and its "
    "course/reference constant; tensile yield strength is not substituted."
)

missing_required_properties = []
if youngs_modulus_gpa is None:
    missing_required_properties.append("Young's modulus E (Euler)")
if compressive_strength_mpa is None:
    missing_required_properties.append("compressive/crushing strength sigma_c (Rankine-Gordon)")
if rankine_constant_dimensionless is None:
    missing_required_properties.append("Rankine constant a (Rankine-Gordon)")
if yield_stress_mpa is None:
    missing_required_properties.append("yield stress sigma_y (Johnson)")
if missing_required_properties:
    st.info(
        "The following theory predictions need additional inputs: "
        + ", ".join(missing_required_properties)
        + ". Enter a verified value manually; unavailable database values are not inferred."
    )

with st.expander("Material references and property notes"):
    st.caption(selected_material_grade.notes)
    for property_name, property_value in selected_material_grade.properties.items():
        if property_value.source_url is not None:
            property_reference = (
                f"[{property_value.source}]({property_value.source_url})"
            )
        else:
            property_reference = "No verified value"
        st.markdown(
            f"- **{MATERIAL_PROPERTY_LABELS[property_name]} "
            f"({property_value.unit}):** {property_reference}. {property_value.notes}"
        )

property_sources = st.session_state.get("material_property_sources", {})
origin_groups = {"Database": [], "User-entered": []}
for property_name, source in property_sources.items():
    if source in ("database", "user") and st.session_state.get(property_name) is not None:
        origin = "Database" if source == "database" else "User-entered"
        origin_groups[origin].append(MATERIAL_PROPERTY_LABELS[property_name])
origin_summaries = [
    f"{origin}: {', '.join(names)}"
    for origin, names in origin_groups.items()
    if names
]
if origin_summaries:
    st.caption("Value origins — " + " | ".join(origin_summaries))

st.divider()
st.subheader("End Conditions")
end_condition_columns = st.columns(2)
with end_condition_columns[0]:
    end_condition = st.selectbox(
        "Idealized end condition",
        options=list(EndCondition),
        format_func=lambda condition: END_CONDITION_LABELS[condition],
        key="end_condition",
    )
effective_length_factor_value = effective_length_factor(end_condition)
with end_condition_columns[1]:
    st.metric("Effective-length factor K (dimensionless)", f"{effective_length_factor_value:g}")
st.caption("Support conditions are idealizations; real restraint may differ.")

st.divider()
st.subheader("Loading and Safety Factor")
loading_columns = st.columns(3)
with loading_columns[0]:
    applied_load_kn = optional_number_input("Applied axial load (kN)", "applied_load_kn")
with loading_columns[1]:
    factor_of_safety = optional_number_input(
        "Factor of safety (dimensionless)",
        "factor_of_safety",
        step=0.1,
    )
with loading_columns[2]:
    if applied_load_kn is None:
        st.metric("Applied load entered", "No")
    else:
        st.metric("Applied axial load", f"{applied_load_kn:,.6g} kN")

raw_inputs = [
    ("Column length", column_length_mm, "mm"),
    ("Young's modulus E", youngs_modulus_gpa, "GPa"),
    ("Factor of safety", factor_of_safety, "dimensionless"),
    ("Applied axial load", applied_load_kn, "kN"),
]
if diameter_mm is not None:
    raw_inputs.append(("Diameter", diameter_mm, "mm"))
if width_mm is not None:
    raw_inputs.append(("Width", width_mm, "mm"))
if height_mm is not None:
    raw_inputs.append(("Height", height_mm, "mm"))
if compressive_strength_mpa is not None:
    raw_inputs.append(("Compressive strength sigma_c", compressive_strength_mpa, "MPa"))
if rankine_constant_dimensionless is not None:
    raw_inputs.append(("Rankine constant a", rankine_constant_dimensionless, "dimensionless"))
if yield_stress_mpa is not None:
    raw_inputs.append(("Yield stress sigma_y", yield_stress_mpa, "MPa"))

input_errors = []
for input_name, input_value, unit in raw_inputs:
    if input_value is not None:
        try:
            validate_positive_finite(input_name, input_value, unit)
        except ValueError as error:
            input_errors.append(str(error))

engineering_inputs = {}
if column_length_mm is not None:
    engineering_inputs["column_length_m"] = column_length_mm / 1000
if youngs_modulus_gpa is not None:
    engineering_inputs["youngs_modulus_pa"] = youngs_modulus_gpa * 1e9
if compressive_strength_mpa is not None:
    engineering_inputs["compressive_strength_pa"] = compressive_strength_mpa * 1e6
if yield_stress_mpa is not None:
    engineering_inputs["yield_stress_pa"] = yield_stress_mpa * 1e6
if rankine_constant_dimensionless is not None:
    engineering_inputs["rankine_constant_dimensionless"] = rankine_constant_dimensionless
if factor_of_safety is not None:
    engineering_inputs["factor_of_safety"] = factor_of_safety

if not input_errors and engineering_inputs:
    try:
        validate_engineering_inputs(engineering_inputs)
    except ValueError as error:
        input_errors.append(str(error))

geometry_input_errors = [
    error
    for error in input_errors
    if any(error.startswith(name) for name in ("Column length", "Diameter", "Width", "Height"))
]

calculate_clicked = st.button("Calculate", type="primary", key="calculate_column")
if not calculate_clicked:
    st.info("Results clear when an input changes. Select Calculate to update the analysis.")
    st.stop()

if input_errors:
    st.warning("Invalid input values are excluded from the calculations that require them.")
    for input_error in input_errors:
        st.write(f"- {input_error}")

st.divider()
st.subheader("Results")
if geometry_input_errors:
    st.error("Not calculated — invalid geometry input. Correct the errors above before calculating section properties.")
    render_column_classification(None)
else:
    geometry_is_complete = column_length_mm is not None and (
        (section_type == "Solid circular" and diameter_mm is not None)
        or (section_type == "Rectangular" and width_mm is not None and height_mm is not None)
    )

    if not geometry_is_complete:
        st.info("Enter the section dimensions and column length to calculate section and column properties.")
        render_column_classification(None)
    else:
        try:
            column_length_m = column_length_mm / 1000
            if section_type == "Solid circular":
                section_properties = solid_circular_section(diameter_mm / 1000)
            else:
                section_properties = rectangular_section(width_mm / 1000, height_mm / 1000)

            effective_length_m = effective_length(column_length_m, end_condition)
            least_radius_of_gyration_m = radius_of_gyration(section_properties)
            slenderness_ratio_value = slenderness_ratio(
                effective_length_m,
                least_radius_of_gyration_m,
            )

            validate_engineering_inputs(
                {
                    "column_length_m": column_length_m,
                    "area_m2": section_properties.area_m2,
                    "minimum_second_moment_m4": section_properties.minimum_second_moment_m4,
                    "effective_length_m": effective_length_m,
                    "least_radius_of_gyration_m": least_radius_of_gyration_m,
                }
            )
        except (ValueError, OverflowError) as error:
            st.error(f"Could not calculate column properties: {error}")
            render_column_classification(None)
        else:
            st.markdown("### Column Properties")
            property_columns = st.columns(3)
            property_columns[0].metric("Area", format_engineering_value(section_properties.area_m2, "m²"))
            property_columns[1].metric("Second moment I_x", format_engineering_value(section_properties.second_moment_x_m4, "m⁴"))
            property_columns[2].metric("Second moment I_y", format_engineering_value(section_properties.second_moment_y_m4, "m⁴"))

            property_columns = st.columns(3)
            property_columns[0].metric(
                f"Second moment I_min (weaker axis: {section_properties.weaker_axis})",
                format_engineering_value(section_properties.minimum_second_moment_m4, "m⁴"),
            )
            property_columns[1].metric(
                "Least radius of gyration k",
                format_engineering_value(least_radius_of_gyration_m, "m"),
            )
            property_columns[2].metric("Effective length Le", format_engineering_value(effective_length_m, "m"))

            property_columns = st.columns(2)
            property_columns[0].metric("Slenderness ratio Le/k", f"{slenderness_ratio_value:,.6g}")
            if applied_load_kn is None:
                property_columns[1].metric("Applied axial load", "Not entered")
            else:
                property_columns[1].metric("Applied axial load", format_engineering_value(applied_load_kn, "kN"))

            column_classification = render_column_classification(
                slenderness_ratio_value,
                youngs_modulus_pa=(
                    youngs_modulus_gpa * 1e9
                    if youngs_modulus_gpa is not None
                    and not any(
                        error.startswith("Young's modulus E") for error in input_errors
                    )
                    else None
                ),
                yield_stress_pa=(
                    yield_stress_mpa * 1e6
                    if yield_stress_mpa is not None
                    and not any(
                        error.startswith("Yield stress sigma_y")
                        for error in input_errors
                    )
                    else None
                ),
            )

            st.markdown("### Critical Loads")
            euler_load_n = None
            euler_message = "Not calculated — missing required input: Young's modulus E."
            if "Young's modulus E" in " ".join(input_errors):
                euler_message = "Not calculated — invalid input: Young's modulus E must be positive and finite."
            elif youngs_modulus_gpa is not None:
                try:
                    euler_load_n = euler_critical_load(
                        youngs_modulus_gpa * 1e9,
                        section_properties.minimum_second_moment_m4,
                        effective_length_m,
                    )
                    euler_message = ""
                except (ValueError, OverflowError) as error:
                    euler_message = f"Calculation error — {error}"

            rankine_load_n = None
            if compressive_strength_mpa is None or rankine_constant_dimensionless is None:
                rankine_message = "Not calculated — missing required input: compressive strength and the explicit Rankine constant."
            elif any(
                error.startswith(("Compressive strength sigma_c", "Rankine constant a"))
                for error in input_errors
            ):
                rankine_message = "Not calculated — invalid input: compressive strength and Rankine constant must be positive and finite."
            else:
                try:
                    rankine_load_n = rankine_critical_load(
                        compressive_strength_mpa * 1e6,
                        section_properties.area_m2,
                        rankine_constant_dimensionless,
                        effective_length_m,
                        least_radius_of_gyration_m,
                    )
                    rankine_message = ""
                except (ValueError, OverflowError) as error:
                    rankine_message = f"Calculation error — {error}"

            johnson_load_n = None
            if youngs_modulus_gpa is None or yield_stress_mpa is None:
                johnson_message = "Not calculated — missing required input: Young's modulus E and course-defined yield stress."
            elif any(
                error.startswith(("Young's modulus E", "Yield stress sigma_y"))
                for error in input_errors
            ):
                johnson_message = "Not calculated — invalid input: Young's modulus and yield stress must be positive and finite."
            else:
                try:
                    johnson_load_n = johnson_critical_load(
                        yield_stress_mpa * 1e6,
                        youngs_modulus_gpa * 1e9,
                        section_properties.area_m2,
                        effective_length_m,
                        least_radius_of_gyration_m,
                    )
                    johnson_message = ""
                except JohnsonOutOfRangeError as error:
                    johnson_message = f"Out of range — {error}"
                except (ValueError, OverflowError) as error:
                    johnson_message = f"Calculation error — {error}"

            applicability_criteria = load_applicability_criteria()
            recommendation = recommend_theory(
                slenderness_ratio_value,
                youngs_modulus_gpa=(
                    youngs_modulus_gpa
                    if not any(error.startswith("Young's modulus E") for error in input_errors)
                    else None
                ),
                compressive_strength_mpa=(
                    compressive_strength_mpa
                    if not any(
                        error.startswith("Compressive strength sigma_c")
                        for error in input_errors
                    )
                    else None
                ),
                rankine_constant_dimensionless=(
                    rankine_constant_dimensionless
                    if not any(error.startswith("Rankine constant a") for error in input_errors)
                    else None
                ),
                yield_stress_mpa=(
                    yield_stress_mpa
                    if not any(error.startswith("Yield stress sigma_y") for error in input_errors)
                    else None
                ),
                applied_load_kn=(
                    applied_load_kn
                    if not any(error.startswith("Applied axial load") for error in input_errors)
                    else None
                ),
                critical_loads_n={
                    TheoryName.EULER: euler_load_n,
                    TheoryName.RANKINE: rankine_load_n,
                    TheoryName.JOHNSON: johnson_load_n,
                },
                criteria=(
                    replace(
                        applicability_criteria,
                        johnson_minimum_slenderness_ratio=(
                            column_classification.short_max_slenderness_ratio
                        ),
                        johnson_range_reference=(
                            "Johnson intermediate range begins at the material-specific "
                            "Euler-stress/yield boundary in classification_criteria.json"
                        ),
                        johnson_range_reference_url=(
                            column_classification.reference_url
                        ),
                    )
                    if column_classification is not None
                    and column_classification.classification is not None
                    and column_classification.short_max_slenderness_ratio is not None
                    else applicability_criteria
                ),
            )
            reviews_by_name = {
                review.theory.value: review for review in recommendation.theory_reviews
            }
            assessments = {
                theory_name: reviews_by_name[theory_name]
                for theory_name in ("Euler", "Rankine", "Johnson")
            }
            theory_results = [
                ("Euler", euler_load_n, euler_message),
                ("Rankine", rankine_load_n, rankine_message),
                ("Johnson", johnson_load_n, johnson_message),
            ]
            result_columns = st.columns(3)
            for result_column, (theory_name, critical_load_n, result_message) in zip(
                result_columns,
                theory_results,
            ):
                if critical_load_n is None:
                    result_column.metric(f"{theory_name} critical load", "Not calculated")
                else:
                    result_column.metric(
                        f"{theory_name} critical load",
                        format_critical_load(critical_load_n),
                    )
                result_column.caption(f"Applicability: {assessments[theory_name].status.value}")
                if result_message:
                    result_column.info(result_message)

            st.subheader("Recommended Theory")
            if recommendation.recommended_theory is None:
                unresolved_inputs = tuple(
                    dict.fromkeys(
                        missing_input
                        for review in recommendation.theory_reviews
                        for missing_input in review.missing_inputs
                    )
                )
                st.info(
                    "Insufficient information to recommend. "
                    + recommendation.explanation
                    + (
                        " Required inputs or criteria: "
                        + ", ".join(unresolved_inputs)
                        + "."
                        if unresolved_inputs
                        else ""
                    )
                )
            else:
                st.success(
                    f"Recommended theory: {recommendation.recommended_theory.value}. "
                    + recommendation.explanation
                )

            johnson_review = assessments["Johnson"]
            johnson_lower_boundary = (
                applicability_criteria.johnson_minimum_slenderness_ratio
            )
            if (
                johnson_lower_boundary is not None
                and slenderness_ratio_value < johnson_lower_boundary
            ):
                st.warning(
                    "Short-column/crushing-dominated region: slenderness is below the "
                    "configured Johnson lower boundary. A separate verified "
                    "compressive-strength check is shown below when its input is available."
                )
            elif (
                johnson_review.status is ApplicabilityStatus.APPLICABLE
                and johnson_lower_boundary == 0
            ):
                st.warning(
                    "Very low slenderness can be crushing-dominated. The configured "
                    "Johnson lower bound of zero is only the mathematical limit of the "
                    "classical formula, not a validated short-column cutoff; no numerical "
                    "crushing crossover is specified. Review the separate crushing-strength "
                    "check below."
                )

            if recommendation.candidate_theories:
                for candidate in recommendation.candidate_theories:
                    candidate_load_n = recommendation.critical_loads_n.get(candidate)
                    if candidate_load_n is None:
                        st.write(
                            f"{candidate.value} critical load: not calculated from the "
                            "available valid inputs."
                        )
                    elif recommendation.applied_load_kn is None:
                        st.write(
                            f"{candidate.value} critical load: "
                            f"{format_critical_load(candidate_load_n)}. Applied load was "
                            "not provided, so no load comparison is available."
                        )
                    else:
                        critical_load_kn = candidate_load_n / 1000
                        load_ratio = recommendation.applied_load_kn / critical_load_kn
                        st.write(
                            f"{candidate.value} critical load: "
                            f"{format_critical_load(candidate_load_n)}; applied load: "
                            f"{recommendation.applied_load_kn:g} kN "
                            f"(applied/critical = {load_ratio:.4g}). This comparison alone "
                            "does not establish safety or design adequacy."
                        )
            else:
                st.caption(
                    "Formula loads are not treated as valid capacities because no theory "
                    "meets all configured criteria. No applied-load adequacy conclusion is made."
                )

            st.markdown("**Slenderness and material properties considered**")
            recommendation_property_columns = st.columns(3)
            recommendation_property_columns[0].metric(
                "Recommendation slenderness ratio Le/k",
                format_engineering_value(recommendation.slenderness_ratio, "dimensionless"),
            )
            recommendation_property_columns[1].metric(
                "Young's modulus E for recommendation",
                (
                    format_engineering_value(recommendation.material_properties["youngs_modulus_gpa"], "GPa")
                    if recommendation.material_properties["youngs_modulus_gpa"] is not None
                    else "Not provided or valid"
                ),
            )
            recommendation_property_columns[2].metric(
                "Yield stress sigma_y for recommendation",
                (
                    format_engineering_value(recommendation.material_properties["yield_stress_mpa"], "MPa")
                    if recommendation.material_properties["yield_stress_mpa"] is not None
                    else "Not provided or valid"
                ),
            )
            recommendation_property_columns = st.columns(2)
            recommendation_property_columns[0].metric(
                "Compressive strength sigma_c for recommendation",
                (
                    format_engineering_value(recommendation.material_properties["compressive_strength_mpa"], "MPa")
                    if recommendation.material_properties["compressive_strength_mpa"] is not None
                    else "Not provided or valid"
                ),
            )
            recommendation_property_columns[1].metric(
                "Rankine constant a for recommendation",
                (
                    format_engineering_value(
                        recommendation.material_properties["rankine_constant_dimensionless"],
                        "dimensionless",
                    )
                    if recommendation.material_properties["rankine_constant_dimensionless"] is not None
                    else "Not provided or valid"
                ),
            )

            review_columns = st.columns(3)
            for review_column, review in zip(review_columns, recommendation.theory_reviews):
                review_column.markdown(f"**{review.theory.value}**")
                review_column.caption(f"Applicability: {review.status.value}")
                review_column.write(review.explanation)
                if review.missing_inputs:
                    review_column.write(
                        "Required inputs: " + ", ".join(review.missing_inputs)
                    )
                if review.reference_url:
                    review_column.markdown(
                        f"[Supporting reference: {review.supporting_reference}]"
                        f"({review.reference_url})"
                    )
                else:
                    review_column.caption(
                        f"Supporting reference: {review.supporting_reference}"
                    )

            valid_applied_load_kn = recommendation.applied_load_kn
            valid_factor_of_safety = (
                factor_of_safety
                if not any(error.startswith("Factor of safety") for error in input_errors)
                else None
            )
            load_assessment_rows = []
            load_assessment_by_theory = {}
            critical_load_warnings = []
            allowable_load_warnings = []
            for theory_name, critical_load_n, _ in theory_results:
                review = assessments[theory_name]
                applicable = review.status is ApplicabilityStatus.APPLICABLE
                critical_load_kn = (
                    critical_load_n / 1000 if critical_load_n is not None else None
                )
                if not applicable:
                    critical_assessment = "Not assessed — applicability not confirmed"
                    critical_ratio_display = "Not assessed"
                elif critical_load_kn is None:
                    critical_assessment = "Not assessed — critical load not calculated"
                    critical_ratio_display = "Not assessed"
                elif valid_applied_load_kn is None:
                    critical_assessment = "Not assessed — applied load not provided or valid"
                    critical_ratio_display = "Not assessed"
                else:
                    critical_ratio = valid_applied_load_kn / critical_load_kn
                    critical_ratio_display = format_engineering_value(
                        critical_ratio,
                        "dimensionless",
                    )
                    if critical_ratio > 1:
                        critical_assessment = "Applied load exceeds predicted critical load"
                        critical_load_warnings.append(
                            f"{theory_name}: {valid_applied_load_kn:g} kN applied "
                            f"> {critical_load_kn:g} kN critical "
                            f"(applied/critical = {critical_ratio:.4g})."
                        )
                    elif critical_ratio < 1:
                        critical_assessment = "Applied load is below predicted critical load"
                    else:
                        critical_assessment = "Applied load equals predicted critical load"

                if not applicable:
                    allowable_load_display = "Not calculated — applicability not confirmed"
                    allowable_assessment = "Not assessed"
                elif critical_load_kn is None:
                    allowable_load_display = "Not calculated — critical load unavailable"
                    allowable_assessment = "Not assessed"
                elif valid_factor_of_safety is None:
                    allowable_load_display = "Not calculated — valid factor of safety not entered"
                    allowable_assessment = "Not assessed"
                else:
                    allowable_load_kn = critical_load_kn / valid_factor_of_safety
                    allowable_load_display = format_engineering_value(
                        allowable_load_kn,
                        "kN",
                    )
                    if valid_applied_load_kn is None:
                        allowable_assessment = (
                            "Not assessed — applied load not provided or valid"
                        )
                    elif valid_applied_load_kn > allowable_load_kn:
                        allowable_assessment = "Applied load exceeds theoretical allowable load"
                        allowable_load_warnings.append(
                            f"{theory_name}: applied load {valid_applied_load_kn:g} kN "
                            f"> theoretical allowable load {allowable_load_kn:g} kN."
                        )
                    elif valid_applied_load_kn < allowable_load_kn:
                        allowable_assessment = "Applied load is below theoretical allowable load"
                    else:
                        allowable_assessment = "Applied load equals theoretical allowable load"

                load_assessment_by_theory[theory_name] = critical_assessment
                load_assessment_rows.append(
                    {
                        "Theory": theory_name,
                        "Applicability": review.status.value,
                        "Critical load (kN)": format_engineering_value(
                            critical_load_kn,
                            "kN",
                        )
                        if critical_load_kn is not None
                        else "Not calculated",
                        "Applied / critical ratio": critical_ratio_display,
                        "Critical-load assessment": critical_assessment,
                        "Theoretical allowable load (kN)": allowable_load_display,
                        "Allowable-load assessment": allowable_assessment,
                    }
                )

            recommended_theory = recommendation.recommended_theory
            recommended_load_n = (
                recommendation.critical_loads_n.get(recommended_theory)
                if recommended_theory is not None
                else None
            )
            recommended_review = (
                assessments[recommended_theory.value]
                if recommended_theory is not None
                else None
            )
            recommended_allowable_kn = (
                recommended_load_n / 1000 / valid_factor_of_safety
                if recommended_review is not None
                and recommended_review.status is ApplicabilityStatus.APPLICABLE
                and recommended_load_n is not None
                and valid_factor_of_safety is not None
                else None
            )
            st.subheader("Results Summary")
            summary_columns = st.columns(5)
            summary_columns[0].metric(
                "Recommended theory",
                recommended_theory.value if recommended_theory is not None else "None verified",
            )
            summary_columns[1].metric(
                "Recommended critical load",
                format_critical_load(recommended_load_n),
            )
            summary_columns[2].metric(
                "Theoretical allowable load",
                format_engineering_value(recommended_allowable_kn, "kN")
                if recommended_allowable_kn is not None
                else "Not justified",
            )
            summary_columns[3].metric(
                "Applied axial load",
                format_engineering_value(valid_applied_load_kn, "kN")
                if valid_applied_load_kn is not None
                else "Not entered or valid",
            )
            summary_columns[4].metric(
                "Load assessment",
                load_assessment_by_theory.get(
                    recommended_theory.value,
                    "No verified recommendation",
                )
                if recommended_theory is not None
                else "No verified recommendation",
            )
            st.caption(
                "Theoretical comparisons only—not a certified design check. Results assume "
                "the selected idealized end restraints and configured applicability criteria; "
                "they do not account for all real-member imperfections or design requirements."
            )

            if recommended_review is not None:
                st.write(
                    f"**Why {recommended_theory.value} is recommended:** "
                    f"{recommended_review.explanation}"
                )
                excluded_theories = [
                    f"{review.theory.value} ({review.status.value}): {review.explanation}"
                    for review in recommendation.theory_reviews
                    if review.theory is not recommended_theory
                ]
                if excluded_theories:
                    st.write("**Other theories:** " + " ".join(excluded_theories))

            st.subheader("Theory Comparison")
            st.caption(
                "Calculated values are mathematical predictions only. Applicability is "
                "determined by the configured course-specific criteria."
            )
            comparison_rows = []
            for theory_name, critical_load_n, result_message in theory_results:
                if critical_load_n is None:
                    if result_message.startswith("Out of range"):
                        calculation_status = (
                            "Non-physical prediction — " + result_message.removeprefix("Out of range — ")
                        )
                    elif result_message.startswith("Calculation error"):
                        calculation_status = result_message
                    elif result_message.startswith("Not calculated"):
                        calculation_status = result_message
                    else:
                        calculation_status = f"Not calculated — {result_message}"
                    load_display = "Not calculated"
                else:
                    applicability = assessments[theory_name].status
                    if applicability is ApplicabilityStatus.APPLICABLE:
                        calculation_status = (
                            "Calculated; within the configured applicability criterion"
                        )
                    elif applicability is ApplicabilityStatus.OUT_OF_RANGE:
                        calculation_status = (
                            "Formula calculated; outside the configured applicability range"
                        )
                    else:
                        calculation_status = (
                            "Formula calculated; applicability not confirmed"
                        )
                    load_display = format_engineering_value(critical_load_n / 1000, "kN")

                comparison_rows.append(
                    {
                        "Theory": theory_name,
                        "Critical load (kN)": load_display,
                        "Calculation status": calculation_status,
                        "Applicability status": assessments[theory_name].status.value,
                        "Applicability reason": assessments[theory_name].explanation,
                    }
                )
            st.dataframe(comparison_rows, hide_index=True, width="stretch")

            st.subheader("Short-Column Crushing Check")
            valid_compressive_strength_mpa = (
                compressive_strength_mpa
                if not any(
                    error.startswith("Compressive strength sigma_c")
                    for error in input_errors
                )
                else None
            )
            if valid_compressive_strength_mpa is None:
                st.info(
                    "Not calculated — enter a verified compressive/crushing strength to "
                    "compare against the theoretical squash load. Tensile yield strength "
                    "is not substituted."
                )
            else:
                crushing_load_n = (
                    valid_compressive_strength_mpa
                    * 1e6
                    * section_properties.area_m2
                )
                if not isfinite(crushing_load_n) or crushing_load_n <= 0:
                    st.error(
                        "Could not calculate the squash load: the supplied compressive "
                        "strength and section area produced a non-physical result."
                    )
                else:
                    crushing_load_kn = crushing_load_n / 1000
                    st.metric(
                        "Theoretical squash load (compressive strength × area)",
                        format_engineering_value(crushing_load_kn, "kN"),
                    )
                    if recommendation.applied_load_kn is None:
                        st.caption(
                            "Applied load was not provided or valid, so no crushing-load "
                            "comparison is available."
                        )
                    elif recommendation.applied_load_kn > crushing_load_kn:
                        st.error(
                            f"Applied load ({recommendation.applied_load_kn:g} kN) exceeds "
                            f"the theoretical squash load ({crushing_load_kn:g} kN). "
                            "This educational comparison is not a certified design check."
                        )
                    elif recommendation.applied_load_kn < crushing_load_kn:
                        st.caption(
                            f"Applied load ({recommendation.applied_load_kn:g} kN) is below "
                            f"the theoretical squash load ({crushing_load_kn:g} kN). This "
                            "comparison does not establish safety."
                        )
                    else:
                        st.warning(
                            "Applied load equals the theoretical squash load. This "
                            "educational comparison is not a certified design check."
                        )
            st.caption(
                "The squash load is the material compressive/crushing strength multiplied "
                "by area. It is separate from Rankine-Gordon and does not include buckling "
                "or other design limit states."
            )

            st.subheader("Applied Load Assessment")
            safety_factor_display = (
                format_engineering_value(valid_factor_of_safety, "dimensionless")
                if valid_factor_of_safety is not None
                else (
                    format_engineering_value(factor_of_safety, "dimensionless")
                    + " (invalid)"
                )
                if factor_of_safety is not None
                else "Not entered"
            )
            st.metric("Entered factor of safety", safety_factor_display)
            st.caption(
                "Critical-load ratios and theoretical allowable loads are shown only for "
                "theories marked applicable by the configured criteria. The allowable load "
                "is that theory's critical load divided by the entered factor of safety."
            )
            st.dataframe(load_assessment_rows, hide_index=True, width="stretch")
            for warning in critical_load_warnings:
                st.error(f"Applied load exceeds predicted critical load. {warning}")
            for warning in allowable_load_warnings:
                st.warning(
                    f"Applied load exceeds theoretical allowable load. {warning} "
                    "This is not a certified design check."
                )

            st.caption(
                "The horizontal axis includes this column's local slenderness range and the "
                "Euler–Johnson transition when available. Johnson is clipped at Cc and at any "
                "configured lower applicability boundary."
            )
            graph_point_count = 121
            transition_ratio = recommendation.euler_johnson_transition_ratio
            graph_minimum_slenderness = (
                min(slenderness_ratio_value * 0.5, transition_ratio * 0.5)
                if transition_ratio is not None
                else slenderness_ratio_value * 0.5
            )
            graph_maximum_slenderness = (
                max(slenderness_ratio_value * 1.5, transition_ratio * 1.5)
                if transition_ratio is not None
                else slenderness_ratio_value * 1.5
            )
            graph_slenderness_span = (
                graph_maximum_slenderness - graph_minimum_slenderness
            )
            graph_slenderness_ratios = {
                graph_minimum_slenderness
                + graph_slenderness_span * point_index / (graph_point_count - 1)
                for point_index in range(graph_point_count)
            }
            if transition_ratio is not None:
                graph_slenderness_ratios.add(transition_ratio)
            if (
                applicability_criteria.johnson_minimum_slenderness_ratio is not None
                and applicability_criteria.johnson_minimum_slenderness_ratio > 0
            ):
                graph_slenderness_ratios.add(
                    applicability_criteria.johnson_minimum_slenderness_ratio
                )
            graph_slenderness_ratios = sorted(graph_slenderness_ratios)

            try:
                graph_curves = build_slenderness_curve_data(
                    graph_slenderness_ratios,
                    section_properties,
                    youngs_modulus_pa=(
                        youngs_modulus_gpa * 1e9
                        if youngs_modulus_gpa is not None
                        else None
                    ),
                    compressive_strength_pa=(
                        compressive_strength_mpa * 1e6
                        if compressive_strength_mpa is not None
                        else None
                    ),
                    rankine_constant_dimensionless=(
                        rankine_constant_dimensionless
                    ),
                    yield_stress_pa=(
                        yield_stress_mpa * 1e6
                        if yield_stress_mpa is not None
                        else None
                    ),
                )
            except (ValueError, OverflowError) as error:
                st.warning(f"Could not build graph data: {error}")
            else:
                graph_labels = {
                    "Euler": "Euler",
                    "Rankine-Gordon": "Rankine-Gordon",
                    "Johnson": "Johnson",
                }
                graph_colors = {
                    "Euler": "#35a5ff",
                    "Rankine-Gordon": "#43d9ad",
                    "Johnson": "#f4b942",
                }
                graph_line_styles = {
                    "Euler": "solid",
                    "Rankine-Gordon": "dash",
                    "Johnson": "dot",
                }
                if any(
                    load_n is not None
                    for critical_loads_n in graph_curves.values()
                    for load_n in critical_loads_n
                ):
                    graph_titles = {
                        "Euler": "Euler Theory — Critical Load vs. Slenderness",
                        "Rankine-Gordon": "Rankine–Gordon Theory — Critical Load vs. Slenderness",
                        "Johnson": "Johnson Theory — Critical Load vs. Slenderness",
                    }
                    graph_result_messages = {
                        "Euler": euler_message,
                        "Rankine-Gordon": rankine_message,
                        "Johnson": johnson_message,
                    }
                    graph_theory_names = {
                        "Euler": TheoryName.EULER,
                        "Rankine-Gordon": TheoryName.RANKINE,
                        "Johnson": TheoryName.JOHNSON,
                    }
                    for theory_name in ("Euler", "Rankine-Gordon", "Johnson"):
                        critical_loads_n = graph_curves[theory_name]
                        if theory_name == "Johnson":
                            johnson_minimum = (
                                applicability_criteria.johnson_minimum_slenderness_ratio
                            )
                            available_points = [
                                (slenderness_ratio_value_i, load_n / 1000)
                                for slenderness_ratio_value_i, load_n in zip(
                                    graph_slenderness_ratios,
                                    critical_loads_n,
                                )
                                if load_n is not None
                                and transition_ratio is not None
                                and slenderness_ratio_value_i <= transition_ratio
                                and (
                                    johnson_minimum is None
                                    or slenderness_ratio_value_i >= johnson_minimum
                                )
                            ]
                        else:
                            available_points = [
                                (slenderness_ratio_value_i, load_n / 1000)
                                for slenderness_ratio_value_i, load_n in zip(
                                    graph_slenderness_ratios,
                                    critical_loads_n,
                                )
                                if load_n is not None
                            ]
                        if not available_points:
                            st.markdown(f"#### {graph_titles[theory_name]}")
                            st.info(
                                (
                                    "Johnson transition Cc is unavailable. Enter valid Young's "
                                    "modulus and yield strength to define its upper range."
                                    if theory_name == "Johnson"
                                    and transition_ratio is None
                                    else graph_result_messages[theory_name]
                                    or "No calculated values fall within this theory's configured graph range."
                                )
                            )
                            continue

                        graph_figure = go.Figure(
                            go.Scatter(
                                x=[point[0] for point in available_points],
                                y=[point[1] for point in available_points],
                                mode="lines",
                                name=(
                                    "Johnson"
                                    if theory_name == "Johnson"
                                    else graph_labels[theory_name]
                                ),
                                line={
                                    "color": graph_colors[theory_name],
                                    "width": 2.7,
                                    "dash": graph_line_styles[theory_name],
                                },
                                hovertemplate=(
                                    "Slenderness ratio: %{x:.4g}<br>"
                                    "Critical load: %{y:.4g} kN<extra>%{fullData.name}</extra>"
                                ),
                            )
                        )
                        current_theory = graph_theory_names[theory_name]
                        current_critical_load_n = recommendation.critical_loads_n.get(
                            current_theory
                        )
                        current_review = reviews_by_name[current_theory.value]
                        current_point_in_johnson_range = (
                            theory_name != "Johnson"
                            or transition_ratio is not None
                            and slenderness_ratio_value <= transition_ratio
                            and (
                                applicability_criteria.johnson_minimum_slenderness_ratio
                                is None
                                or slenderness_ratio_value
                                >= applicability_criteria.johnson_minimum_slenderness_ratio
                            )
                        )
                        if (
                            current_critical_load_n is not None
                            and current_point_in_johnson_range
                        ):
                            current_point_name = (
                                "Current column — applicable point"
                                if current_review.status is ApplicabilityStatus.APPLICABLE
                                else "Current column — formula prediction"
                            )
                            graph_figure.add_trace(
                                go.Scatter(
                                    x=[slenderness_ratio_value],
                                    y=[current_critical_load_n / 1000],
                                    mode="markers",
                                    name=current_point_name,
                                    marker={
                                        "color": graph_colors[theory_name],
                                        "size": 10,
                                        "symbol": "circle",
                                        "line": {"color": "#f3f7fb", "width": 1.5},
                                    },
                                    hovertemplate=(
                                        "Current column: λ = %{x:.4g}<br>"
                                        "Formula prediction: %{y:.4g} kN<br>"
                                        f"Applicability: {current_review.status.value}"
                                        "<extra></extra>"
                                    ),
                                )
                            )
                        graph_figure.add_vline(
                            x=slenderness_ratio_value,
                            line_dash="dash",
                            line_color="#c7d2df",
                            line_width=1.5,
                        )
                        if (
                            transition_ratio is not None
                            and theory_name in ("Euler", "Johnson")
                        ):
                            graph_figure.add_vline(
                                x=transition_ratio,
                                line_dash="dot",
                                line_color="#f4b942",
                                line_width=2,
                            )
                            graph_figure.add_annotation(
                                x=transition_ratio,
                                y=0.99,
                                xref="x",
                                yref="paper",
                                text=f"Euler–Johnson transition Cc = {transition_ratio:,.3f}",
                                showarrow=False,
                                xanchor="right",
                                yanchor="top",
                                xshift=-5,
                                yshift=-8,
                                bgcolor="#15212d",
                                bordercolor="#f4b942",
                                borderwidth=1,
                                font={"color": "#f4b942", "size": 11},
                            )
                        graph_figure.add_annotation(
                            x=slenderness_ratio_value,
                            y=0.91,
                            xref="x",
                            yref="paper",
                            text=f"Current column: λ = {slenderness_ratio_value:,.6g}",
                            showarrow=False,
                            xanchor="left",
                            yanchor="top",
                            xshift=8,
                            yshift=-8,
                            bgcolor="#15212d",
                            bordercolor="#35a5ff",
                            borderwidth=1,
                            font={"color": "#e8eef5", "size": 12},
                        )
                        graph_figure.update_layout(
                            title={
                                "text": graph_titles[theory_name],
                                "x": 0.02,
                                "xanchor": "left",
                                "font": {"size": 17},
                            },
                            template="plotly_dark",
                            paper_bgcolor="#111a24",
                            plot_bgcolor="#111a24",
                            font={"family": "Segoe UI, sans-serif", "color": "#dce7f1", "size": 12},
                            hovermode="x unified",
                            legend={
                                "title": {"text": "Theory status"},
                                "orientation": "h",
                                "y": 0.02,
                                "x": 0.02,
                                "xanchor": "left",
                                "yanchor": "bottom",
                                "font": {"size": 10},
                                "bgcolor": "rgba(11, 16, 22, 0.82)",
                                "bordercolor": "#263544",
                                "borderwidth": 1,
                                "itemclick": False,
                                "itemdoubleclick": False,
                            },
                            margin={"l": 82, "r": 28, "t": 76, "b": 88},
                            height=430,
                        )
                        graph_figure.update_xaxes(
                            title_text="Slenderness Ratio (Le/k)",
                            range=[graph_minimum_slenderness, graph_maximum_slenderness],
                            gridcolor="#263544",
                            zerolinecolor="#34485b",
                            tickfont={"size": 11},
                            title_font={"color": "#c5d3e0", "size": 13},
                            automargin=True,
                        )
                        graph_figure.update_yaxes(
                            title_text="Critical Load (kN)",
                            gridcolor="#263544",
                            zerolinecolor="#34485b",
                            tickfont={"size": 11},
                            title_font={"color": "#c5d3e0", "size": 13},
                            automargin=True,
                        )
                        st.plotly_chart(
                            graph_figure,
                            use_container_width=True,
                            height=430,
                            config={"displaylogo": False, "responsive": True},
                        )
                        st.caption(
                            f"{theory_name} applicability at the current slenderness: "
                            f"{current_review.status.value}. {current_review.explanation}"
                        )
                        if (
                            theory_name == "Johnson"
                            and applicability_criteria.johnson_minimum_slenderness_ratio
                            is None
                        ):
                            st.caption(
                                "The Johnson curve is clipped at Cc. Its lower slenderness "
                                "boundary is not configured, so applicability in the short-column "
                                "region remains unverified."
                            )
                    current_load_comparison = []
                    for theory_name in ("Euler", "Rankine-Gordon", "Johnson"):
                        current_review = reviews_by_name[
                            graph_theory_names[theory_name].value
                        ]
                        current_load_n = recommendation.critical_loads_n.get(
                            graph_theory_names[theory_name]
                        )
                        if (
                            current_review.status is not ApplicabilityStatus.APPLICABLE
                            or current_load_n is None
                        ):
                            continue
                        current_load_comparison.append(
                            {
                                "Theory": theory_name,
                                "Current load at λ": format_engineering_value(current_load_n / 1000, "kN"),
                            }
                        )
                    if current_load_comparison:
                        comparison_columns = st.columns(len(current_load_comparison))
                        for comparison_column, comparison_item in zip(comparison_columns, current_load_comparison):
                            comparison_column.metric(
                                f"{comparison_item['Theory']} at λ = {slenderness_ratio_value:,.4g}",
                                comparison_item["Current load at λ"],
                            )

                    st.caption(
                        "The dashed line marks the current column's slenderness ratio. "
                        "It is a reference marker, not a theory-applicability boundary."
                    )
                    st.caption(
                        "The vertical Cc reference marks the Euler–Johnson transition. The "
                        "Johnson curve does not extend into the Euler region; any unconfigured "
                        "lower applicability boundary remains explicitly unverified."
                    )
                else:
                    graph_titles = {
                        "Euler": "Euler Theory — Critical Load vs. Slenderness",
                        "Rankine-Gordon": "Rankine–Gordon Theory — Critical Load vs. Slenderness",
                        "Johnson": "Johnson Theory — Critical Load vs. Slenderness",
                    }
                    graph_result_messages = {
                        "Euler": euler_message,
                        "Rankine-Gordon": rankine_message,
                        "Johnson": johnson_message,
                    }
                    for theory_name in ("Euler", "Rankine-Gordon", "Johnson"):
                        st.markdown(f"#### {graph_titles[theory_name]}")
                        st.info(
                            graph_result_messages[theory_name]
                            or "No positive curve values are available in this plotted range."
                        )

            with st.expander("Formulas, assumptions, and applicability", expanded=False):
                st.markdown("**Euler**")
                st.latex(r"P_E = \frac{\pi^2 E I_{min}}{L_e^2}")
                st.write(assessments["Euler"].explanation)
                st.markdown("**Rankine-Gordon**")
                st.latex(r"P_R = \frac{\sigma_c A}{1 + a (L_e/k)^2}")
                st.write(assessments["Rankine"].explanation)
                st.markdown("**Johnson parabolic**")
                st.latex(r"P_J = A\sigma_y\left(1 - \frac{\sigma_y}{4\pi^2 E}(L_e/k)^2\right)")
                st.write(assessments["Johnson"].explanation)

            if factor_of_safety is None:
                st.info(
                    "No factor of safety was entered. Theoretical allowable loads are therefore "
                    "not calculated; critical-load comparisons are not a safety determination."
                )
            else:
                st.info(
                    "Allowable loads above are theoretical critical-load/FoS comparisons for "
                    "applicable theories only. They are not certified design checks and do not "
                    "establish design safety or adequacy."
                )