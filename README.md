# Toy Problem 0: OpenFOAM Single-Phase Flow Automation and Validation

A Python-based framework designed to automate, parameterize, and validate Computational Fluid Dynamics (CFD) simulations of single-phase pipe flows using **OpenFOAM** (`simpleFoam`).

This project integrates analytical theoretical validation directly into the execution pipeline, ensuring full traceability and real-time numerical error verification.

---

## Features

- **Robust Configuration Management:** Parameter validation and typing via **Pydantic** (`SimulationConfig`).
- **Automated Workflow Orchestration:** Full CFD lifecycle execution (`run_pipeline.py`):
  1. Mesh generation and refinement (`blockMesh`).
  2. Initial and boundary condition setup in `0/`.
  3. Numerical scheme and solver control setup (`fvSchemes`, `fvSolution`, `controlDict`).
  4. Flow regime configuration (Laminar vs. RANS turbulence models).
  5. Post-processing and automated verification report generation.
- **Integrated Analytical Verification:**
  - **Laminar Regime ($Re \le 2500$):** Parabolic velocity profile and Hagen-Poiseuille Darcy friction factor ($f = 64/Re$).
  - **Turbulent Regime Support ($Re > 4000$):** Modular support for RANS models ($k-\omega\text{ SST} / k-\epsilon$) and Blasius/Moody correlations.
- **Mesh Quality Metrics:** Automatic viscous sublayer ($y^+$) monitoring.

---

## Repository Structure

```text
toy-problem-0/
├── config/
│   └── simulation_config.py   # Parameterized case management (Pydantic)
├── scripts/
│   ├── generate_mesh.py       # Mesh automation (blockMeshDict)
│   ├── setup_physics.py      # Initial/boundary conditions (U, p, nu)
│   ├── setup_system.py       # Solver numerical schemes and time controls
│   ├── setup_turbulence.py   # Regime selection (Laminar or RANS)
│   └── post_process.py       # Data extraction, ΔP calculation, and error report
├── template_case/            # OpenFOAM base case template
├── requirements.txt          # Python dependencies
└── run_pipeline.py           # Main pipeline orchestration script