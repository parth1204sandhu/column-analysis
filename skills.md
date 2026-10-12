# skills.md --- Project Skills and Engineering Rules

This file defines the technical skills, conventions, and boundaries for
the Column Analysis and Comparison Tool. Read it before implementing or
modifying the project.

## 1. Project objective

Build an educational Python/Streamlit tool for concentric axial loading
of columns, restricted to the column topics in ME-211 Mechanics of
Solids, Unit 04.

## 2. Required engineering topics

Use only these syllabus topics:

-   Types and failure of columns
-   Euler's column theory
-   Slenderness ratio
-   End conditions and equivalent length
-   Limitations of Euler's formula
-   Factor of safety
-   Rankine's straight-line / Rankine-Gordon formula
-   Johnson's parabolic formula

Do not add unrelated failure theories or present a separate
crushing-theory model in the comparison. Rankine's equation may use a
crushing-strength input as part of its formula.

## 3. Programming stack

-   Python 3.10+
-   Streamlit
-   NumPy
-   Pandas
-   Plotly or Matplotlib
-   pytest

Prefer standard-library features when adequate. Do not add dependencies
without a clear reason.

## 4. Architecture skills

Keep responsibilities separated:

-   `app.py`: Streamlit UI and page flow only
-   `column_analysis/sections.py`: geometry and section properties
-   `column_analysis/properties.py`: effective length, radius of
    gyration, slenderness ratio
-   `column_analysis/theories.py`: pure functions for Euler, Rankine,
    and Johnson
-   `column_analysis/validation.py`: input validation and applicability
    checks
-   `column_analysis/reporting.py`: optional report formatting/export
-   `tests/`: unit tests for calculations and edge cases

Calculation functions should accept explicit inputs and return numeric
results or structured result objects. They should not read Streamlit
widgets, print output, or mutate global state.

## 5. Units and numeric conventions

-   Use SI units internally: m, m², m⁴, Pa, N, kg/m³ if density is later
    needed.
-   UI may accept mm, mm²-related dimensions, and MPa, but convert once
    at the boundary.
-   Use descriptive variable names with units in comments/docstrings
    where ambiguity is possible.
-   Display loads in N or kN, stress/modulus in Pa or MPa, dimensions in
    mm or m, and clearly label every displayed unit.
-   Do not mix mm and m in a formula.
-   Use floating-point arithmetic; avoid unnecessary rounding until
    display time.

## 6. Column geometry

Support geometry only when formulas are correctly implemented and
tested.

Minimum recommended first version: - Solid circular section -
Rectangular section

Optional after core validation: - Hollow circular section

For non-symmetric sections, calculate both principal second moments of
area and use the smaller relevant value for buckling about the weaker
axis. For a rectangular section, do not assume the stronger axis is the
only buckling axis.

Common properties: - Area `A` - Second moment of area about each
relevant axis `I` - Least second moment of area `I_min` - Least radius
of gyration `k_min = sqrt(I_min / A)`

## 7. End conditions and effective length

Provide these idealized end conditions, with factors clearly labelled as
approximations:

-   Pinned-pinned: K = 1.0
-   Fixed-fixed: K = 0.5
-   Fixed-free (cantilever): K = 2.0
-   Fixed-pinned: K ≈ 0.699

Use `Le = K * L`.

Do not imply real supports always behave exactly like ideal supports.
Explain that restraint assumptions affect results.

## 8. Theory implementation

### Euler

`P_E = pi² * E * I_min / Le²`

Requirements: - Use the least second moment of area. - Require positive
`E`, `I_min`, and `Le`. - Flag that Euler applies to sufficiently
slender, elastic columns and has limitations.

### Rankine-Gordon

A commonly used form is:

`P_R = sigma_c * A / (1 + a * (Le / k_min)²)`

where `sigma_c` is the selected crushing/compressive strength and `a` is
an empirical Rankine constant whose value and unit convention depend on
the reference/formulation.

Requirements: - Do not invent a universal value for `a`. - Ask for or
clearly document the empirical constant and its convention. - Use
consistent units. - Show the selected values and assumptions.

### Johnson parabolic formula

A commonly used form is:

`P_J = A * sigma_y * (1 - (sigma_y / (4 * pi² * E)) * (Le / k_min)²)`

where `sigma_y` is the relevant yield/compressive stress as defined by
the course reference.

Requirements: - Implement only after confirming the exact form and
definitions expected in the course notes. - Check the
slenderness/applicability range using a clearly documented criterion. -
Do not show a negative Johnson load as a meaningful physical capacity. -
If the result is outside the supported range, flag it rather than
presenting it as a valid prediction.

## 9. Classification and applicability

-   Do not use an arbitrary universal length to classify a column as
    short, intermediate, or long.
-   Compute and display slenderness ratio.
-   Implement classification only using a criterion from the user's
    course notes/textbook or a clearly labelled configurable criterion.
-   Show the applicable theory/range and explain why.
-   Where no course criterion has been provided, ask the user for the
    formula/range or label classification as provisional.

## 10. Factor of safety

-   Use `allowable_load = critical_load / factor_of_safety` only when
    the selected theory/result is applicable and the factor of safety is
    positive.
-   Validate factor of safety `> 0`; if the course requires a different
    convention, follow that convention.
-   Label critical load, allowable load, and applied load separately.
-   Do not claim a design is safe unless the comparison and assumptions
    justify that statement.

## 11. Testing

Use pytest. Include: - Normal valid cases - Invalid dimensions/material
properties - Unit-conversion checks - End-condition effective-length
checks - Geometry property checks - Theory formula checks against
hand-calculated examples - Applicability-boundary checks - Zero/negative
input rejection

Tests should use known expected values derived independently, not simply
call the same function twice.

## 12. UI and usability

-   Keep the interface understandable to a Mechanical Engineering
    student.
-   Group inputs into Geometry, Material, Loading, and End Conditions.
-   Display formulas and substituted values.
-   Use comparison tables and clearly labelled graphs.
-   Do not overwhelm the user with every parameter at once.
-   Provide a sample/example mode with all assumptions labelled.
-   Show validation errors next to relevant inputs.

## 13. General coding rules

-   Use type hints for calculation functions.
-   Add docstrings to public functions.
-   Use descriptive names.
-   Keep functions small and testable.
-   Catch expected input errors and explain them to the user.
-   Do not silently replace invalid inputs with defaults.
-   Do not hard-code material properties without labelling them as
    examples.
-   Do not claim a feature is complete until tested.
