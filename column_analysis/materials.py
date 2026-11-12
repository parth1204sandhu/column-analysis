"""Typed access to the local material-property reference database."""

import json
from dataclasses import dataclass
from math import isfinite
from pathlib import Path


_DATABASE_PATH = Path(__file__).with_name("materials.json")
_PROPERTY_UNITS = {
    "youngs_modulus_gpa": "GPa",
    "compressive_strength_mpa": "MPa",
    "yield_stress_mpa": "MPa",
    "rankine_constant_dimensionless": "dimensionless",
}


@dataclass(frozen=True)
class MaterialProperty:
    """A property value and the reference or reason it is unavailable."""

    value: float | None
    unit: str
    source: str | None
    source_url: str | None
    notes: str


@dataclass(frozen=True)
class MaterialGrade:
    """Material identity, grade notes, and its available property data."""

    material_id: str
    material: str
    grade: str
    notes: str
    properties: dict[str, MaterialProperty]

    @property
    def display_name(self) -> str:
        """Return the single material name shown in the selector."""
        return self.material


def load_material_database() -> dict[str, MaterialGrade]:
    """Load and validate the versioned local material database."""
    data = json.loads(_DATABASE_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError(f"{_DATABASE_PATH} must use material database schema version 1.")

    entries = data.get("materials")
    if not isinstance(entries, list):
        raise ValueError(f"{_DATABASE_PATH} must contain a materials list.")
    expected_names = {
        "Structural Steel",
        "Stainless Steel",
        "Aluminium Alloy 6061-T6",
        "Copper",
    }
    if len(entries) != len(expected_names):
        raise ValueError("The material database must contain exactly four materials.")

    materials: dict[str, MaterialGrade] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Each material database entry must be an object.")

        material_id = entry.get("id")
        for field in ("id", "material", "grade", "notes"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise ValueError(f"Each material entry must have a non-empty {field!r}.")
        if material_id in materials:
            raise ValueError(f"Duplicate material id {material_id!r}.")

        raw_properties = entry.get("properties")
        if not isinstance(raw_properties, dict) or set(raw_properties) != set(_PROPERTY_UNITS):
            raise ValueError(
                f"Material {material_id!r} must define exactly: "
                f"{', '.join(_PROPERTY_UNITS)}."
            )

        properties: dict[str, MaterialProperty] = {}
        for name, expected_unit in _PROPERTY_UNITS.items():
            raw_property = raw_properties[name]
            if not isinstance(raw_property, dict):
                raise ValueError(f"Property {name!r} for {material_id!r} must be an object.")

            value = raw_property.get("value")
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
                or value <= 0
            ):
                raise ValueError(
                    f"Property {name!r} for {material_id!r} must be positive and finite or null."
                )
            if raw_property.get("unit") != expected_unit:
                raise ValueError(
                    f"Property {name!r} for {material_id!r} must use {expected_unit!r}."
                )

            source = raw_property.get("source")
            source_url = raw_property.get("source_url")
            if (source is None) != (source_url is None):
                raise ValueError(
                    f"Property {name!r} for {material_id!r} must provide both source and source_url, or neither."
                )
            if source is not None and (
                not isinstance(source, str)
                or not source.strip()
                or not isinstance(source_url, str)
                or not source_url.startswith("https://")
            ):
                raise ValueError(
                    f"Property {name!r} for {material_id!r} has an invalid source reference."
                )
            if value is not None and source is None:
                raise ValueError(
                    f"Property {name!r} for {material_id!r} needs a source when a value is available."
                )
            notes = raw_property.get("notes")
            if not isinstance(notes, str) or not notes.strip():
                raise ValueError(f"Property {name!r} for {material_id!r} needs notes.")

            properties[name] = MaterialProperty(
                value=float(value) if value is not None else None,
                unit=expected_unit,
                source=source,
                source_url=source_url,
                notes=notes,
            )

        materials[material_id] = MaterialGrade(
            material_id=material_id,
            material=entry["material"],
            grade=entry["grade"],
            notes=entry["notes"],
            properties=properties,
        )

    display_names = [material.display_name for material in materials.values()]
    if len(display_names) != len(set(display_names)):
        raise ValueError("Material display names must be unique.")
    if set(display_names) != expected_names:
        raise ValueError(
            "The material database must contain Structural Steel, Stainless Steel, "
            "Aluminium Alloy 6061-T6, and Copper."
        )

    return materials
