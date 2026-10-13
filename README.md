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


