from math import isfinite

import streamlit as st
import plotly.graph_objects as go

from column_analysis.graph_data import build_slenderness_curve_data
from column_analysis.properties import (
    EndCondition,
    effective_length,
    effective_length_factor,
    radius_of_gyration,
    slenderness_ratio,
)
from column_analysis.sections import rectangular_section, solid_circular_section
from column_analysis.theories import (
    euler_critical_load,
    johnson_critical_load,
    rankine_critical_load,
)
from column_analysis.validation import (
    assess_theory_applicability,
    validate_engineering_inputs,
    validate_positive_finite,
)


END_CONDITION_LABELS = {
    EndCondition.PINNED_PINNED: "Pinned-pinned",
    EndCondition.FIXED_FIXED: "Fixed-fixed",
    EndCondition.FIXED_FREE: "Fixed-free (cantilever)",
    EndCondition.FIXED_PINNED: "Fixed-pinned",
}


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


st.set_page_config(
    page_title="Column Analysis Studio",
    layout="wide",
)
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1.5rem; }
    h1 { font-size: 1.9rem !important; margin-bottom: 0.15rem !important; }
    h2, h3 { margin-top: 0.75rem !important; margin-bottom: 0.35rem !important; }
    div[data-testid="stVerticalBlock"] { gap: 0.7rem; }
    hr { margin: 0.45rem 0 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Column Analysis Studio")
st.caption("Column buckling analysis using Euler, Rankine and Johnson theories")
st.caption(
    "Enter dimensions in mm and material properties in the displayed units. "
    "Calculations use SI internally; no material values or empirical constants are prefilled."
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
material_columns = st.columns(2)
with material_columns[0]:
    youngs_modulus_gpa = optional_number_input("Young's modulus E (GPa)", "youngs_modulus_gpa")
with material_columns[1]:
    st.caption("Select optional theories to enter their required material data.")
    optional_theory_columns = st.columns(2)
    with optional_theory_columns[0]:
        include_rankine = st.checkbox("Calculate Rankine-Gordon", key="include_rankine")
    with optional_theory_columns[1]:
        include_johnson = st.checkbox("Calculate Johnson", key="include_johnson")

compressive_strength_mpa = None
rankine_constant_dimensionless = None
yield_stress_mpa = None
if include_rankine:
    rankine_columns = st.columns(2)
    with rankine_columns[0]:
        compressive_strength_mpa = optional_number_input(
            "Compressive/crushing strength sigma_c (MPa)",
            "compressive_strength_mpa",
        )
    with rankine_columns[1]:
        rankine_constant_dimensionless = optional_number_input(
            "Rankine constant a (dimensionless, from course/reference)",
            "rankine_constant_dimensionless",
            step=0.001,
        )
    st.caption(
        "For the supplied Rankine form, a is dimensionless. Enter the value and convention "
        "specified by your course/reference; no default is assumed."
    )

if include_johnson:
    yield_stress_mpa = optional_number_input(
        "Yield stress sigma_y (MPa, as defined by the course)",
        "yield_stress_mpa",
    )

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
else:
    geometry_is_complete = column_length_mm is not None and (
        (section_type == "Solid circular" and diameter_mm is not None)
        or (section_type == "Rectangular" and width_mm is not None and height_mm is not None)
    )

    if not geometry_is_complete:
        st.info("Enter the section dimensions and column length to calculate section and column properties.")
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
                    euler_message = f"Not calculated — invalid input: {error}"

            rankine_load_n = None
            if not include_rankine:
                rankine_message = "Not selected."
            elif compressive_strength_mpa is None or rankine_constant_dimensionless is None:
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
                    rankine_message = f"Not calculated — invalid input: {error}"

            johnson_load_n = None
            if not include_johnson:
                johnson_message = "Not selected."
            elif youngs_modulus_gpa is None or yield_stress_mpa is None:
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
                except (ValueError, OverflowError) as error:
                    johnson_message = f"Not calculated — invalid input: {error}"

            rankine_assessment_constant = rankine_constant_dimensionless
            if any(error.startswith("Rankine constant a") for error in input_errors):
                rankine_assessment_constant = None
            assessments = {
                "Euler": assess_theory_applicability("Euler"),
                "Rankine": assess_theory_applicability(
                    "Rankine",
                    rankine_constant_dimensionless=rankine_assessment_constant,
                ),
                "Johnson": assess_theory_applicability("Johnson"),
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

            st.subheader("Theory Comparison")
            st.caption(
                "Calculated values are mathematical predictions only. None is verified as "
                "applicable until course-specific criteria are configured."
            )
            comparison_rows = []
            for theory_name, critical_load_n, result_message in theory_results:
                if critical_load_n is None:
                    if result_message.startswith("Not calculated"):
                        calculation_status = result_message
                    elif result_message == "Not selected.":
                        calculation_status = "Not selected"
                    else:
                        calculation_status = f"Not calculated — {result_message}"
                    load_display = "Not calculated"
                else:
                    calculation_status = "Calculated mathematically; applicability unverified"
                    load_display = format_engineering_value(critical_load_n / 1000, "kN")

                comparison_rows.append(
                    {
                        "Theory": theory_name,
                        "Critical load (kN)": load_display,
                        "Calculation status": calculation_status,
                        "Applicability status": assessments[theory_name].status.value,
                    }
                )
            st.dataframe(comparison_rows, hide_index=True, width="stretch")

            st.subheader("Critical Load vs. Slenderness")
            st.caption(
                "Curves span 0.5 to 1.5 times this column's slenderness for local comparison; "
                "this display range is not a short/intermediate/long classification. Hover over "
                "a curve to inspect its theoretical or provisional load."
            )
            graph_point_count = 121
            graph_minimum_slenderness = slenderness_ratio_value * 0.5
            graph_slenderness_span = slenderness_ratio_value
            graph_slenderness_ratios = [
                graph_minimum_slenderness
                + graph_slenderness_span * point_index / (graph_point_count - 1)
                for point_index in range(graph_point_count)
            ]

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
                        if include_rankine and compressive_strength_mpa is not None
                        else None
                    ),
                    rankine_constant_dimensionless=(
                        rankine_constant_dimensionless if include_rankine else None
                    ),
                    yield_stress_pa=(
                        yield_stress_mpa * 1e6
                        if include_johnson and yield_stress_mpa is not None
                        else None
                    ),
                )
            except (ValueError, OverflowError) as error:
                st.warning(f"Could not build graph data: {error}")
            else:
                graph_figure = go.Figure()
                graph_labels = {
                    "Euler": "Euler (theoretical; criterion not configured)",
                    "Rankine-Gordon": "Rankine-Gordon (provisional; verify constant)",
                    "Johnson": "Johnson (theoretical; criterion not configured)",
                }
                for theory_name, critical_loads_n in graph_curves.items():
                    if any(load_n is not None for load_n in critical_loads_n):
                        graph_figure.add_trace(
                            go.Scatter(
                                x=graph_slenderness_ratios,
                                y=[
                                    load_n / 1000 if load_n is not None else None
                                    for load_n in critical_loads_n
                                ],
                                mode="lines",
                                name=graph_labels[theory_name],
                                connectgaps=False,
                                hovertemplate=(
                                    "Slenderness ratio: %{x:.4g}<br>"
                                    "Critical load: %{y:.4g} kN<extra>%{fullData.name}</extra>"
                                ),
                            )
                        )

                if graph_figure.data:
                    graph_figure.add_vline(
                        x=slenderness_ratio_value,
                        line_dash="dash",
                        line_color="gray",
                    )
                    graph_figure.update_layout(
                        template="plotly_white",
                        hovermode="x unified",
                        legend_title_text="Theory status",
                        margin={"l": 20, "r": 20, "t": 20, "b": 20},
                    )
                    graph_figure.update_xaxes(
                        title_text="Slenderness ratio Le/k (dimensionless)"
                    )
                    graph_figure.update_yaxes(title_text="Critical load (kN)")
                    st.plotly_chart(
                        graph_figure,
                        width="stretch",
                        config={"displaylogo": False},
                    )
                    st.caption(
                        "Johnson points without a positive critical stress are omitted. "
                        "All curves remain theoretical/provisional until their course-specific "
                        "applicability criteria are configured."
                    )
                else:
                    st.info(
                        "No theory curves can be calculated yet. Enter E for Euler/Johnson, "
                        "or select Rankine and provide its strength and constant."
                    )

            with st.expander("Formulas, assumptions, and applicability", expanded=False):
                st.markdown("**Euler**")
                st.latex(r"P_E = \frac{\pi^2 E I_{min}}{L_e^2}")
                st.write(assessments["Euler"].message)
                st.markdown("**Rankine-Gordon**")
                st.latex(r"P_R = \frac{\sigma_c A}{1 + a (L_e/k)^2}")
                st.write(assessments["Rankine"].message)
                st.markdown("**Johnson parabolic**")
                st.latex(r"P_J = A\sigma_y\left(1 - \frac{\sigma_y}{4\pi^2 E}(L_e/k)^2\right)")
                st.write(assessments["Johnson"].message)

            if factor_of_safety is None:
                st.info(
                    "Enter a positive factor of safety if allowable loads are needed. "
                    "Allowable loads are withheld until theory applicability is confirmed."
                )
            else:
                st.info(
                    "Allowable loads are withheld because course-specific applicability "
                    "criteria are not configured. A factor of safety alone does not confirm "
                    "that a theory applies."
                )