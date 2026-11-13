# Column Analysis Studio

A Python-based engineering application for analysing columns under axial compression.

Features

- 8 cross-sections: Circular, rectangular, hollow, I, C, L and T sections.
- Material database: Steel, aluminium, cast iron, copper, brass, bronze and wood.
- Custom materials: Enter your own mechanical properties.
- End conditions: Calculate effective column length.
- Section properties: Area, centroid, moments of inertia and radius of gyration.
- Buckling analysis: Euler, Rankine–Gordon and Johnson theories.
- Results: Theory comparison, recommendations, graphs and load assessment.

Formulas

Effective length:

"Le = K × L"

Radius of gyration:

"k = √(Imin / A)"

Slenderness ratio:

"λ = Le / k"

Critical buckling load:

- Euler: "P = π²EImin / Le²"
- Rankine: "P = σcA / (1 + aλ²)"
- Johnson: "P = Aσy(1 − σyλ² / 4π²E)"

Technology

- Python
- Streamlit
- NumPy
- Pandas
- Matplotlib

Run Locally

Clone the repository:

git clone YOUR_REPOSITORY_URL
cd column-analysis

Create a virtual environment and install dependencies:

python -m venv .venv

pip install -r requirements.txt

Launch the application:

streamlit run app.py

Limitations

This is an educational analysis tool based on idealized flexural buckling. It does not perform complete design-code checks or account for all real-world imperfections, eccentric loading, torsional buckling or flexural-torsional buckling.

Purpose

Developed as a Mechanical Engineering project to explore column stability, cross-sectional properties and classical buckling theories.