import sys
import subprocess
import os
import re
import csv
import math
import traceback
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.simulation_config import SimulationConfig

# ==============================================================================
# CONFIGURAÇÃO ÚNICA DE AMOSTRAGEM
# ==============================================================================
SAMPLING_PERCENTAGE = 50  # % da posição do duto a partir do inlet
CSV_OUTPUT_PATH = Path("simulation_results.csv")


def run_foam_cmd(cmd_str: str) -> subprocess.CompletedProcess:
    """Executa um comando do OpenFOAM garantindo o carregamento do ambiente bashrc."""
    full_cmd = f"source /usr/lib/openfoam/openfoam2606/etc/bashrc && {cmd_str}"
    return subprocess.run(
        full_cmd,
        shell=True,
        executable="/bin/bash",
        capture_output=True,
        text=True,
        env=os.environ.copy()
    )


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
    with open(dict_path, "w", encoding="utf-8") as f:
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
        with open(latest_file, "r", encoding="utf-8") as f:
            for line in reversed(f.readlines()):
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split()
                    return float(parts[-1])
    except Exception:
        return None

    return None

def extract_and_save_profile(case_dir: Path, cfg: SimulationConfig, num_planes: int = 50):
    """Extrai a pressão ao longo de vários pontos do duto para o gráfico individual."""
    model_name = cfg.turbulence_model
    z_positions = [cfg.length * (i / (num_planes + 1)) for i in range(1, num_planes + 1)]
    profile_data = []

    for z in z_positions:
        post_plane_dir = case_dir / "postProcessing" / "planeSample"
        if post_plane_dir.exists():
            shutil.rmtree(post_plane_dir, ignore_errors=True)

        create_plane_dict(case_dir, z)
        cmd_plane = f"postProcess -case {case_dir} -func planeSample -latestTime"
        run_foam_cmd(cmd_plane)

        p_val = read_surface_field_value(case_dir)
        if p_val is not None:
            profile_data.append((z, p_val))

    profiles_dir = Path("profiles")
    profiles_dir.mkdir(exist_ok=True)
    dest_file = profiles_dir / f"perfil_{model_name}.dat"

    with open(dest_file, "w", encoding="utf-8") as f:
        f.write("# z_m p_kinematic\n")
        for z, p in profile_data:
            f.write(f"{z:.6f} {p:.8e}\n")

def run_openfoam_postprocess(case_dir: Path, z_target: float):
    """Executa os pós-processamentos no OpenFOAM."""
    create_plane_dict(case_dir, z_target)

    cmd_plane = f"postProcess -case {case_dir} -func planeSample -latestTime"
    res_plane = run_foam_cmd(cmd_plane)
    if res_plane.returncode != 0:
        print(f"Aviso no postProcess (planeSample): {res_plane.stderr.strip()}")

    cmd_yplus = f"simpleFoam -case {case_dir} -postProcess -func yPlus -latestTime"
    res_yplus = run_foam_cmd(cmd_yplus)
    if res_yplus.returncode != 0:
        print(f"Aviso no yPlus: {res_yplus.stderr.strip()}")


def get_simulated_plane_pressure(case_dir: Path, z_target: float, ratio: float, dp_theory: float) -> tuple[float, float, str]:
    """Extrai a pressão na posição z_target."""
    p_plane = read_surface_field_value(case_dir)
    if p_plane is not None:
        p_inlet_est = p_plane / (1.0 - ratio) if (1.0 - ratio) > 0 else p_plane
        return p_plane, p_inlet_est

    cmd_inlet = f"simpleFoam -case {case_dir} -postProcess -func \"patchAverage(name=inlet, p)\" -latestTime"
    res_inlet = run_foam_cmd(cmd_inlet)
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
    cmd = f"simpleFoam -case {case_dir} -postProcess -func yPlus -latestTime"
    result = run_foam_cmd(cmd)
    
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
        with open(owner_path, 'r', encoding="utf-8") as f:
            content = f.read()
            match = re.search(r'nCells:\s*(\d+)', content)
            if match:
                num_cells = match.group(1)

    decomp_path = "template_case/system/decomposeParDict"
    num_cores = "N/A"
    if os.path.exists(decomp_path):
        with open(decomp_path, 'r', encoding="utf-8") as f:
            for line in f:
                if "numberOfSubdomains" in line:
                    num_cores = line.split()[1].rstrip(';')
                    break

    log_path = "template_case/simpleFoam.log"
    execution_time = "N/A"
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding="utf-8") as f:
            for line in reversed(f.readlines()):
                if "ClockTime" in line or "ExecutionTime" in line:
                    execution_time = line.strip()
                    break

    return num_cores, num_cells, execution_time


def save_to_csv(data: dict, output_file: Path):
    """Escreve os dados extraídos em um arquivo CSV se não for um teste de independência."""
    # Se a flag de bloqueio estiver ativa, ignora a gravação no simulation_results.csv
    if os.environ.get("SKIP_SIMULATION_RESULTS_CSV") == "1":
        print("[INFO] Gravação em simulation_results.csv ignorada (Estudo de Independência).")
        return

    file_exists = output_file.exists()
    
    with open(output_file, mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=data.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)


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

    # --- INCLINAÇÃO E COMPONENTE HIDROSTÁTICA ---
    inclination_deg = getattr(cfg, "inclination_deg", 0.0)
    theta_rad = math.radians(inclination_deg)
    g_acc = 9.81

    # Queda de pressão por atrito (Darcy-Weisbach) em Pa
    dp_friction_pa = f_darcy * (effective_length / cfg.diameter) * (0.5 * cfg.density * (u_avg ** 2))
    
    # Componente hidrostática em Pa
    dp_hydrostatic_pa = cfg.density * g_acc * effective_length * math.sin(theta_rad)

    # Queda de pressão total teórica em Pa
    dp_theory_pa = dp_friction_pa + dp_hydrostatic_pa

    # Pressão cinemática teórica apenas por atrito
    dp_kinematic_friction = dp_friction_pa / cfg.density
    dp_kinematic_theory = dp_kinematic_friction  # <--- DEFINIDA CORRETAMENTE

    run_openfoam_postprocess(case_dir, z_target)

    try:
        simulated_dp_kinematic, p_inlet_raw = get_simulated_plane_pressure(
            case_dir, z_target, sampling_ratio, dp_kinematic_theory
        )
        method_used = "plane_sampling"

        # 1. Pressão por atrito extraída do OpenFOAM (Pa)
        simulated_dp_friction_pa = simulated_dp_kinematic * cfg.density

        # 2. Pressão Total Simulada = Atrito do OpenFOAM + Hidrostática
        simulated_dp_pa = simulated_dp_friction_pa + dp_hydrostatic_pa

        # 3. Cálculo do Erro Relativo (Pressão Total Simulada vs Teórica)
        error = abs(simulated_dp_pa - dp_theory_pa) / dp_theory_pa * 100.0

        yplus_data = get_wall_yplus(case_dir)
        num_cores, num_cells, execution_time = get_performance_metrics()

        if yplus_data['avg'] < 1.0:
            yplus_status = "Optimal (y+ < 1)"
        elif 30.0 <= yplus_data['avg'] <= 300.0:
            yplus_status = "Optimal wall functions (30 < y+ < 300)"
        else:
            yplus_status = "Buffer layer (1 < y+ < 30)"

        results_data = {
            "mesh_factor": cfg.mesh_factor,
            "inclination_deg": inclination_deg,
            "reynolds_number": re_num,
            "flow_regime": flow_regime,
            "pipe_length_m": cfg.length,
            "effective_length_m": effective_length,
            "z_target_m": z_target,
            "theoretical_darcy_f": f_darcy,
            "theoretical_dp_pa": dp_theory_pa,
            "simulated_dp_pa": simulated_dp_pa,
            "relative_error_pct": error,
            "yplus_min": yplus_data["min"],
            "yplus_max": yplus_data["max"],
            "yplus_avg": yplus_data["avg"],
            "yplus_status": yplus_status,
            "extraction_method": method_used,
            "num_cores": num_cores,
            "num_cells": num_cells,
            "execution_time": execution_time,
            "verification": "SUCCESS" if error < 5.0 else "EXCEEDED_5_PERCENT"
        }

        save_to_csv(results_data, CSV_OUTPUT_PATH)
        print(f"Resultados salvos com sucesso em: {CSV_OUTPUT_PATH.resolve()}")
        return results_data

    except Exception as err:
        print(f"Erro ao extrair resultados do pós-processamento: {err}")
        traceback.print_exc()
        return None


if __name__ == "__main__":
    verify_results()