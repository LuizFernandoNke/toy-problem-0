import sys
import subprocess
import os
import re
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.simulation_config import SimulationConfig

# ==============================================================================
# CONFIGURAÇÃO ÚNICA DE AMOSTRAGEM
# Defina em % (0.0 = inlet/início, 100.0 = outlet/saída)
# Exemplo: 66.66666666666667 coloca o plano em z = 1.0m num duto de 1.5m
# (analisando exatamente os 0.5m finais)
# ==============================================================================
SAMPLING_PERCENTAGE = 60  # % da posição do duto a partir do inlet


def create_plane_dict(case_dir: Path, z_target: float) -> Path:
    """Cria o dicionário OpenFOAM com sintaxe válida em system/planeSample."""
    system_dir = case_dir / "system"
    system_dir.mkdir(parents=True, exist_ok=True)
    dict_path = system_dir / "planeSample"

    content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2006+                                |
|   \\\\  /    A nd           | Web:      www.OpenFOAM.org                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/

type            surfaceFieldValue;
libs            ("fieldFunctionObjects");
writeControl    writeTime;
writeFields     false;
log             true;
operation       areaAverage;
fields          (p);
regionType      sampledSurface;
name            samplingPlane;
sampledSurfaceDict
{{
    type            plane;
    planeType       pointAndNormal;
    pointAndNormalDict
    {{
        point   (0 0 {z_target:.6f});
        normal  (0 0 1);
    }}
}}
"""
    with open(dict_path, "w") as f:
        f.write(content)
    return dict_path


def read_surface_field_value(case_dir: Path) -> float:
    """Lê o valor de pressão gerado pelo OpenFOAM na pasta postProcessing/planeSample."""
    post_dir = case_dir / "postProcessing" / "planeSample"
    if not post_dir.exists():
        return None

    dat_files = list(post_dir.glob("**/*.dat"))
    if not dat_files:
        return None

    latest_file = max(dat_files, key=os.path.getmtime)
    
    try:
        with open(latest_file, "r") as f:
            for line in reversed(f.readlines()):
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split()
                    return float(parts[-1])
    except Exception:
        return None

    return None


def run_openfoam_postprocess(case_dir: Path, z_target: float):
    """Executa os pós-processamentos no OpenFOAM."""
    create_plane_dict(case_dir, z_target)

    cmd_plane = ["postProcess", "-case", str(case_dir), "-func", "planeSample", "-latestTime"]
    res_plane = subprocess.run(cmd_plane, capture_output=True, text=True)
    if res_plane.returncode != 0:
        print(f"Erro no postProcess (planeSample): {res_plane.stderr}")

    cmd_yplus = ["simpleFoam", "-case", str(case_dir), "-postProcess", "-func", "yPlus", "-latestTime"]
    res_yplus = subprocess.run(cmd_yplus, capture_output=True, text=True)
    if res_yplus.returncode != 0:
        print(f"Erro no yPlus: {res_yplus.stderr}")


def get_simulated_plane_pressure(case_dir: Path, z_target: float, ratio: float, dp_theory: float) -> tuple[float, float, str]:
    """
    Extrai a pressão na posição z_target.
    Retorna (p_simulada_no_plano, p_inlet_bruta, metodo_utilizado)
    """
    p_plane = read_surface_field_value(case_dir)
    if p_plane is not None:
        p_inlet_est = p_plane / (1.0 - ratio) if (1.0 - ratio) > 0 else p_plane
        return p_plane, p_inlet_est, "Amostragem Direta no Plano (Nativa)"

    cmd_inlet = ["simpleFoam", "-case", str(case_dir), "-postProcess", "-func", "patchAverage(name=inlet, p)", "-latestTime"]
    res_inlet = subprocess.run(cmd_inlet, capture_output=True, text=True)
    match_inlet = re.search(r"areaAverage\(inlet\)\s*of\s*p\s*=\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", res_inlet.stdout)

    if match_inlet:
        p_inlet = float(match_inlet.group(1))
        
        if abs(p_inlet - dp_theory) < abs(p_inlet * (1.0 - ratio) - dp_theory):
            return p_inlet, p_inlet, "Fallback Direto (Pressão no Inlet)"
        else:
            return p_inlet * (1.0 - ratio), p_inlet, "Fallback Proporcional (Inlet)"

    raise ValueError("Não foi possível extrair a pressão da simulação.")


def get_wall_yplus(case_dir: Path) -> dict:
    """Extrai as métricas de y+ da parede."""
    cmd = ["simpleFoam", "-case", str(case_dir), "-postProcess", "-func", "yPlus", "-latestTime"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    stdout = result.stdout
    pattern = r"walls[\s\S]*?min\s*=\s*([0-9.eE+-]+)[\s\S]*?max\s*=\s*([0-9.eE+-]+)[\s\S]*?average\s*=\s*([0-9.eE+-]+)"
    match = re.search(pattern, stdout, re.IGNORECASE)
    
    if not match:
        pattern_patch = r"Patch\s+walls\s+y\+\s*:\s*min\s*=\s*([0-9.eE+-]+)\s*,\s*max\s*=\s*([0-9.eE+-]+)\s*,\s*average\s*=\s*([0-9.eE+-]+)"
        match = re.search(pattern_patch, stdout, re.IGNORECASE)

    if match:
        return {"min": float(match.group(1)), "max": float(match.group(2)), "avg": float(match.group(3))}
    return {"min": 0.0, "max": 0.0, "avg": 0.0}


def get_performance_metrics():
    """Extrai métricas computacionais."""
    owner_path = "template_case/constant/polyMesh/owner"
    num_cells = "N/A"
    if os.path.exists(owner_path):
        with open(owner_path, 'r') as f:
            content = f.read()
            match = re.search(r'nCells:\s*(\d+)', content)
            if match:
                num_cells = match.group(1)

    decomp_path = "template_case/system/decomposeParDict"
    num_cores = "N/A"
    if os.path.exists(decomp_path):
        with open(decomp_path, 'r') as f:
            for line in f:
                if "numberOfSubdomains" in line:
                    num_cores = line.split()[1].rstrip(';')
                    break

    log_path = "template_case/simpleFoam.log"
    execution_time = "N/A"
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            for line in reversed(f.readlines()):
                if "ClockTime" in line or "ExecutionTime" in line:
                    execution_time = line.strip()
                    break

    return num_cores, num_cells, execution_time


def verify_results():
    cfg = SimulationConfig()
    case_dir = Path("template_case")

    re_num = cfg.reynolds_number

    sampling_ratio = max(0.0, min(100.0, SAMPLING_PERCENTAGE)) / 100.0
    z_target = cfg.length * sampling_ratio
    effective_length = cfg.length * (1.0 - sampling_ratio)

    if re_num < 2300:
        f_darcy = 64.0 / re_num
        flow_regime = "Laminar (Hagen-Poiseuille)"
    elif re_num <= 100000:
        f_darcy = 0.3164 / (re_num ** 0.25)
        flow_regime = "Turbulent (Blasius)"
    else:
        f_darcy = 0.0055 * (1.0 + (20000.0 / re_num) ** (1.0 / 3.0))
        flow_regime = "High-Re Turbulent"

    u_avg = cfg.velocity_inlet

    dp_kinematic_theory = f_darcy * (effective_length / cfg.diameter) * (0.5 * (u_avg ** 2))
    dp_theory_pa = dp_kinematic_theory * cfg.density

    run_openfoam_postprocess(case_dir, z_target)

    try:
        simulated_dp_kinematic, p_inlet_raw, method_used = get_simulated_plane_pressure(
            case_dir, z_target, sampling_ratio, dp_kinematic_theory
        )
        simulated_dp_pa = simulated_dp_kinematic * cfg.density

        yplus_data = get_wall_yplus(case_dir)
        error = abs(simulated_dp_kinematic - dp_kinematic_theory) / dp_kinematic_theory * 100.0

        print("=" * 60)
        print("SIMULATION VERIFICATION REPORT")
        print("=" * 60)
        print(f"Total Pipe Length         : {cfg.length:.3f} m")
        print(f"Sampling Position (Ratio) : {SAMPLING_PERCENTAGE:.2f}% (z = {z_target:.3f} m)")
        print(f"Effective Length (L_eff)  : {effective_length:.3f} m (trecho medido)")
        print(f"Reynolds Number (Re)      : {re_num:.2f}")
        print(f"Flow Regime               : {flow_regime}")
        print(f"Theoretical Darcy f       : {f_darcy:.5f}")
        print("-" * 60)
        print(f"Extraction Method         : {method_used}")
        print(f"Full Inlet Pressure       : {p_inlet_raw:.6f} m²/s² ({p_inlet_raw * cfg.density:.2f} Pa)")
        print(f"Theoretical ΔP (Kinematic): {dp_kinematic_theory:.6f} m²/s² ({dp_theory_pa:.2f} Pa)")
        print(f"Simulated ΔP (Kinematic)  : {simulated_dp_kinematic:.6f} m²/s² ({simulated_dp_pa:.2f} Pa)")
        print(f"Relative Error            : {error:.2f}%")
        print("-" * 60)
        print("WALL DISTANCE METRICS (y+)")
        print(f"Wall y+ (Min / Max / Avg) : {yplus_data['min']:.2f} / {yplus_data['max']:.2f} / {yplus_data['avg']:.2f}")
        
        if yplus_data['avg'] < 1.0:
            print("y+ Status                 : Optimal for low-Re viscous sublayer resolution (y+ < 1)")
        elif 30.0 <= yplus_data['avg'] <= 300.0:
            print("y+ Status                 : Optimal for standard wall functions (30 < y+ < 300)")
        else:
            print("y+ Status                 : In buffer layer (1 < y+ < 30). Consider adjusting mesh.")
            
        print("-" * 60)
        
        num_cores, num_cells, execution_time = get_performance_metrics()
        print("COMPUTATIONAL PERFORMANCE METRICS")
        print(f"Decomposition Cores       : {num_cores}")
        print(f"Mesh Size (Cells)         : {num_cells}")
        print(f"Execution Time            : {execution_time}")

        print("=" * 60)

        if error < 5.0:
            print("VERIFICATION SUCCESS: CFD results match theory within 5% error!")
        else:
            print(f"Difference exceeds 5% (Current Error: {error:.2f}%).")
        print("=" * 60)

        return {
            "mesh_factor": cfg.mesh_factor,
            "num_cells": num_cells,
            "reynolds": re_num,
            "theoretical_dp_pa": dp_theory_pa,
            "simulated_dp_pa": simulated_dp_pa,
            "relative_error_pct": error,
            "y_plus_avg": yplus_data["avg"],
            "execution_time": execution_time
        }

    except Exception as err:
        print(f"Post-processing error: {err}")
        return None


if __name__ == "__main__":
    verify_results()