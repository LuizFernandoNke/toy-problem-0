import sys
from pathlib import Path

# Add root directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.simulation_config import SimulationConfig

def setup_physics_files(cfg: SimulationConfig, case_dir: Path):
    """Generates 0/U, 0/p, and constant/transportProperties for OpenFOAM."""
  
    nu_value = cfg.kinematic_viscosity

    transport_props = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2312                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "constant";
    object      transportProperties;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

transportModel  singlePhase;

nu              [0 2 -1 0 0 0 0] {nu_value:.7e};

// ************************************************************************* //
"""
    transport_path = case_dir / "constant" / "transportProperties"
    transport_path.parent.mkdir(parents=True, exist_ok=True)
    with open(transport_path, "w", encoding="utf-8") as f:
        f.write(transport_props)

    u_file = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2312                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       volVectorField;
    location    "0";
    object      U;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

dimensions      [0 1 -1 0 0 0 0];

internalField   uniform ({cfg.velocity_inlet} 0 0);

boundaryField
{{
    inlet
    {{
        type            fixedValue;
        internalField   uniform ({cfg.velocity_inlet} 0 0);
    }}

    outlet
    {{
        type            zeroGradient;
    }}

    walls
    {{
        type            noSlip;
    }}
}}

// ************************************************************************* //
"""
    u_path = case_dir / "0" / "U"
    u_path.parent.mkdir(parents=True, exist_ok=True)
    with open(u_path, "w", encoding="utf-8") as f:
        f.write(u_file)

    p_file = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2312                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       volScalarField;
    location    "0";
    object      p;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

dimensions      [0 2 -2 0 0 0 0];

internalField   uniform 0;

boundaryField
{
    inlet
    {
        type            zeroGradient;
    }

    outlet
    {
        type            fixedValue;
        value           uniform 0;
    }

    walls
    {
        type            zeroGradient;
    }
}

// ************************************************************************* //
"""
    p_path = case_dir / "0" / "p"
    p_path.parent.mkdir(parents=True, exist_ok=True)
    with open(p_path, "w", encoding="utf-8") as f:
        f.write(p_file)

    print("Physical boundary conditions and fluid properties generated")

if __name__ == "__main__":
    config = SimulationConfig()
    target_case = Path("template_case")
    setup_physics_files(config, target_case)