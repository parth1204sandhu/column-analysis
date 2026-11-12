import json
from pathlib import Path

import pytest

from column_analysis.materials import create_custom_material, load_material_database


DATABASE_PATH = Path(__file__).resolve().parents[1] / "column_analysis" / "materials.json"
EXPECTED_PROPERTY_UNITS = {
    "youngs_modulus_gpa": "GPa",
    "compressive_strength_mpa": "MPa",
    "yield_stress_mpa": "MPa",
    "rankine_constant_dimensionless": "dimensionless",
}
EXPECTED_NAMES = (
    "Generic Softwood",
    "Generic Hardwood",
    "Cast Iron",
    "Brass",
    "Bronze",
    "Copper",
    "Aluminium",
    "Stainless Steel",
    "Structural Steel",
)


def test_material_database_contains_standard_materials_in_display_order() -> None:
    database = json.loads(DATABASE_PATH.read_text(encoding="utf-8"))
    materials = load_material_database()

    assert database["schema_version"] == 2
    assert tuple(material.display_name for material in materials.values()) == EXPECTED_NAMES
    assert len(materials) == len(EXPECTED_NAMES)


def test_every_material_record_has_a_unique_identifier_without_grade_subcategories() -> None:
    database = json.loads(DATABASE_PATH.read_text(encoding="utf-8"))
    identifiers = [record["id"] for record in database["materials"]]
    materials = load_material_database()

    assert len(identifiers) == len(set(identifiers)) == len(EXPECTED_NAMES)
    assert set(identifiers) == set(materials)
    assert all("grade" not in record for record in database["materials"])
    assert all(material.grade is None for material in materials.values())


def test_material_properties_have_valid_units_and_references() -> None:
    for material in load_material_database().values():
        assert material.notes.strip()
        assert set(material.properties) == set(EXPECTED_PROPERTY_UNITS)

        for property_name, property_value in material.properties.items():
            assert property_value.unit == EXPECTED_PROPERTY_UNITS[property_name]
            assert property_value.notes.strip()
            if property_value.value is not None:
                assert property_value.value > 0
                assert property_value.source
                assert property_value.source_url.startswith("https://")
            else:
                assert property_value.source is None
                assert property_value.source_url is None


def test_generic_elastic_moduli_are_documented_representatives() -> None:
    materials = load_material_database()
    expected_moduli_gpa = {
        "generic-softwood": 11.1,
        "generic-hardwood": 11.7,
        "cast-iron": 130.0,
        "brass": 113.5,
        "bronze": 108.0,
        "copper": 117.0,
        "aluminium": 69.0,
        "stainless-steel": 193.0,
        "structural-steel": 200.0,
    }

    for material_id, expected_value in expected_moduli_gpa.items():
        property_value = materials[material_id].properties["youngs_modulus_gpa"]
        assert property_value.value == pytest.approx(expected_value)
        assert property_value.source
        assert property_value.source_url.startswith("https://")


def test_wood_compression_properties_are_parallel_to_grain_and_limited() -> None:
    materials = load_material_database()

    assert materials["generic-softwood"].properties["compressive_strength_mpa"].value == 41.2
    assert materials["generic-hardwood"].properties["compressive_strength_mpa"].value == 51.2
    for material_id in ("generic-softwood", "generic-hardwood"):
        material = materials[material_id]
        assert "parallel to grain" in material.notes
        assert "perpendicular-to-grain" in material.notes
        assert "parallel to grain" in material.properties[
            "compressive_strength_mpa"
        ].notes


def test_yield_and_rankine_values_are_not_assumed_for_generic_materials() -> None:
    materials = load_material_database()

    for material in materials.values():
        assert material.properties["yield_stress_mpa"].value is None
        assert material.properties["rankine_constant_dimensionless"].value is None

    cast_iron = materials["cast-iron"]
    assert cast_iron.properties["compressive_strength_mpa"].value is None
    assert "not modeled as a ductile material" in cast_iron.properties[
        "yield_stress_mpa"
    ].notes


def test_unavailable_properties_have_explanatory_notes() -> None:
    for material in load_material_database().values():
        for property_value in material.properties.values():
            if property_value.value is None:
                assert property_value.notes
                assert (
                    "not" in property_value.notes.lower()
                    or "no " in property_value.notes.lower()
                )


def test_custom_material_uses_the_standard_property_interface_and_optional_values() -> None:
    material = create_custom_material(
        "  Test alloy  ",
        youngs_modulus_gpa=70.0,
        yield_stress_mpa=250.0,
    )

    assert material.material_id == "custom-material"
    assert material.display_name == "Test alloy"
    assert material.properties["youngs_modulus_gpa"].value == 70.0
    assert material.properties["yield_stress_mpa"].value == 250.0
    assert material.properties["compressive_strength_mpa"].value is None
    assert material.properties["rankine_constant_dimensionless"].value is None
    assert material.properties["yield_stress_mpa"].source == "User-entered"


def test_custom_material_accepts_modulus_at_broad_screening_ceiling() -> None:
    material = create_custom_material(
        "High modulus material",
        youngs_modulus_gpa=2000.0,
    )

    assert material.properties["youngs_modulus_gpa"].value == 2000.0


@pytest.mark.parametrize(
    ("name", "youngs_modulus_gpa", "optional_values"),
    [
        ("  ", 70.0, {}),
        ("Test", None, {}),
        ("Test", 0.0, {}),
        ("Test", 1e6, {}),
        ("Test", float("nan"), {}),
        ("Test", True, {}),
        ("Test", 70.0, {"yield_stress_mpa": 0.0}),
        ("Test", 70.0, {"compressive_strength_mpa": float("inf")}),
        ("Test", 70.0, {"rankine_constant_dimensionless": -0.1}),
    ],
)
def test_custom_material_rejects_invalid_values(
    name: str,
    youngs_modulus_gpa: float | None,
    optional_values: dict[str, float],
) -> None:
    with pytest.raises(ValueError):
        create_custom_material(
            name,
            youngs_modulus_gpa=youngs_modulus_gpa,
            **optional_values,
        )
