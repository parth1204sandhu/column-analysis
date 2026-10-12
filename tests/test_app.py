from pathlib import Path

from streamlit.testing.v1 import AppTest


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


def test_missing_rankine_and_johnson_inputs_are_not_calculated() -> None:
    app = _app_with_circle()
    app.checkbox(key="include_rankine").set_value(True)
    app.checkbox(key="include_johnson").set_value(True)
    app.run(timeout=15)
    app = _calculate(app)

    rows = _comparison_rows(app)
    assert rows["Rankine"]["Critical load (kN)"] == "Not calculated"
    assert "Not calculated — missing required input" in rows["Rankine"]["Calculation status"]
    assert rows["Johnson"]["Critical load (kN)"] == "Not calculated"
    assert "Not calculated — missing required input" in rows["Johnson"]["Calculation status"]


def test_invalid_youngs_modulus_does_not_produce_theory_loads() -> None:
    app = _app_with_circle(youngs_modulus_gpa=0.0)
    app.checkbox(key="include_johnson").set_value(True)
    app.run(timeout=15)
    app.number_input(key="yield_stress_mpa").set_value(250.0)
    app.run(timeout=15)
    app = _calculate(app)

    rows = _comparison_rows(app)
    assert rows["Euler"]["Critical load (kN)"] == "Not calculated"
    assert "Not calculated — invalid input" in rows["Euler"]["Calculation status"]
    assert rows["Johnson"]["Critical load (kN)"] == "Not calculated"
    assert "Not calculated — invalid input" in rows["Johnson"]["Calculation status"]


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