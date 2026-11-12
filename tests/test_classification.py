import json
from pathlib import Path

import pytest

from column_analysis.classification import (
    ColumnClass,
    classify_column,
    load_column_classification_criteria,
)


_CRITERIA_PATH = Path(__file__).resolve().parents[1] / "column_analysis" / "classification_criteria.json"
_CRITERIA = load_column_classification_criteria()
_E_PA = 200e9
_YIELD_PA = 250e6
_SHORT_BOUNDARY = 3.141592653589793 * (_E_PA / _YIELD_PA) ** 0.5
_INTERMEDIATE_BOUNDARY = (2 * 3.141592653589793**2 * _E_PA / _YIELD_PA) ** 0.5


@pytest.mark.parametrize(
    ("slenderness_ratio", "expected_class"),
    [
        (1.0, ColumnClass.SHORT),
        (_SHORT_BOUNDARY, ColumnClass.SHORT),
        (_SHORT_BOUNDARY + 1e-8, ColumnClass.INTERMEDIATE),
        (_INTERMEDIATE_BOUNDARY, ColumnClass.INTERMEDIATE),
        (_INTERMEDIATE_BOUNDARY + 1e-8, ColumnClass.LONG),
    ],
)
def test_material_dependent_classification_and_exact_boundaries(
    slenderness_ratio: float,
    expected_class: ColumnClass,
) -> None:
    result = classify_column(
        slenderness_ratio,
        _CRITERIA,
        youngs_modulus_pa=_E_PA,
        yield_stress_pa=_YIELD_PA,
    )

    assert result.classification is expected_class
    assert result.slenderness_ratio == pytest.approx(slenderness_ratio)
    assert result.short_max_slenderness_ratio == pytest.approx(_SHORT_BOUNDARY)
    assert result.intermediate_max_slenderness_ratio == pytest.approx(
        _INTERMEDIATE_BOUNDARY
    )
    assert result.reference_url == "https://mechanicalc.com/reference/column-buckling"
    assert result.explanation


def test_classification_limits_change_with_material_properties() -> None:
    steel = classify_column(
        95.0,
        _CRITERIA,
        youngs_modulus_pa=205e9,
        yield_stress_pa=275e6,
    )
    stainless = classify_column(
        95.0,
        _CRITERIA,
        youngs_modulus_pa=193e9,
        yield_stress_pa=205e6,
    )

    assert steel.classification is ColumnClass.INTERMEDIATE
    assert stainless.classification is ColumnClass.SHORT
    assert steel.short_max_slenderness_ratio != stainless.short_max_slenderness_ratio


@pytest.mark.parametrize(
    ("slenderness_ratio", "youngs_modulus_pa", "yield_stress_pa", "message"),
    [
        (None, _E_PA, _YIELD_PA, "slenderness ratio"),
        (40.0, None, _YIELD_PA, "Young's modulus"),
        (40.0, _E_PA, None, "yield stress"),
        (40.0, 0.0, _YIELD_PA, "Young's modulus"),
        (40.0, _E_PA, float("nan"), "yield stress"),
    ],
)
def test_missing_or_invalid_inputs_report_classification_unavailable(
    slenderness_ratio: float | None,
    youngs_modulus_pa: float | None,
    yield_stress_pa: float | None,
    message: str,
) -> None:
    result = classify_column(
        slenderness_ratio,
        _CRITERIA,
        youngs_modulus_pa=youngs_modulus_pa,
        yield_stress_pa=yield_stress_pa,
    )

    assert result.classification is None
    assert message in result.explanation


@pytest.mark.parametrize(
    ("key", "invalid_value"),
    [
        ("short_boundary", {"equation": "x", "derivation": "x", "euler_stress_to_yield_ratio": 0.5}),
        ("intermediate_upper_boundary", {"equation": "x", "derivation": "x", "euler_stress_to_yield_ratio": 2.0}),
    ],
)
def test_configuration_rejects_reversed_or_invalid_material_boundary_ratios(
    tmp_path,
    monkeypatch,
    key: str,
    invalid_value: dict[str, object],
) -> None:
    from column_analysis import classification

    data = json.loads(_CRITERIA_PATH.read_text(encoding="utf-8"))
    data[key] = invalid_value
    path = tmp_path / "classification.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(classification, "_CLASSIFICATION_PATH", path)

    with pytest.raises(ValueError):
        load_column_classification_criteria()
