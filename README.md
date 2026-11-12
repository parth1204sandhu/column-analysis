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

The Results area includes a deterministic **Recommended Theory** assessment. The local, editable `column_analysis/applicability_criteria.json` stores explicit range criteria and their references. The Euler/Johnson transition follows the cited condition that Euler critical stress equals half the yield strength, giving `Cc = sqrt(2*pi^2*E/sigma_y)`. This is a material-dependent transition, not a universal numeric slenderness cutoff. Euler is considered above `Cc`; the classical Johnson formula is considered in its configured theoretical range `0 < lambda < Cc`. The configured lower limit of zero is only the mathematical limit of the formula, not a validated short-column cutoff or confirmation that crushing cannot govern. Very low slenderness may be crushing-dominated, and no numerical crossover is claimed. When a verified compressive/crushing strength is entered, the Results area separately compares applied load with the theoretical squash load `sigma_c * A`; this is not Rankine-Gordon and is not a certified design check. Rankine-Gordon is not recommended until its referenced range and matching empirical constant are configured. Formula predictions are calculated separately from applicability; the comparison table reports both and includes the reason for each applicability decision.

The Johnson range citation documents the classical intermediate-column criterion and its Euler transition; it does not supply a separate numerical short-column boundary. The zero lower limit therefore documents the formula's mathematical domain only. Below any positive lower bound configured locally, the recommendation reports the short-column/crushing-dominated region rather than forcing Johnson or Euler.

The three individual critical-load graphs use their own theory formulas, show the current slenderness, and distinguish formula predictions from applicability. The Applied Load Assessment compares applied load, critical load, and (when entered) theoretical allowable load only for theories whose applicability is confirmed. An allowable load is calculated as critical load divided by the user-entered factor of safety; these are educational, theoretical comparisons—not certified design checks.

To configure a different Johnson lower slenderness bound, provide the bound and its source in that JSON file. To configure Rankine-Gordon, provide both range bounds, the sourced dimensionless constant for the exact equation shown above, and its reference. If configured ranges overlap, `preferred_theory_order` must resolve that overlap; otherwise the app reports the candidates without selecting one.

For a solid circular column with diameter 50 mm, length 3000 mm, E = 200 GPa, and pinned-pinned ends, `I = pi*0.05^4/64 = 3.06796e-7 m^4`, `Le = 3 m`, and Euler gives `67.2879 kN`. Thus 67.288 kN is consistent with the stated inputs; 44.8 kN is not.

## Material properties

The Material Properties selector contains exactly **Structural Steel**, **Stainless Steel**, **Aluminium Alloy 6061-T6**, and **Copper**. The first material is selected initially and each selection populates the properties supported by its references. Property sources, product conditions, and limitations are available in an expandable reference section. Unverified values remain blank; in particular, tensile yield strength is not treated as compressive/crushing strength, and no Rankine constant is inferred. Euler, Johnson, and Rankine-Gordon predictions are calculated whenever their required valid inputs are available; Rankine requires manually supplied, sourced compressive strength and constant.

The versioned database is `column_analysis/materials.json`; its typed loader and schema validation are in `column_analysis/materials.py`. Verify referenced values against the actual supplied material condition and applicable course/reference before using them.

## How it is made

Python 3.10+ and Streamlit build the interface. Plotly displays the graphs, and pytest runs the tests. The UI is in `app.py`; calculation code is kept in `column_analysis/` and tested separately in `tests/`. Inputs are converted to SI units for calculations. The app currently supports solid circular and rectangular sections.

## Run it

In Windows PowerShell, from the project folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit, usually `http://localhost:8501`. Run tests with `python -m pytest`.
