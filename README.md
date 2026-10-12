# Column Analysis and Comparison Tool

A Python application for analysing columns under concentric axial
loading using the column theories included in the **Mechanics of Solids
(ME-211), Unit 04** syllabus.

The application will provide an interactive Streamlit frontend where a
user enters column geometry, material properties, loading, and end
conditions. It will calculate relevant column properties, estimate
critical loads using applicable syllabus theories, and compare results
with tables and graphs.

## Syllabus scope

Implement only the following column topics/theories:

-   Types of columns and failure of columns
-   Euler's column theory
-   Slenderness ratio
-   End conditions for long columns
-   Equivalent length of columns
-   Limitations of Euler's formula
-   Factor of safety
-   Rankine's straight-line formula (Rankine-Gordon formula)
-   Johnson's parabolic formula

Do not add unrelated failure theories or advanced theories outside this
syllabus. Do not present crushing theory as a separate comparison
theory; the crushing-strength parameter may be used inside Rankine's
formula.

## Planned features

-   Inputs for column length, cross-section, material properties,
    applied axial load, and end condition
-   Support for solid circular, rectangular, and hollow circular
    sections, if feasible in the first version
-   Calculation of cross-sectional area, second moment of area, least
    radius of gyration, effective length, and slenderness ratio
-   Euler, Rankine, and Johnson critical-load calculations, with
    applicability notes
-   End conditions: pinned-pinned, fixed-fixed, fixed-free, and
    fixed-pinned
-   Factor of safety and allowable-load calculations
-   A comparison table showing each applicable theory's result and
    assumptions
-   Graphs of critical load versus slenderness ratio
-   Clear units, input validation, and a worked calculation breakdown
-   Optional downloadable results report after the core calculations are
    verified

## Technology stack

-   Python 3
-   Streamlit for the interface
-   NumPy for numerical calculations
-   Pandas for result tables
-   Plotly or Matplotlib for graphs
-   pytest for tests

Keep the calculation engine separate from the user interface so that
engineering calculations can be tested independently.

## Quick start

1.  Install Python 3.10 or newer.
2.  Open this folder in VS Code.
3.  Create and activate a virtual environment.

### Windows PowerShell

``` powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Linux/macOS

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

4.  Install dependencies once `requirements.txt` has been created:

``` bash
python -m pip install -r requirements.txt
```

5.  Run the app:

``` bash
streamlit run app.py
```

Streamlit will print a local URL, normally `http://localhost:8501`.

## Suggested project structure

``` text
column-analysis/
├── app.py
├── requirements.txt
├── README.md
├── copilot.md
├── skills.md
├── column_analysis/
│   ├── __init__.py
│   ├── sections.py
│   ├── properties.py
│   ├── theories.py
│   ├── validation.py
│   └── reporting.py
└── tests/
    ├── test_sections.py
    ├── test_properties.py
    └── test_theories.py
```

Copilot may adjust this structure slightly, but it must keep UI code
separate from calculation logic.

## Engineering and safety notes

-   Use consistent SI units internally: metres, square metres, pascals,
    and newtons. The interface may accept millimetres and MPa but must
    convert explicitly.
-   State assumptions and units next to each result.
-   Use the least moment of inertia and least radius of gyration for
    buckling checks.
-   Use the effective length `Le = K * L`, with the selected
    end-condition factor documented in the interface.
-   Do not classify columns using an arbitrary universal length cutoff.
    Explain the slenderness ratio and use the theory's stated
    applicability criteria.
-   Euler theory is for sufficiently slender columns and has
    limitations. Flag it when the assumptions are not met.
-   Johnson's parabolic formula is intended for intermediate columns and
    must only be shown as applicable when the selected course/material
    criterion supports it.
-   Rankine's formula combines crushing and buckling effects through its
    empirical constant. The constant and its units/convention must be
    clearly documented.
-   Do not silently choose material constants. Require the user to enter
    them or provide clearly labelled example values.
-   Factor of safety and allowable load should be calculated
    transparently. Do not imply the tool replaces professional design
    verification.
-   Validate inputs to prevent zero/negative dimensions, invalid
    material properties, division by zero, and misleading results.

## Development approach

Build and test in stages:

1.  Project setup and a minimal Streamlit page
2.  Cross-section property calculations
3.  End-condition/effective-length calculations
4.  Euler calculation and unit tests
5.  Rankine and Johnson calculations and unit tests
6.  Applicability checks and theory comparison
7.  Frontend inputs, results, and graphs
8.  Validation, sample cases, and report export

Do not implement all features in one unreviewed code dump. See
`copilot.md` for the required Copilot workflow.

## Testing

Run tests with:

``` bash
python -m pytest
```

Before relying on a result, compare sample calculations with worked
examples from the course textbook/lecture notes and have the assumptions
reviewed by the course instructor.

## Status

This README describes the intended project. Features should be marked
complete only after implementation and tests confirm they work.
