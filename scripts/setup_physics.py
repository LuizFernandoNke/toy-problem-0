import sys
import math
from pathlib import Path

# Add root directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.simulation_config import SimulationConfig

def setup_physics_files(cfg: SimulationConfig, case_dir: Path):
    """Generates 0/U, 0/p, constant/transportProperties, and constant/g for OpenFOAM."""
    
    # =========================================================================
    # 1. Write constant/transportProperties
    # =========================================================================
    transport_props = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2606                                 |
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

transportModel  Newtonian;

nu              [0 2 -1 0 0 0 0] {cfg.kinematic_viscosity:.7e};

// ************************************************************************* //
"""
    transport_path = case_dir / "constant" / "transportProperties"
    transport_path.parent.mkdir(parents=True, exist_ok=True)
    with open(transport_path, "w", encoding="utf-8") as f:
        f.write(transport_props)

    # =========================================================================
    # 2. Write constant/g (Gravity Vector with Inclination)
    # =========================================================================
    inclination_deg = getattr(cfg, 'inclination_deg', 0.0)
    rad = math.radians(inclination_deg)
    g_mag = 9.81

    # Decomposição do vetor gravidade (Tubo no eixo Z, vertical no eixo Y)
    gx = 0.0
    gy = -g_mag * math.cos(rad)
    gz = -g_mag * math.sin(rad)

    g_file = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2606                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       uniformDimensionedVectorField;
    location    "constant";
    object      g;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

dimensions      [0 1 -2 0 0 0 0];
value           ({gx:.6f} {gy:.6f} {gz:.6f});

// ************************************************************************* //
"""
    g_path = case_dir / "constant" / "g"
    g_path.parent.mkdir(parents=True, exist_ok=True)
    with open(g_path, "w", encoding="utf-8") as f:
        f.write(g_file)

    # =========================================================================
    # 3. Write 0/U (Velocity Boundary Conditions)
    # =========================================================================
    radius = cfg.diameter / 2.0
    u_avg = cfg.velocity_inlet

    u_file = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2606                                 |
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

internalField   uniform (0 0 {u_avg});

boundaryField
{{
    inlet
    {{
        type            codedFixedValue;
        value           uniform (0 0 {u_avg});
        name            parabolicInlet;

        code
        #{{
            const scalar R = {radius:.6f};
            const scalar Uavg = {u_avg:.6f};
            const scalar Umax = 2.0 * Uavg;

            const vectorField& C = patch().Cf();
            vectorField& U = *this;

            forAll(C, i)
            {{
                const scalar r2 = sqr(C[i].x()) + sqr(C[i].y());
                scalar uz = Umax * (1.0 - r2 / sqr(R));

                if (uz < 0.0) uz = 0.0;

                U[i] = vector(0, 0, uz);
            }}
        #}};
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

    # =========================================================================
    # 4. Write 0/p (Kinematic Pressure Boundary Conditions)
    # =========================================================================
    p_file = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2606                                 |
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

    print(f"Physical boundary conditions and gravity vector (inclination: {inclination_deg}°) generated successfully.")

if __name__ == "__main__":
    config = SimulationConfig()
    target_case = Path("template_case")
    setup_physics_files(config, target_case)