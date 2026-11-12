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
    app.number_input(key="diameter_mm").set_value(20.0)
    app.number_input(key="column_length_mm").set_value(length_mm)
    if youngs_modulus_gpa is not None:
        app.number_input(key="youngs_modulus_gpa").set_value(youngs_modulus_gpa)
    app.run(timeout=15)
    return app


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


def test_default_column_classification_uses_material_specific_properties() -> None:
    app = _calculate(_app_with_circle())

    assert any(item.value == "### Column Classification" for item in app.markdown)
    metrics = _metric_values(app)
    assert metrics["Classification"] == "Short"
    assert metrics["Current slenderness ratio"] == "40 dimensionless"
    assert any("SHORT COLUMN" in item.value for item in app.success)
    assert any(
        "mechanicalc.com/reference/column-buckling" in item.value
        for item in app.caption
    )


def test_classification_reports_missing_material_property_without_inventing_it() -> None:
    app = _app_with_circle()
    app.selectbox(key="material_selector").set_value("Aluminium Alloy 6061-T6")
    app.run(timeout=15)
    app = _calculate(app)

    assert _metric_values(app)["Classification"] == "Classification unavailable"
    assert any("yield stress" in item.value for item in app.warning)


def test_column_classification_updates_with_geometry_and_end_condition() -> None:
    app = _calculate(_app_with_circle(length_mm=200.0))
    assert _metric_values(app)["Classification"] == "Short"

    app.number_input(key="column_length_mm").set_value(500.0)
    app.run(timeout=15)
    app = _calculate(app)
    assert _metric_values(app)["Classification"] == "Intermediate"

    app.selectbox(key="end_condition").set_value("fixed-free")
    app.run(timeout=15)
    app = _calculate(app)
    assert _metric_values(app)["Classification"] == "Long"

    app.number_input(key="diameter_mm").set_value(40.0)
    app.run(timeout=15)
    app = _calculate(app)
    assert _metric_values(app)["Classification"] == "Intermediate"

    app.selectbox(key="material_selector").set_value("Stainless Steel")
    app.run(timeout=15)
    app = _calculate(app)
    assert _metric_values(app)["Classification"] == "Intermediate"

    app.selectbox(key="section_type").set_value("Rectangular")
    app.run(timeout=15)
    app.number_input(key="width_mm").set_value(40.0)
    app.number_input(key="height_mm").set_value(20.0)
    app.number_input(key="column_length_mm").set_value(200.0)
    app.selectbox(key="end_condition").set_value("pinned-pinned")
    app.run(timeout=15)
    app = _calculate(app)
    assert _metric_values(app)["Classification"] == "Short"


def test_50_mm_by_3000_mm_pinned_column_euler_load_is_67_288_kn() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    app.number_input(key="diameter_mm").set_value(50.0)
    app.number_input(key="column_length_mm").set_value(3000.0)
    app.number_input(key="youngs_modulus_gpa").set_value(200.0)
    app.run(timeout=15)
    app = _calculate(app)

    metrics = _metric_values(app)
    assert metrics["Second moment I_min (weaker axis: both)"] == "3.068 × 10⁻⁷ m⁴"
    assert metrics["Effective length Le"] == "3 m"
    assert metrics["Slenderness ratio Le/k"] == "240"
    assert metrics["Euler critical load"] == "67.288 kN"


def test_missing_rankine_and_johnson_inputs_are_not_calculated() -> None:
    app = _app_with_circle()
    app.selectbox(key="material_selector").set_value("Aluminium Alloy 6061-T6")
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


def test_short_column_classification_does_not_recommend_intermediate_theory() -> None:
    app = _calculate(_app_with_circle())

    assert any(item.value == "Recommended Theory" for item in app.subheader)
    assert any("Insufficient information to recommend" in item.value for item in app.info)
    assert any("SHORT COLUMN" in item.value for item in app.success)
    metrics = _metric_values(app)
    assert metrics["Recommendation slenderness ratio Le/k"] == "40 dimensionless"
    assert metrics["Young's modulus E for recommendation"] == "200 GPa"
    assert metrics["Yield stress sigma_y for recommendation"] == "275 MPa"
    assert metrics["Compressive strength sigma_c for recommendation"] == "Not provided or valid"
    assert _comparison_rows(app)["Johnson"]["Applicability status"] == ApplicabilityStatus.OUT_OF_RANGE.value
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
    app.number_input(key="diameter_mm").set_value(50.0)
    app.number_input(key="column_length_mm").set_value(3000.0)
    app.number_input(key="youngs_modulus_gpa").set_value(200.0)
    app.number_input(key="yield_stress_mpa").set_value(250.0)
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
    app = _app_with_circle(length_mm=500.0)
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
    assert applicable_marker["x"] == [100.0]


def test_applied_load_assessment_and_theoretical_allowable_are_applicability_gated() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    app.number_input(key="diameter_mm").set_value(50.0)
    app.number_input(key="column_length_mm").set_value(3000.0)
    app.number_input(key="youngs_modulus_gpa").set_value(200.0)
    app.number_input(key="yield_stress_mpa").set_value(250.0)
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
    app.number_input(key="width_mm").set_value(50.0)
    app.number_input(key="height_mm").set_value(100.0)
    app.number_input(key="column_length_mm").set_value(200.0)
    app.number_input(key="youngs_modulus_gpa").set_value(200.0)
    app.run(timeout=15)
    app = _calculate(app)

    metrics = _metric_values(app)
    assert metrics["Area"] == "0.005 m²"
    assert metrics["Second moment I_min (weaker axis: y)"] == "1.042 × 10⁻⁶ m⁴"
    assert metrics["Effective length Le"] == "0.2 m"


def test_material_dropdown_has_four_options_and_populates_default_material() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    material_options = app.selectbox(key="material_selector").options
    database = load_material_database()

    assert len(material_options) == len(database) == 4
    assert material_options == [
        "Structural Steel",
        "Stainless Steel",
        "Aluminium Alloy 6061-T6",
        "Copper",
    ]
    assert not any(
        selectbox.key == "material_grade_selector" for selectbox in app.selectbox
    )
    assert app.selectbox(key="material_selector").value == "Structural Steel"
    assert app.number_input(key="youngs_modulus_gpa").value == 205.0
    assert app.session_state["yield_stress_mpa"] == 275.0
    assert app.session_state["compressive_strength_mpa"] is None
    assert app.session_state["rankine_constant_dimensionless"] is None
    assert app.session_state["material_property_sources"]["youngs_modulus_gpa"] == "database"
    assert any("SteelConstruction.info" in item.value for item in app.markdown)

    app.selectbox(key="material_selector").set_value("Stainless Steel")
    app.run(timeout=15)
    assert app.number_input(key="youngs_modulus_gpa").value == 193.0
    assert app.number_input(key="yield_stress_mpa").value == 205.0


def test_material_changes_update_properties_and_clear_stale_overrides() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    app.selectbox(key="material_selector").set_value("Stainless Steel")
    app.run(timeout=15)

    assert app.session_state["yield_stress_mpa"] == 205.0
    assert app.session_state["youngs_modulus_gpa"] == 193.0

    app.number_input(key="youngs_modulus_gpa").set_value(180.0)
    app.run(timeout=15)
    assert app.session_state["material_property_sources"]["youngs_modulus_gpa"] == "user"
    assert any("User-entered: Young's modulus E" in item.value for item in app.caption)

    app.selectbox(key="material_selector").set_value("Structural Steel")
    app.run(timeout=15)
    assert app.session_state["youngs_modulus_gpa"] == 205.0
    assert app.session_state["yield_stress_mpa"] == 275.0

    app.selectbox(key="material_selector").set_value("Aluminium Alloy 6061-T6")
    app.run(timeout=15)
    assert app.session_state["youngs_modulus_gpa"] == 68.9
    assert app.session_state["yield_stress_mpa"] is None
    assert app.session_state["material_property_sources"]["yield_stress_mpa"] == "unavailable"


def test_copper_selection_does_not_infer_unverified_properties() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)
    app.selectbox(key="material_selector").set_value("Copper")
    app.run(timeout=15)

    assert app.number_input(key="youngs_modulus_gpa").value is None
    assert app.session_state["yield_stress_mpa"] is None
    assert app.session_state["material_property_sources"]["youngs_modulus_gpa"] == "unavailable"
    assert "material_grade_selector" not in app.session_state


def test_missing_theory_inputs_are_reported_in_one_compact_message() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=15)

    missing_input_messages = [
        item.value
        for item in app.info
        if item.value.startswith("The following theory predictions need additional inputs")
    ]
    assert len(missing_input_messages) == 1
    assert "compressive/crushing strength sigma_c" in missing_input_messages[0]
    assert "Rankine constant a" in missing_input_messages[0]
    assert "yield stress sigma_y" not in missing_input_messages[0]


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
    app.number_input(key="diameter_mm").set_value(20.0)
    app.number_input(key="column_length_mm").set_value(50.0)
    app.run(timeout=15)
    app = _calculate(app)

    metrics = _metric_values(app)
    assert metrics["Slenderness ratio Le/k"] == "10"
    assert any("Recommended Theory" in item.value for item in app.subheader)
    assert any("Insufficient information to recommend" in item.value for item in app.info)

    app.number_input(key="column_length_mm").set_value(500.0)
    app.run(timeout=15)
    app = _calculate(app)
    assert _metric_values(app)["Slenderness ratio Le/k"] == "100"
    assert any("Recommended theory: Johnson" in item.value for item in app.success)

    app.number_input(key="column_length_mm").set_value(1000.0)
    app.run(timeout=15)
    app = _calculate(app)
    assert _metric_values(app)["Slenderness ratio Le/k"] == "200"
    assert any("Recommended theory: Euler" in item.value for item in app.success)