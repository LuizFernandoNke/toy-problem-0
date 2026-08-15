import sys
import math
from pathlib import Path

# Add root directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.simulation_config import SimulationConfig

def setup_turbulence_files(cfg: SimulationConfig, case_dir: Path):
    """Generates momentumTransport, 0/k, 0/omega, and 0/nut files for OpenFOAM."""
    
    # 1. Calculate Turbulence Quantities using SimulationConfig properties
    reynolds = cfg.reynolds_number
    i_turb = 0.16 * (reynolds ** (-1.0 / 8.0))
    k_val = 1.5 * (cfg.velocity_inlet * i_turb) ** 2
    
    l_scale = 0.07 * cfg.diameter
    c_mu = 0.09
    omega_val = (k_val ** 0.5) / ((c_mu ** 0.25) * l_scale)

    def get_header(obj_name, obj_class="volScalarField", location='"0"'):
        return f"""/*--------------------------------*- C++ -*----------------------------------*\\
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
    class       {obj_class};
    location    {location};
    object      {obj_name};
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
"""

    # 2. constant/momentumTransport
    mom_trans = get_header("momentumTransport", "dictionary", '"constant"') + """
simulationType  RAS;

RAS
{
    model           kOmegaSST;
    turbulence      on;
    printCoeffs     on;
}

// ************************************************************************* //
"""
    mom_path = case_dir / "constant" / "momentumTransport"
    mom_path.parent.mkdir(parents=True, exist_ok=True)
    with open(mom_path, "w", encoding="utf-8") as f:
        f.write(mom_trans)

    # 3. 0/k
    k_file = get_header("k") + f"""
dimensions      [0 2 -2 0 0 0 0];

internalField   uniform {k_val:.6e};

boundaryField
{{
    inlet
    {{
        type            fixedValue;
        value           uniform {k_val:.6e};
    }}
    outlet
    {{
        type            zeroGradient;
    }}
    walls
    {{
        type            kLowReWallFunction;
        value           uniform {k_val:.6e};
    }}
}}

// ************************************************************************* //
"""
    with open(case_dir / "0" / "k", "w", encoding="utf-8") as f:
        f.write(k_file)

    # 4. 0/omega
    omega_file = get_header("omega") + f"""
dimensions      [0 0 -1 0 0 0 0];

internalField   uniform {omega_val:.6e};

boundaryField
{{
    inlet
    {{
        type            fixedValue;
        value           uniform {omega_val:.6e};
    }}
    outlet
    {{
        type            zeroGradient;
    }}
    walls
    {{
        type            omegaWallFunction;
        value           uniform {omega_val:.6e};
    }}
}}

// ************************************************************************* //
"""
    with open(case_dir / "0" / "omega", "w", encoding="utf-8") as f:
        f.write(omega_file)

    # 5. 0/nut
    nut_file = get_header("nut") + """
dimensions      [0 2 -1 0 0 0 0];

internalField   uniform 0;

boundaryField
{
    inlet
    {
        type            calculated;
        value           uniform 0;
    }
    outlet
    {
        type            calculated;
        value           uniform 0;
    }
    walls
    {
        type            nutkWallFunction;
        value           uniform 0;
    }
}

// ************************************************************************* //
"""
    with open(case_dir / "0" / "nut", "w", encoding="utf-8") as f:
        f.write(nut_file)

    print(f"Turbulence configurations generated successfully (Re = {reynolds:.2f}).")

if __name__ == "__main__":
    config = SimulationConfig()
    target_case = Path("template_case")
    setup_turbulence_files(config, target_case)