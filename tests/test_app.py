import json
from dataclasses import replace
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import column_analysis.recommendation as recommendation_module
from column_analysis.materials import load_material_database
from column_analysis.recommendation import load_applicability_criteria
from column_analysis.validation import ApplicabilityStatus


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _app_with_circle(length_mm: float = 200.0, youngs_modulus_gpa: float | None = 200.0) -> AppTest:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    app = _select_custom_material(
        app,
        youngs_modulus_gpa=youngs_modulus_gpa,
        yield_stress_mpa=275.0,
    )
    app.number_input(key="diameter_mm").set_value(20.0)
    app.number_input(key="column_length_mm").set_value(length_mm)
    app.run(timeout=15)
    return app


def _select_custom_material(
    app: AppTest,
    *,
    name: str = "Test material",
    youngs_modulus_gpa: float | None = 200.0,
    yield_stress_mpa: float | None = None,
    compressive_strength_mpa: float | None = None,
    rankine_constant_dimensionless: float | None = None,
) -> AppTest:
    app.selectbox(key="material_selector").set_value("Custom Material")
    app.run(timeout=15)
    app.text_input(key="custom_material_name").set_value(name)
    values = {
        "youngs_modulus_gpa": youngs_modulus_gpa,
        "yield_stress_mpa": yield_stress_mpa,
        "compressive_strength_mpa": compressive_strength_mpa,
        "rankine_constant_dimensionless": rankine_constant_dimensionless,
    }
    for key, value in values.items():
        if value is not None:
            app.number_input(key=key).set_value(value)
    return app.run(timeout=15)


def _calculate(app: AppTest) -> AppTest:
    app.button(key="calculate_column").click()
    return app.run(timeout=15)


def _metric_values(app: AppTest) -> dict[str, str]:
    return {metric.label: metric.value for metric in app.metric}


def _comparison_rows(app: AppTest) -> dict[str, dict[str, str]]:
    records = app.dataframe[0].value.to_dict(orient="records")
    return {record["Theory"]: record for record in records}


def test_200_mm_pinned_circular_column_has_200_mm_effective_length() -> None:
    app = _calculate(_app_with_circle())

    metrics = _metric_values(app)
    assert app.selectbox(key="end_condition").value == "pinned-pinned"
    assert metrics["Effective-length factor K (dimensionless)"] == "1"
    assert metrics["Effective length Le"] == "0.2 m"
    assert metrics["Least radius of gyration k"] == "0.005 m"
    assert metrics["Slenderness ratio Le/k"] == "40"
    assert metrics["Second moment I_min (weaker axis: both)"] == "7.854 × 10⁻⁹ m⁴"
    assert metrics["Euler critical load"] == "387.58 kN"


def test_50_mm_by_3000_mm_pinned_column_euler_load_is_67_288_kn() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    app = _select_custom_material(app, yield_stress_mpa=250.0)
    app.number_input(key="diameter_mm").set_value(50.0)
    app.number_input(key="column_length_mm").set_value(3000.0)
    app.run(timeout=15)
    app = _calculate(app)

    metrics = _metric_values(app)
    assert metrics["Second moment I_min (weaker axis: both)"] == "3.068 × 10⁻⁷ m⁴"
    assert metrics["Effective length Le"] == "3 m"
    assert metrics["Slenderness ratio Le/k"] == "240"
    assert metrics["Euler critical load"] == "67.288 kN"


def test_missing_rankine_and_johnson_inputs_are_not_calculated() -> None:
    app = _app_with_circle()
    app.selectbox(key="material_selector").set_value("Aluminium")
    app.run(timeout=15)
    app = _calculate(app)

    rows = _comparison_rows(app)
    assert rows["Rankine"]["Critical load (kN)"] == "Not calculated"
    assert "Not calculated — missing required input" in rows["Rankine"]["Calculation status"]
    assert rows["Johnson"]["Critical load (kN)"] == "Not calculated"
    assert "Not calculated — missing required input" in rows["Johnson"]["Calculation status"]


def test_invalid_youngs_modulus_does_not_produce_theory_loads() -> None:
    app = _app_with_circle(youngs_modulus_gpa=0.0)
    app.number_input(key="yield_stress_mpa").set_value(250.0)
    app.run(timeout=15)
    app = _calculate(app)

    rows = _comparison_rows(app)
    assert rows["Euler"]["Critical load (kN)"] == "Not calculated"
    assert "Not calculated — invalid input" in rows["Euler"]["Calculation status"]
    assert rows["Johnson"]["Critical load (kN)"] == "Not calculated"
    assert "Not calculated — invalid input" in rows["Johnson"]["Calculation status"]
    assert _metric_values(app)["Young's modulus E for recommendation"] == "Not provided or valid"


def test_recommended_theory_section_explains_johnson_and_short_column_limitation() -> None:
    app = _calculate(_app_with_circle())

    assert any(item.value == "Recommended Theory" for item in app.subheader)
    assert any("Recommended theory: Johnson" in item.value for item in app.success)
    assert any("Very low slenderness can be crushing-dominated" in item.value for item in app.warning)
    assert any(
        "not a certification of short-column behavior" in item.value
        for item in app.markdown
    )
    metrics = _metric_values(app)
    assert metrics["Recommendation slenderness ratio Le/k"] == "40 dimensionless"
    assert metrics["Young's modulus E for recommendation"] == "200 GPa"
    assert metrics["Yield stress sigma_y for recommendation"] == "275 MPa"
    assert metrics["Compressive strength sigma_c for recommendation"] == "Not provided or valid"
    assert any("MechanicalC" in item.value for item in app.markdown)
    assert any("Rankine criteria are not configured" in item.value for item in app.caption)


def test_separate_crushing_check_uses_compressive_strength_and_applied_load() -> None:
    app = _app_with_circle()
    app.number_input(key="compressive_strength_mpa").set_value(250.0)
    app.number_input(key="applied_load_kn").set_value(100.0)
    app.run(timeout=15)
    app = _calculate(app)

    metrics = _metric_values(app)
    assert metrics["Theoretical squash load (compressive strength × area)"] == "78.54 kN"
    assert any(
        "exceeds the theoretical squash load" in item.value for item in app.error
    )
    assert any(
        "separate from Rankine-Gordon" in item.value for item in app.caption
    )


def test_long_column_recommendation_compares_prediction_without_claiming_safety() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    app = _select_custom_material(
        app,
        youngs_modulus_gpa=200.0,
        yield_stress_mpa=250.0,
    )
    app.number_input(key="diameter_mm").set_value(50.0)
    app.number_input(key="column_length_mm").set_value(3000.0)
    app.number_input(key="applied_load_kn").set_value(10.0)
    app.run(timeout=15)
    app = _calculate(app)

    assert any(
        "Recommended theory: Euler" in item.value
        for item in app.success
    )
    assert any(
        "Euler critical load: 67.288 kN; applied load: 10 kN" in item.value
        and "does not establish safety" in item.value
        for item in app.markdown
    )
    rows = _comparison_rows(app)
    assert rows["Euler"]["Applicability status"] == ApplicabilityStatus.APPLICABLE.value
    assert rows["Euler"]["Applicability reason"]
    assert rows["Johnson"]["Applicability status"] == ApplicabilityStatus.OUT_OF_RANGE.value
    assert rows["Johnson"]["Applicability reason"]

    chart_specs = [
        json.loads(chart.proto.spec) for chart in app.get("plotly_chart")
    ]
    euler_chart = next(
        chart
        for chart in chart_specs
        if any(trace.get("name") == "Euler" for trace in chart["data"])
    )
    euler_marker = next(
        trace
        for trace in euler_chart["data"]
        if trace.get("mode") == "markers"
        and trace.get("name") == "Current column — applicable point"
    )
    assert euler_marker["x"] == [240.0]
    assert euler_marker["y"][0] == pytest.approx(67.2879268)
    assert any(
        trace.get("mode") == "lines"
        and trace.get("name") == "Johnson"
        for chart in chart_specs
        for trace in chart["data"]
    )
    johnson_chart = next(
        chart
        for chart in chart_specs
        if any(trace.get("name") == "Johnson" for trace in chart["data"])
    )
    johnson_curve = next(
        trace for trace in johnson_chart["data"] if trace.get("name") == "Johnson"
    )
    assert johnson_curve["x"][-1] == pytest.approx(125.663706, rel=1e-6)
    assert max(johnson_curve["x"]) < 240.0
    assert not any(
        trace.get("name") == "Current column — applicable point"
        for trace in johnson_chart["data"]
    )
    assert any(
        shape.get("x0") == 240.0 and shape.get("x1") == 240.0
        for shape in euler_chart["layout"]["shapes"]
    )
    assert not any(
        "safe" in item.value.lower().split() for item in app.success
    )


def test_three_individual_graphs_show_their_own_calculated_theory_curves() -> None:
    app = _app_with_circle()
    app.number_input(key="youngs_modulus_gpa").set_value(205.0)
    app.number_input(key="compressive_strength_mpa").set_value(250.0)
    app.number_input(key="rankine_constant_dimensionless").set_value(0.001)
    app.number_input(key="yield_stress_mpa").set_value(275.0)
    app.run(timeout=15)
    app = _calculate(app)

    chart_specs = [
        json.loads(chart.proto.spec) for chart in app.get("plotly_chart")
    ]
    assert len(chart_specs) == 3
    expected_titles = {
        "Euler": "Euler Theory — Critical Load vs. Slenderness",
        "Rankine-Gordon": "Rankine–Gordon Theory — Critical Load vs. Slenderness",
        "Johnson": "Johnson Theory — Critical Load vs. Slenderness",
    }
    for theory_name, expected_title in expected_titles.items():
        chart = next(
            chart
            for chart in chart_specs
            if any(trace.get("name") == theory_name for trace in chart["data"])
        )
        assert chart["layout"]["title"]["text"] == expected_title
        assert any(
            trace.get("mode") == "lines" and trace.get("name") == theory_name
            for trace in chart["data"]
        )
        assert any(
            trace.get("mode") == "markers"
            and trace.get("name")
            in {
                "Current column — applicable point",
                "Current column — formula prediction",
            }
            for trace in chart["data"]
        )

    transition_ratio = 121.304
    euler_chart = next(
        chart
        for chart in chart_specs
        if any(trace.get("name") == "Euler" for trace in chart["data"])
    )
    johnson_chart = next(
        chart
        for chart in chart_specs
        if any(trace.get("name") == "Johnson" for trace in chart["data"])
    )
    euler_curve = next(
        trace for trace in euler_chart["data"] if trace.get("name") == "Euler"
    )
    johnson_curve = next(
        trace for trace in johnson_chart["data"] if trace.get("name") == "Johnson"
    )
    rankine_chart = next(
        chart
        for chart in chart_specs
        if any(trace.get("name") == "Rankine-Gordon" for trace in chart["data"])
    )
    rankine_curve = next(
        trace
        for trace in rankine_chart["data"]
        if trace.get("name") == "Rankine-Gordon"
    )
    assert max(rankine_curve["x"]) > transition_ratio
    assert johnson_curve["x"][-1] == pytest.approx(transition_ratio, abs=0.001)
    euler_transition_index = euler_curve["x"].index(johnson_curve["x"][-1])
    assert johnson_curve["y"][-1] == pytest.approx(
        euler_curve["y"][euler_transition_index],
        rel=1e-4,
    )
    assert any(
        shape.get("x0") == pytest.approx(transition_ratio, abs=0.001)
        and shape.get("x1") == pytest.approx(transition_ratio, abs=0.001)
        for shape in johnson_chart["layout"]["shapes"]
    )


def test_johnson_curve_honors_configured_lower_applicability_boundary(monkeypatch) -> None:
    criteria = replace(
        load_applicability_criteria(),
        johnson_minimum_slenderness_ratio=50.0,
        johnson_range_reference="Test-only configured intermediate range",
        johnson_range_reference_url="https://example.org/test-johnson-range",
    )
    monkeypatch.setattr(
        recommendation_module,
        "load_applicability_criteria",
        lambda: criteria,
    )
    app = _app_with_circle(length_mm=400.0)
    app.number_input(key="youngs_modulus_gpa").set_value(205.0)
    app.run(timeout=15)
    app = _calculate(app)

    chart_specs = [
        json.loads(chart.proto.spec) for chart in app.get("plotly_chart")
    ]
    johnson_chart = next(
        chart
        for chart in chart_specs
        if any(trace.get("name") == "Johnson" for trace in chart["data"])
    )
    johnson_curve = next(
        trace for trace in johnson_chart["data"] if trace.get("name") == "Johnson"
    )
    assert johnson_curve["x"][0] == 50.0
    assert johnson_curve["x"][-1] == pytest.approx(121.304, abs=0.001)
    applicable_marker = next(
        trace
        for trace in johnson_chart["data"]
        if trace.get("name") == "Current column — applicable point"
    )
    assert applicable_marker["x"] == [80.0]


def test_applied_load_assessment_and_theoretical_allowable_are_applicability_gated() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    app = _select_custom_material(
        app,
        youngs_modulus_gpa=200.0,
        yield_stress_mpa=250.0,
    )
    app.number_input(key="diameter_mm").set_value(50.0)
    app.number_input(key="column_length_mm").set_value(3000.0)
    app.number_input(key="applied_load_kn").set_value(80.0)
    app.number_input(key="factor_of_safety").set_value(2.0)
    app.run(timeout=15)
    app = _calculate(app)

    assert _metric_values(app)["Entered factor of safety"] == "2 dimensionless"
    assert any("Applied load exceeds predicted critical load" in item.value for item in app.error)
    assert any(
        "Applied load exceeds theoretical allowable load" in item.value
        for item in app.warning
    )
    assessment_rows = app.dataframe[1].value.to_dict(orient="records")
    rows = {record["Theory"]: record for record in assessment_rows}
    assert rows["Euler"]["Applicability"] == ApplicabilityStatus.APPLICABLE.value
    assert rows["Euler"]["Applied / critical ratio"] == "1.1889 dimensionless"
    assert rows["Euler"]["Critical-load assessment"] == (
        "Applied load exceeds predicted critical load"
    )
    assert rows["Euler"]["Theoretical allowable load (kN)"] == "33.644 kN"
    assert rows["Euler"]["Allowable-load assessment"] == (
        "Applied load exceeds theoretical allowable load"
    )
    assert rows["Johnson"]["Applicability"] == ApplicabilityStatus.OUT_OF_RANGE.value
    assert rows["Johnson"]["Applied / critical ratio"] == "Not assessed"
    assert rows["Johnson"]["Theoretical allowable load (kN)"].startswith(
        "Not calculated — applicability"
    )


def test_unverified_theory_is_not_compared_with_applied_load() -> None:
    app = _calculate(_app_with_circle())

    assessment_rows = app.dataframe[1].value.to_dict(orient="records")
    rows = {record["Theory"]: record for record in assessment_rows}
    assert rows["Euler"]["Applicability"] == ApplicabilityStatus.OUT_OF_RANGE.value
    assert rows["Euler"]["Applied / critical ratio"] == "Not assessed"
    assert rows["Euler"]["Critical-load assessment"] == (
        "Not assessed — applicability not confirmed"
    )
    assert rows["Euler"]["Theoretical allowable load (kN)"].startswith(
        "Not calculated — applicability"
    )


def test_committed_input_change_hides_results_until_recalculated() -> None:
    app = _calculate(_app_with_circle())
    assert any(metric.label == "Euler critical load" for metric in app.metric)

    app.number_input(key="column_length_mm").set_value(400.0)
    app.run(timeout=15)

    assert len(app.dataframe) == 0
    assert any("Select Calculate to update the analysis" in item.value for item in app.info)


def test_rectangular_ui_reports_both_axes_and_weaker_axis() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    app.selectbox(key="section_type").set_value("Rectangular")
    app.run(timeout=15)
    app = _select_custom_material(app)
    app.number_input(key="width_mm").set_value(50.0)
    app.number_input(key="height_mm").set_value(100.0)
    app.number_input(key="column_length_mm").set_value(200.0)
    app.run(timeout=15)
    app = _calculate(app)

    metrics = _metric_values(app)
    assert metrics["Area"] == "0.005 m²"
    assert metrics["Second moment I_min (weaker axis: y)"] == "1.042 × 10⁻⁶ m⁴"
    assert metrics["Effective length Le"] == "0.2 m"


@pytest.mark.parametrize(
    (
        "section_type",
        "dimension_values_mm",
        "dimension_labels",
        "expected_area",
        "expected_centroid_x",
        "expected_centroid_y",
    ),
    [
        (
            "Solid circular",
            {"diameter_mm": 50.0},
            {"diameter_mm": "Diameter D (mm)"},
            "0.0019635 m²",
            "0.025 m",
            "0.025 m",
        ),
        (
            "Rectangular",
            {"width_mm": 50.0, "height_mm": 100.0},
            {"width_mm": "Width B (mm)", "height_mm": "Height H (mm)"},
            "0.005 m²",
            "0.025 m",
            "0.05 m",
        ),
        (
            "Hollow circular (pipe)",
            {"outer_diameter_mm": 80.0, "inner_diameter_mm": 60.0},
            {
                "outer_diameter_mm": "Outer diameter D (mm)",
                "inner_diameter_mm": "Inner diameter d (mm)",
            },
            "0.0021991 m²",
            "0.04 m",
            "0.04 m",
        ),
        (
            "Hollow rectangular (RHS / box)",
            {
                "outer_width_mm": 80.0,
                "outer_height_mm": 120.0,
                "wall_thickness_mm": 5.0,
            },
            {
                "outer_width_mm": "Outer width B (mm)",
                "outer_height_mm": "Outer height H (mm)",
                "wall_thickness_mm": "Wall thickness t (mm)",
            },
            "0.0019 m²",
            "0.04 m",
            "0.06 m",
        ),
        (
            "I-section",
            {
                "overall_depth_mm": 200.0,
                "flange_width_mm": 100.0,
                "web_thickness_mm": 10.0,
                "flange_thickness_mm": 15.0,
            },
            {
                "overall_depth_mm": "Overall depth H (mm)",
                "flange_width_mm": "Flange width B (mm)",
                "web_thickness_mm": "Web thickness tw (mm)",
                "flange_thickness_mm": "Flange thickness tf (mm)",
            },
            "0.0047 m²",
            "0.05 m",
            "0.1 m",
        ),
        (
            "Channel (C-section)",
            {
                "overall_depth_mm": 200.0,
                "flange_width_mm": 80.0,
                "web_thickness_mm": 10.0,
                "flange_thickness_mm": 15.0,
            },
            {
                "overall_depth_mm": "Overall depth H (mm)",
                "flange_width_mm": "Flange width B (overall width) (mm)",
                "web_thickness_mm": "Web thickness tw (mm)",
                "flange_thickness_mm": "Flange thickness tf (mm)",
            },
            "0.0041 m²",
            "0.025488 m",
            "0.1 m",
        ),
        (
            "Angle (L-section)",
            {
                "horizontal_leg_mm": 80.0,
                "vertical_leg_mm": 100.0,
                "thickness_mm": 10.0,
            },
            {
                "horizontal_leg_mm": "Horizontal leg b (mm)",
                "vertical_leg_mm": "Vertical leg h (mm)",
                "thickness_mm": "Thickness t (mm)",
            },
            "0.0017 m²",
            "0.021471 m",
            "0.031471 m",
        ),
        (
            "T-section",
            {
                "overall_depth_mm": 180.0,
                "flange_width_mm": 90.0,
                "web_thickness_mm": 10.0,
                "flange_thickness_mm": 15.0,
            },
            {
                "overall_depth_mm": "Overall depth H (mm)",
                "flange_width_mm": "Flange width B (mm)",
                "web_thickness_mm": "Web thickness tw (mm)",
                "flange_thickness_mm": "Flange thickness tf (mm)",
            },
            "0.003 m²",
            "0.045 m",
            "0.123 m",
        ),
    ],
)
def test_each_section_can_be_selected_dimensioned_and_calculated(
    section_type: str,
    dimension_values_mm: dict[str, float],
    dimension_labels: dict[str, str],
    expected_area: str,
    expected_centroid_x: str,
    expected_centroid_y: str,
) -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    app.selectbox(key="section_type").set_value(section_type)
    app.run(timeout=15)

    visible_inputs = {number_input.key: number_input for number_input in app.number_input}
    for input_key, input_value in dimension_values_mm.items():
        assert input_key in visible_inputs
        assert visible_inputs[input_key].label == dimension_labels[input_key]
        app.number_input(key=input_key).set_value(input_value)
    app.number_input(key="column_length_mm").set_value(3000.0)
    app.run(timeout=15)
    app = _calculate(app)

    metrics = _metric_values(app)
    assert app.selectbox(key="section_type").value == section_type
    assert metrics["Area"] == expected_area
    assert metrics["Centroid x̄"] == expected_centroid_x
    assert metrics["Centroid ȳ"] == expected_centroid_y
    assert "Second moment Ixx" in metrics
    assert "Second moment Iyy" in metrics
    assert "Product of inertia Ixy" in metrics
    assert "Principal second moment I1" in metrics
    assert "Principal second moment I2" in metrics
    assert any(label.startswith("Second moment I_min") for label in metrics)
    assert metrics["Least radius of gyration k"]


def test_angle_ui_uses_minimum_principal_moment_for_buckling() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    app.selectbox(key="section_type").set_value("Angle (L-section)")
    app.run(timeout=15)
    app = _select_custom_material(app)
    app.number_input(key="horizontal_leg_mm").set_value(80.0)
    app.number_input(key="vertical_leg_mm").set_value(100.0)
    app.number_input(key="thickness_mm").set_value(10.0)
    app.number_input(key="column_length_mm").set_value(3000.0)
    app.run(timeout=15)
    app = _calculate(app)

    metrics = _metric_values(app)
    assert metrics["Product of inertia Ixy"] == "-7.412 × 10⁻⁷ m⁴"
    assert metrics["Principal second moment I2"] == "4.89 × 10⁻⁷ m⁴"
    assert metrics["Second moment I_min (weaker axis: principal)"] == (
        "4.89 × 10⁻⁷ m⁴"
    )
    assert metrics["Least radius of gyration k"] == "0.01696 m"
    assert metrics["Euler critical load"] == "107.25 kN"


def test_invalid_hollow_geometry_shows_shape_specific_error() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    app.selectbox(key="section_type").set_value("Hollow rectangular (RHS / box)")
    app.run(timeout=15)
    app.number_input(key="outer_width_mm").set_value(20.0)
    app.number_input(key="outer_height_mm").set_value(100.0)
    app.number_input(key="wall_thickness_mm").set_value(10.0)
    app.number_input(key="column_length_mm").set_value(1000.0)
    app.run(timeout=15)
    app = _calculate(app)

    assert any(
        "outer_width_m must be greater than twice wall_thickness_m" in error.value
        for error in app.error
    )


def test_material_dropdown_loads_database_values_into_editable_fields() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    material_options = app.selectbox(key="material_selector").options
    database = load_material_database()

    assert len(material_options) == 10
    assert len(database) == 9
    assert material_options == [
        "Generic Softwood",
        "Generic Hardwood",
        "Cast Iron",
        "Brass",
        "Bronze",
        "Copper",
        "Aluminium",
        "Stainless Steel",
        "Structural Steel",
        "Custom Material",
    ]
    assert not any(
        selectbox.key == "material_grade_selector" for selectbox in app.selectbox
    )
    assert app.selectbox(key="material_selector").value == "Structural Steel"
    assert {
        number_input.key for number_input in app.number_input
    }.issuperset(
        {
            "youngs_modulus_gpa",
            "compressive_strength_mpa",
            "yield_stress_mpa",
            "rankine_constant_dimensionless",
        }
    )

    for material in database.values():
        app.selectbox(key="material_selector").set_value(material.display_name)
        app.run(timeout=15)
        for property_name, property_value in material.properties.items():
            assert app.number_input(key=property_name).value == property_value.value
            assert app.session_state["material_property_sources"][property_name] == (
                "database" if property_value.value is not None else "unavailable"
            )


def test_custom_material_optional_properties_remain_blank_until_entered() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    app = _select_custom_material(app, yield_stress_mpa=None)

    assert app.text_input(key="custom_material_name").value == "Test material"
    assert app.number_input(key="youngs_modulus_gpa").value == 200.0
    assert app.number_input(key="yield_stress_mpa").value is None
    assert app.number_input(key="compressive_strength_mpa").value is None
    assert app.number_input(key="rankine_constant_dimensionless").value is None
    assert any("Custom material properties entered by the user" in item.value for item in app.caption)
    assert app.session_state["material_property_sources"]["yield_stress_mpa"] == "unavailable"


def test_material_switch_recalculates_results_without_stale_custom_properties() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    app = _select_custom_material(
        app,
        youngs_modulus_gpa=200.0,
        yield_stress_mpa=275.0,
    )
    app.number_input(key="diameter_mm").set_value(50.0)
    app.number_input(key="column_length_mm").set_value(3000.0)
    app.number_input(key="factor_of_safety").set_value(2.0)
    app.run(timeout=15)
    app = _calculate(app)
    custom_euler_load = _metric_values(app)["Euler critical load"]
    assert custom_euler_load == "67.288 kN"
    assert _metric_values(app)["Theoretical allowable load"] == "33.644 kN"
    custom_graph_specs = [json.loads(chart.proto.spec) for chart in app.get("plotly_chart")]
    assert any(
        trace.get("name") == "Johnson"
        for chart in custom_graph_specs
        for trace in chart["data"]
    )

    app.selectbox(key="material_selector").set_value("Aluminium")
    app.run(timeout=15)

    metrics = _metric_values(app)
    assert app.number_input(key="youngs_modulus_gpa").value == 69.0
    assert app.number_input(key="yield_stress_mpa").value is None
    assert app.number_input(key="compressive_strength_mpa").value is None
    assert app.number_input(key="rankine_constant_dimensionless").value is None
    assert metrics["Euler critical load"] != custom_euler_load
    assert metrics["Johnson critical load"] == "Not calculated"
    assert metrics["Recommended theory"] == "None verified"
    assert metrics["Theoretical allowable load"] == "Not justified"
    assert app.session_state["material_property_sources"]["yield_stress_mpa"] == "unavailable"
    assert not any(
        "Select Calculate to update the analysis" in item.value for item in app.info
    )
    graph_specs = [json.loads(chart.proto.spec) for chart in app.get("plotly_chart")]
    assert not any(
        trace.get("name") == "Johnson"
        for chart in graph_specs
        for trace in chart["data"]
    )

    app.selectbox(key="material_selector").set_value("Custom Material")
    app.run(timeout=15)
    assert app.number_input(key="youngs_modulus_gpa").value == 200.0
    assert app.number_input(key="yield_stress_mpa").value == 275.0


def test_standard_material_edits_recalculate_theories_recommendation_and_graphs() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    app.number_input(key="diameter_mm").set_value(20.0)
    app.number_input(key="column_length_mm").set_value(200.0)
    app.number_input(key="factor_of_safety").set_value(2.0)
    app.run(timeout=15)
    app = _calculate(app)
    initial_euler_load = _metric_values(app)["Euler critical load"]
    assert _metric_values(app)["Johnson critical load"] == "Not calculated"

    app.number_input(key="youngs_modulus_gpa").set_value(100.0)
    app.run(timeout=15)
    assert _metric_values(app)["Euler critical load"] != initial_euler_load

    app.number_input(key="yield_stress_mpa").set_value(275.0)
    app.run(timeout=15)
    assert _metric_values(app)["Johnson critical load"] != "Not calculated"
    assert _metric_values(app)["Recommended theory"] == "Johnson"
    assert _metric_values(app)["Theoretical allowable load"] != "Not justified"
    assert _comparison_rows(app)["Johnson"]["Applicability status"] == "applicable"

    app.number_input(key="compressive_strength_mpa").set_value(250.0)
    app.run(timeout=15)
    app.number_input(key="rankine_constant_dimensionless").set_value(0.001)
    app.run(timeout=15)
    assert _metric_values(app)["Rankine critical load"] != "Not calculated"
    graph_specs = [json.loads(chart.proto.spec) for chart in app.get("plotly_chart")]
    assert any(
        trace.get("name") == "Rankine-Gordon"
        for chart in graph_specs
        for trace in chart["data"]
    )
    assert any(
        "User-entered: Young's modulus E" in caption.value
        for caption in app.caption
    )
    saved_material = load_material_database()["structural-steel"]
    assert saved_material.properties["youngs_modulus_gpa"].value == 200.0
    assert saved_material.properties["yield_stress_mpa"].value is None
    assert saved_material.properties["compressive_strength_mpa"].value is None
    assert saved_material.properties["rankine_constant_dimensionless"].value is None


@pytest.mark.parametrize(
    ("property_name", "value", "message"),
    [
        ("youngs_modulus_gpa", 0.0, "Young's modulus E must be a finite"),
        ("youngs_modulus_gpa", 1e6, "Young's modulus E must not exceed 2000 GPa"),
        (
            "compressive_strength_mpa",
            0.0,
            "Compressive strength sigma_c must be a finite",
        ),
        ("yield_stress_mpa", 0.0, "Yield stress sigma_y must be a finite"),
        (
            "rankine_constant_dimensionless",
            0.0,
            "Rankine constant a must be a finite",
        ),
    ],
)
def test_standard_material_property_inputs_reject_invalid_values(
    property_name: str,
    value: float,
    message: str,
) -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    app.number_input(key="diameter_mm").set_value(20.0)
    app.number_input(key="column_length_mm").set_value(200.0)
    app.number_input(key=property_name).set_value(value)
    app.run(timeout=15)
    app = _calculate(app)

    assert any(message in item.value for item in app.markdown)


def test_invalid_custom_name_and_required_modulus_are_reported() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    app = _select_custom_material(app, name=" ", youngs_modulus_gpa=0.0)
    app.number_input(key="diameter_mm").set_value(20.0)
    app.number_input(key="column_length_mm").set_value(200.0)
    app.run(timeout=15)
    app = _calculate(app)

    messages = [item.value for item in app.markdown]
    assert any("Custom material name must not be empty" in message for message in messages)
    assert any("Young's modulus E must be a finite" in message for message in messages)
    assert _metric_values(app)["Euler critical load"] == "Not calculated"


def test_invalid_optional_custom_property_is_excluded_without_blocking_euler() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    app = _select_custom_material(
        app,
        youngs_modulus_gpa=200.0,
        compressive_strength_mpa=-10.0,
    )
    app.number_input(key="diameter_mm").set_value(20.0)
    app.number_input(key="column_length_mm").set_value(200.0)
    app.run(timeout=15)
    app = _calculate(app)

    messages = [item.value for item in app.markdown]
    assert any("Compressive strength sigma_c must be a finite" in message for message in messages)
    assert _metric_values(app)["Euler critical load"] != "Not calculated"
    assert _metric_values(app)["Rankine critical load"] == "Not calculated"


def test_missing_theory_inputs_are_reported_in_one_compact_message() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)

    missing_input_messages = [
        item.value
        for item in app.info
        if item.value.startswith("The following theory predictions are unavailable")
    ]
    assert len(missing_input_messages) == 1
    assert "compressive/crushing strength sigma_c" in missing_input_messages[0]
    assert "Rankine constant a" in missing_input_messages[0]
    assert "yield stress sigma_y" in missing_input_messages[0]


def test_short_intermediate_and_long_column_recommendations_with_configured_range(
    monkeypatch,
) -> None:
    criteria = replace(
        load_applicability_criteria(),
        johnson_minimum_slenderness_ratio=20.0,
        johnson_range_reference="Test-only configured intermediate range",
        johnson_range_reference_url="https://example.org/test-johnson-range",
    )
    monkeypatch.setattr(
        recommendation_module,
        "load_applicability_criteria",
        lambda: criteria,
    )
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    app = _select_custom_material(app, yield_stress_mpa=275.0)
    app.number_input(key="diameter_mm").set_value(20.0)
    app.number_input(key="column_length_mm").set_value(50.0)
    app.run(timeout=15)
    app = _calculate(app)

    metrics = _metric_values(app)
    assert metrics["Slenderness ratio Le/k"] == "10"
    assert any("Recommended Theory" in item.value for item in app.subheader)
    assert any("Insufficient information to recommend" in item.value for item in app.info)

    app.number_input(key="column_length_mm").set_value(400.0)
    app.run(timeout=15)
    app = _calculate(app)
    assert _metric_values(app)["Slenderness ratio Le/k"] == "80"
    assert any("Recommended theory: Johnson" in item.value for item in app.success)

    app.number_input(key="column_length_mm").set_value(1000.0)
    app.run(timeout=15)
    app = _calculate(app)
    assert _metric_values(app)["Slenderness ratio Le/k"] == "200"
    assert any("Recommended theory: Euler" in item.value for item in app.success)


@pytest.mark.parametrize("factor_of_safety", [0.5, 1.0])
def test_factor_of_safety_below_one_is_not_used_for_allowable_load(
    factor_of_safety: float,
) -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    app = _select_custom_material(app, yield_stress_mpa=275.0)
    app.number_input(key="diameter_mm").set_value(50.0)
    app.number_input(key="column_length_mm").set_value(3000.0)
    app.number_input(key="factor_of_safety").set_value(factor_of_safety)
    app.run(timeout=15)
    app = _calculate(app)

    assert _metric_values(app)["Theoretical allowable load"] == "Not justified"
    assert any(
        "Factor of safety must be greater than 1.0" in item.value
        for item in app.markdown
    )


@pytest.mark.parametrize("youngs_modulus_gpa", [1e6, 1e308])
def test_modulus_that_overflows_si_conversion_does_not_recommend_a_theory(
    youngs_modulus_gpa: float,
) -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    app = _select_custom_material(
        app,
        youngs_modulus_gpa=youngs_modulus_gpa,
        yield_stress_mpa=275.0,
    )
    app.number_input(key="diameter_mm").set_value(50.0)
    app.number_input(key="column_length_mm").set_value(3000.0)
    app.run(timeout=15)
    app = _calculate(app)

    assert _metric_values(app)["Recommended theory"] == "None verified"
    assert any(
        "Young's modulus E must not exceed 2000 GPa" in item.value
        for item in app.markdown
    )