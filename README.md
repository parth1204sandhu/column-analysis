# Column Analysis Studio

This app estimates and compares the buckling loads of columns under axial compression. It calculates column properties and shows how the result changes with the column's slenderness. It is an educational tool, not a substitute for engineering review.

## Theories and formulas

The app uses Euler, Rankine-Gordon, and Johnson's parabolic theory. The effective length and slenderness are:

- `Le = K * L`
- `k = sqrt(I_min / A)`
- `lambda = Le / k`

Critical-load formulas:

- Euler: `P = pi^2 * E * I_min / Le^2`
- Rankine-Gordon: `P = sigma_c * A / (1 + a * (Le / k)^2)`
- Johnson: `P = A * sigma_y * (1 - (sigma_y / (4 * pi^2 * E)) * (Le / k)^2)`

Here, `A` is area, `I_min` is the weaker-axis second moment of area, `E` is Young's modulus, and `K` depends on the end supports. Enter the Rankine constant and material strengths from your course or reference; the app does not assume them. Theory applicability is not confirmed without course-specific criteria.

Rankine-Gordon uses the dimensionless-constant convention shown above. A constant taken from a different notation or equation must not be copied without an explicit conversion.

## Section axes and analysis scope

Section coordinates use x horizontally to the right and y vertically upward, with centroid coordinates measured from the lower-left of the section's bounding box. The product of inertia is `Ixy = integral((x - xbar) * (y - ybar) dA)`. Principal second moments are `(Ixx + Iyy)/2 ± sqrt(((Ixx - Iyy)/2)^2 + Ixy^2)`; the smaller principal value is used as `I_min` for flexural buckling.

The column calculations represent idealized flexural buckling. Torsional and flexural-torsional buckling are not calculated, which is an important limitation for open sections; this is not a complete stability analysis.


## Column classification

The Results section separately screens columns as **Short**, **Intermediate**, or **Long** using `lambda = Le / k`, where `k = sqrt(I_min / A)`. Material-dependent boundaries are configured in `column_analysis/classification_criteria.json`:

- Short upper limit: `lambda_s = pi * sqrt(E / sigma_y)`, obtained by setting the ideal Euler elastic critical stress `pi^2 * E / lambda^2` equal to yield stress.
- Intermediate upper limit: `lambda_i = sqrt(2 * pi^2 * E / sigma_y)`, the classical Johnson/Euler curve transition where Euler critical stress equals half the yield stress.
- Short: `0 < lambda <= lambda_s`; Intermediate: `lambda_s < lambda <= lambda_i`; Long: `lambda > lambda_i`.

These are material-dependent educational screening bands, not universal class limits or a code design classification. They require valid E and yield stress for the selected condition. The configured assumption that yield stress represents the compressive yield limit is used only for this idealized classification screen; it is not represented as measured compressive/crushing strength and is not used to calculate squash capacity. If E or yield stress is unavailable/invalid, classification is reported as unavailable. The classification remains separate from the Euler/Johnson/Rankine recommendation; the same transition expression is not treated as a universal slenderness cutoff.

The Results area includes a deterministic **Recommended Theory** assessment. The local, editable `column_analysis/applicability_criteria.json` stores explicit range criteria and their references. The Euler/Johnson transition follows the cited condition that Euler critical stress equals half the yield strength, giving `Cc = sqrt(2*pi^2*E/sigma_y)`. This is a material-dependent transition, not a universal numeric slenderness cutoff. Euler is considered above `Cc`; Johnson's formula is mathematically defined for `0 < lambda < Cc`, but the app does not recommend it within the configured short-column screening range. The lower recommendation bound is aligned with the material-dependent classification screen; the classification and theory recommendation remain distinct assessments. When a verified compressive/crushing strength is entered, the Results area separately compares applied load with the theoretical squash load `sigma_c * A`; this is not Rankine-Gordon and is not a certified design check. Rankine-Gordon is not recommended until its referenced range and matching empirical constant are configured. Formula predictions are calculated separately from applicability; the comparison table reports both and includes the reason for each applicability decision.

The Johnson range citation documents the classical intermediate-column criterion and its Euler transition; it does not supply a universal numerical short-column boundary. The configured zero lower limit in `applicability_criteria.json` describes the formula's mathematical domain only. The classification configuration provides a separate material-dependent short-column screen; below that limit, Johnson is not recommended and the result identifies crushing-dominated behavior.

The three individual critical-load graphs use their own theory formulas, show the current slenderness, and distinguish formula predictions from applicability. The Applied Load Assessment compares applied load, critical load, and (when entered) theoretical allowable load only for theories whose applicability is confirmed. An allowable load is calculated as critical load divided by the user-entered factor of safety; these are educational, theoretical comparisons—not certified design checks.

To configure a different Johnson lower slenderness bound, provide the bound and its source in that JSON file. To configure Rankine-Gordon, provide both range bounds, the sourced dimensionless constant for the exact equation shown above, and its reference. If configured ranges overlap, `preferred_theory_order` must resolve that overlap; otherwise the app reports the candidates without selecting one.

For a solid circular column with diameter 50 mm, length 3000 mm, E = 200 GPa, and pinned-pinned ends, `I = pi*0.05^4/64 = 3.06796e-7 m^4`, `Le = 3 m`, and Euler gives `67.2879 kN`. Thus 67.288 kN is consistent with the stated inputs; 44.8 kN is not.

## Material properties

The Material selector contains **Generic Softwood**, **Generic Hardwood**, **Cast Iron**, **Brass**, **Bronze**, **Copper**, **Aluminium**, **Stainless Steel**, **Structural Steel**, and **Custom Material**. The four material-property fields are editable for every selection. Known standard-material values are prefilled from the database, while unavailable values remain blank; selecting a standard material reloads its database values. Edits are session-only and never overwrite the database. Wood values are longitudinal (parallel to grain) representatives; perpendicular-to-grain behavior and full timber design checks are not implemented. Generic cast iron has no assumed ductile yield strength. Custom Material accepts a name and Young's modulus, with yield strength, compressive/crushing strength, and Rankine constant optional. Missing values are never inferred; Johnson requires a suitable yield strength, and Rankine requires its inputs and configured applicability criteria.

The versioned database is `column_analysis/materials.json`; its typed loader and schema validation are in `column_analysis/materials.py`. Verify referenced values against the actual supplied material condition and applicable course/reference before using them.

Young's modulus inputs must be finite and greater than zero, and are screened at a broad upper limit of 2,000 GPa to catch likely unit-entry errors. This ceiling is above the tabulated values for diamond (1,220 GPa) and single-walled carbon nanotubes (1,000 GPa); it is not a universal material limit ([Engineering ToolBox reference table](https://www.engineeringtoolbox.com/young-modulus-d_417.html)). Factors of safety must be greater than 1.0 for the app's conventional allowable-load calculation.

## How it is made

Python 3.10+ and Streamlit build the interface. Plotly displays the graphs, and pytest runs the tests. The UI is in `app.py`; calculation code is kept in `column_analysis/` and tested separately in `tests/`. Inputs are converted to SI units for calculations. The app supports solid and hollow circular/rectangular, I-, channel-, angle-, and T-sections.

## Run it

In Windows PowerShell, from the project folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit, usually `http://localhost:8501`. Run tests with `python -m pytest`.
