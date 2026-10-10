import os
import sys
from pathlib import Path

# Diretórios base
ROOT_DIR = Path(__file__).resolve().parent.parent
CASE_DIR = ROOT_DIR / "template_case"


def setup_control_dict(case_dir: Path):
    """Gera o arquivo system/controlDict."""
    content = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      / F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /  O peration     | Version:  2606                                  |
|   \\\\  /   A nd            | Website:  www.openfoam.com                      |
|    \\\\/    M anipulation   |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      controlDict;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

application     simpleFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         1000;
deltaT          1;
writeControl    timeStep;
writeInterval   10;
purgeWrite      0;
writeFormat     ascii;
writePrecision  6;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;

// ************************************************************************* //
"""
    system_dir = case_dir / "system"
    system_dir.mkdir(parents=True, exist_ok=True)
    with open(system_dir / "controlDict", "w", encoding="utf-8") as f:
        f.write(content)


def setup_fv_schemes(case_dir: Path):
    """Gera o arquivo system/fvSchemes com a entrada wallDist necessária."""
    content = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      / F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /  O peration     | Version:  2606                                  |
|   \\\\  /   A nd            | Website:  www.openfoam.com                      |
|    \\\\/    M anipulation   |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSchemes;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

ddtSchemes
{
    default         steadyState;
}

gradSchemes
{
    default         Gauss linear;
}

divSchemes
{
    default         none;
    div(phi,U)      bounded Gauss linearUpwind grad(U);
    div(phi,k)      bounded Gauss upwind;
    div(phi,omega)  bounded Gauss upwind;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}

laplacianSchemes
{
    default         Gauss linear corrected;
}

interpolationSchemes
{
    default         linear;
}

snGradSchemes
{
    default         corrected;
}

wallDist
{
    method          meshWave;
}

// ************************************************************************* //
"""
    system_dir = case_dir / "system"
    system_dir.mkdir(parents=True, exist_ok=True)
    with open(system_dir / "fvSchemes", "w", encoding="utf-8") as f:
        f.write(content)


def setup_fv_solution(case_dir: Path):
    """Gera o arquivo system/fvSolution."""
    content = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      / F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /  O peration     | Version:  2606                                  |
|   \\\\  /   A nd            | Website:  www.openfoam.com                      |
|    \\\\/    M anipulation   |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSolution;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

solvers
{
    p
    {
        solver          GAMG;
        tolerance       1e-06;
        relTol          0.01;
        smoother        GaussSeidel;
    }

    U
    {
        solver          smoothSolver;
        smoother        GaussSeidel;
        tolerance       1e-05;
        relTol          0.1;
    }

    "(k|omega)"
    {
        solver          smoothSolver;
        smoother        GaussSeidel;
        tolerance       1e-05;
        relTol          0.1;
    }
}

SIMPLE
{
    nNonOrthogonalCorrectors 0;
    consistent      yes;

    residualControl
    {
        p               1e-4;
        U               1e-4;
        "(k|omega)"     1e-4;
    }
}

relaxationFactors
{
    equations
    {
        U               0.7;
        k               0.7;
        omega           0.7;
    }
}

// ************************************************************************* //
"""
    system_dir = case_dir / "system"
    system_dir.mkdir(parents=True, exist_ok=True)
    with open(system_dir / "fvSolution", "w", encoding="utf-8") as f:
        f.write(content)


def setup_decompose_par(case_dir: Path, num_processors: int = 10):
    """Gera o decomposeParDict usando o método Scotch com o cabeçalho FoamFile correto."""
    content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      / F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /  O peration     | Version:  2606                                  |
|   \\\\  /   A nd            | Website:  www.openfoam.com                      |
|    \\\\/    M anipulation   |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      decomposeParDict;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

numberOfSubdomains  {num_processors};

method              scotch;

// ************************************************************************* //
"""
    system_dir = case_dir / "system"
    system_dir.mkdir(parents=True, exist_ok=True)
    with open(system_dir / "decomposeParDict", "w", encoding="utf-8") as f:
        f.write(content)


def main():
    setup_control_dict(CASE_DIR)
    setup_fv_schemes(CASE_DIR)
    setup_fv_solution(CASE_DIR)
    setup_decompose_par(CASE_DIR, num_processors=10)
    print("System files (controlDict, fvSchemes, fvSolution, decomposeParDict) generated successfully.")


if __name__ == "__main__":
    main()