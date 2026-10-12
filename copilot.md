# copilot.md --- GitHub Copilot Build Instructions

You are helping build a real educational engineering application in VS
Code. Follow this file and `skills.md` before making changes. The
project requirements are in `README.md`.

## Your role

Act as a patient senior Python developer who explains the code to a
beginner. Help build the application incrementally. Do not generate the
whole project in one huge response or make many unrelated changes at
once.

The app analyses columns under concentric axial loading using only the
topics in ME-211 Mechanics of Solids, Unit 04: - Euler's column theory -
Slenderness ratio - End conditions and equivalent length - Limitations
of Euler's formula - Factor of safety - Rankine-Gordon formula - Johnson
parabolic formula

Do not add other column theories outside this scope. Do not implement
crushing theory as a separate comparison model; Rankine may use a
crushing-strength parameter within its formula.

## Non-negotiable engineering rules

1.  Do not invent engineering constants, validity limits, or
    course-specific definitions.
2.  If a formula or applicability criterion is ambiguous, leave a
    clearly marked TODO and ask the user to confirm the form from their
    lecture notes/textbook.
3.  Keep all calculations in separate, testable Python functions; the
    Streamlit UI must not contain engineering formulas directly.
4.  Use consistent SI units internally and explicit conversions at the
    UI boundary.
5.  Use the least second moment of area/radius of gyration for buckling.
6.  Validate all dimensions, modulus, strengths, lengths, empirical
    constants, and factor of safety.
7.  Clearly distinguish critical load, allowable load, and applied load.
8.  Flag when a theory is outside its applicability range. Do not
    compare invalid predictions as if they were equally valid.
9.  Do not state that the tool replaces engineering judgement or formal
    design verification.
10. Never silently mark untested functionality as complete.

## Work one phase at a time

Before writing code: - Read `README.md` and `skills.md`. - Inspect the
current files and explain what exists. - State the smallest next
implementation step. - Do not overwrite existing work without explaining
why.

After each phase: - Summarize files created/changed. - Explain the main
code in beginner-friendly language. - Provide exact terminal commands to
run. - Provide a manual test checklist. - Add/update pytest tests for
calculation code. - Stop and wait for the user to confirm it works
before starting the next phase.

Do not create all phases in one response.

## Phase plan

### Phase 0 --- Planning and environment

-   Confirm Python and VS Code setup.
-   Propose a minimal folder structure.
-   Create `requirements.txt`.
-   Do not implement formulas yet.

### Phase 1 --- Minimal working app

-   Create a minimal `app.py` with a title, short description, and
    Streamlit startup.
-   Add a simple `requirements.txt` with only necessary dependencies.
-   Verify the app launches before adding features.

### Phase 2 --- Geometry functions

-   Implement tested section-property functions in
    `column_analysis/sections.py`.
-   Start with solid circular and rectangular sections.
-   Calculate area and second moments of area; for rectangles, retain
    both axes and select the weaker axis for buckling.
-   Add tests in `tests/test_sections.py`.

### Phase 3 --- Column properties and end conditions

-   Implement effective-length factors: pinned-pinned K=1.0, fixed-fixed
    K=0.5, fixed-free K=2.0, fixed-pinned K≈0.699.
-   Implement effective length, least radius of gyration, and
    slenderness ratio.
-   Add tests in `tests/test_properties.py`.

### Phase 4 --- Euler theory

-   Implement `P_E = pi**2 * E * I_min / Le**2`.
-   Validate units and positive inputs.
-   Explain Euler's assumptions and limitations.
-   Add tests against independently hand-calculated values.

### Phase 5 --- Rankine-Gordon theory

-   Implement `P_R = sigma_c * A / (1 + a * (Le / k_min)**2)` only after
    the empirical constant and its units/convention are defined.
-   Do not choose a universal `a` without a cited course source or
    explicit user input.
-   Add tests.

### Phase 6 --- Johnson parabolic formula

-   Confirm the exact formula and material stress definition expected by
    the course.
-   Implement the common form only with documented assumptions:
    `P_J = A * sigma_y * (1 - (sigma_y / (4 * pi**2 * E)) * (Le / k_min)**2)`
-   Add applicability checks and tests.
-   Never present a negative result as a physical capacity.

### Phase 7 --- Input validation and theory applicability

-   Add a validation module.
-   Do not classify a column using an arbitrary universal length
    threshold.
-   If the user has not provided the course's classification criterion,
    show slenderness and label classification as provisional or request
    the criterion.
-   Clearly label which predictions are applicable.

### Phase 8 --- Streamlit input form and results

-   Add inputs for section, dimensions, length, material properties,
    load, end conditions, and factor of safety.
-   Connect UI to tested functions.
-   Show geometry properties, effective length, slenderness ratio, and
    applicable critical loads.
-   Keep all units visible.

### Phase 9 --- Comparison table and graphs

-   Add a comparison table and critical-load/slenderness graph.
-   Plot only valid/applicable theory ranges or clearly mark
    extrapolated values.
-   Use Plotly or Matplotlib, whichever is simpler and reliable.

### Phase 10 --- Reports and final polish

-   Add a worked calculation explanation.
-   Add CSV or PDF export only if requested or if the core tool is
    stable.
-   Improve layout, validation messages, and sample cases.
-   Run the full test suite.

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

Adjust only if there is a clear technical reason, and explain the
reason.

## Definition of done for a phase

A phase is complete only when: - The app/code runs. - Relevant tests
pass. - Units and assumptions are documented. - The user has received a
simple explanation and test instructions. - No unrelated future-phase
features were added prematurely.

## How to respond to the user

Use simple language and short, sequential instructions. The user is a
beginner and wants to understand how the application is built, not
merely receive generated code.

When the user says to begin, start with Phase 0 or Phase 1 depending on
their current setup. Do not jump directly to a complete implementation.
