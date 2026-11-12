import json
from pathlib import Path

from column_analysis.materials import load_material_database


DATABASE_PATH = Path(__file__).resolve().parents[1] / "column_analysis" / "materials.json"
EXPECTED_PROPERTY_UNITS = {
    "youngs_modulus_gpa": "GPa",
    "compressive_strength_mpa": "MPa",
    "yield_stress_mpa": "MPa",
    "rankine_constant_dimensionless": "dimensionless",
}
EXPECTED_NAMES = {
    "Structural Steel",
    "Stainless Steel",
    "Aluminium Alloy 6061-T6",
    "Copper",
}


def test_material_database_contains_exactly_the_four_requested_materials() -> None:
    materials = load_material_database()

    assert len(materials) == 4
    assert {material.display_name for material in materials.values()} == EXPECTED_NAMES


def test_every_material_record_has_a_unique_identifier() -> None:
    database = json.loads(DATABASE_PATH.read_text(encoding="utf-8"))
    identifiers = [record["id"] for record in database["materials"]]
    display_names = [material.display_name for material in load_material_database().values()]

    assert len(identifiers) == len(set(identifiers)) == 4
    assert set(identifiers) == set(load_material_database())
    assert len(display_names) == len(set(display_names)) == 4


def test_material_properties_have_valid_units_and_references() -> None:
    for material in load_material_database().values():
        assert material.grade.strip()
        assert material.notes.strip()
        assert set(material.properties) == set(EXPECTED_PROPERTY_UNITS)

        for property_name, property_value in material.properties.items():
            assert property_value.unit == EXPECTED_PROPERTY_UNITS[property_name]
            assert property_value.notes.strip()
            if property_value.value is not None:
                assert property_value.value > 0
                assert property_value.source
                assert property_value.source_url.startswith("https://")


def test_supported_strength_values_are_condition_specific_and_missing_values_stay_blank() -> None:
    materials = load_material_database()

    assert materials["structural-steel-s275"].properties["yield_stress_mpa"].value == 275.0
    assert materials["stainless-steel-304-annealed"].properties["yield_stress_mpa"].value == 205.0
    assert materials["aluminium-6061-t6"].properties["youngs_modulus_gpa"].value == 68.9
    assert materials["aluminium-6061-t6"].properties["yield_stress_mpa"].value is None
    assert materials["copper-c11000"].properties["yield_stress_mpa"].value is None

    for material in materials.values():
        assert material.properties["compressive_strength_mpa"].value is None
        assert material.properties["rankine_constant_dimensionless"].value is None


def test_unavailable_properties_have_explanatory_notes() -> None:
    for material in load_material_database().values():
        for property_value in material.properties.values():
            if property_value.value is None:
                assert property_value.notes
                assert (
                    "obtain" in property_value.notes.lower()
                    or "not" in property_value.notes.lower()
                    or "no " in property_value.notes.lower()
                )
