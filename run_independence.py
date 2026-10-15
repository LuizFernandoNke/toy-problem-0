import csv
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

from config.simulation_config import SimulationConfig

CASE_DIR = ROOT_DIR / "template_case"
REPORT_CSV = ROOT_DIR / "mesh_independence_report.csv"


def get_openfoam_env_cmd() -> str:
    """Retorna o comando de inicialização do ambiente OpenFOAM."""
    possible_paths = [
        "/usr/lib/openfoam/openfoam2606/etc/bashrc",
        "/opt/openfoam2606/etc/bashrc",
        os.path.expanduser("~/OpenFOAM/openfoam2606/etc/bashrc"),
        "/usr/lib/openfoam/openfoam/etc/bashrc",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return f"source {path} && "
    return "source /usr/lib/openfoam/openfoam2606/etc/bashrc 2>/dev/null || source /usr/lib/openfoam/openfoam/etc/bashrc 2>/dev/null && "


def update_simulation_config(factor: float):
    """Atualiza o mesh_factor no config/simulation_config.py de forma isolada."""
    config_file = ROOT_DIR / "config" / "simulation_config.py"
    if not config_file.exists():
        print(f"[ERRO] Ficheiro {config_file} não encontrado.")
        sys.exit(1)

    content = config_file.read_text(encoding="utf-8")
    pattern = r"(mesh_factor(?:\s*:\s*float)?\s*=\s*)[-+]?\d*\.?\d+"
    if re.search(pattern, content):
        new_content = re.sub(pattern, rf"\g<1>{factor:.2f}", content)
    else:
        new_content = content + f"\nmesh_factor = {factor:.2f}\n"

    config_file.write_text(new_content, encoding="utf-8")


def get_wall_yplus_metrics(case_dir: Path) -> dict:
    """Executa o utilitário yPlus e extrai min, max e média das paredes do duto."""
    env_cmd = get_openfoam_env_cmd()
    cmd = f"{env_cmd} simpleFoam -case {case_dir} -postProcess -func yPlus -latestTime"
    
    res = subprocess.run(
        cmd,
        shell=True,
        executable="/bin/bash",
        capture_output=True,
        text=True,
        env=os.environ.copy()
    )
    
    stdout = res.stdout + "\n" + res.stderr

    # 1. Tenta encontrar a saída específica do patch 'walls'
    pattern_walls = r"(?:Patch\s+)?walls[\s\S]*?min\s*=\s*([0-9.eE+-]+)\s*,\s*max\s*=\s*([0-9.eE+-]+)\s*,\s*average\s*=\s*([0-9.eE+-]+)"
    match = re.search(pattern_walls, stdout, re.IGNORECASE)

    # 2. Caso o nome seja genérico no log
    if not match:
        pattern_gen = r"min\s*=\s*([0-9.eE+-]+)\s*,\s*max\s*=\s*([0-9.eE+-]+)\s*,\s*average\s*=\s*([0-9.eE+-]+)"
        match = re.search(pattern_gen, stdout, re.IGNORECASE)

    if match:
        return {
            "min": f"{float(match.group(1)):.2f}",
            "max": f"{float(match.group(2)):.2f}",
            "avg": f"{float(match.group(3)):.2f}"
        }

    # 3. Fallback: Procura ficheiros gerados em postProcessing/yPlus/
    yplus_dir = case_dir / "postProcessing" / "yPlus"
    if yplus_dir.exists():
        dat_files = list(yplus_dir.glob("**/*.dat"))
        if dat_files:
            latest_dat = max(dat_files, key=os.path.getmtime)
            try:
                lines = latest_dat.read_text(encoding="utf-8", errors="ignore").splitlines()
                for line in reversed(lines):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split()
                        if len(parts) >= 4:
                            return {
                                "min": f"{float(parts[1]):.2f}",
                                "max": f"{float(parts[2]):.2f}",
                                "avg": f"{float(parts[3]):.2f}"
                            }
            except Exception:
                pass

    return {"min": "N/A", "max": "N/A", "avg": "N/A"}


def extract_case_metrics(cfg: SimulationConfig) -> tuple[float, str, dict]:
    """
    Extrai as métricas fisicamente corretas diretamente dos ficheiros do OpenFOAM.
    Retorna: (simulated_dp_pa, num_cells, yplus_metrics_dict)
    """
    # 1. Número de células diretamente do polyMesh/owner
    num_cells = "N/A"
    owner_file = CASE_DIR / "constant" / "polyMesh" / "owner"
    if owner_file.exists():
        try:
            content = owner_file.read_text(encoding="utf-8", errors="ignore")
            match = re.search(r'nCells:\s*(\d+)', content)
            if match:
                num_cells = match.group(1)
        except Exception:
            pass

    # 2. Leitura da pressão cinemática (m²/s²) do plano de amostragem
    post_dir = CASE_DIR / "postProcessing"
    p_kinematic = None

    if post_dir.exists():
        sample_files = []
        for dat in post_dir.glob("**/*.dat"):
            path_str = str(dat).lower()
            if "plane" in path_str or "sample" in path_str:
                sample_files.append(dat)

        if sample_files:
            latest_dat = max(sample_files, key=os.path.getmtime)
            try:
                lines = latest_dat.read_text(encoding="utf-8", errors="ignore").splitlines()
                for line in reversed(lines):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split()
                        p_kinematic = float(parts[-1])
                        break
            except Exception:
                pass

    if p_kinematic is None:
        p_kinematic = 0.0

    sampling_ratio = 0.50
    effective_length = cfg.length * (1.0 - sampling_ratio)
    
    dp_friction_pa = p_kinematic * cfg.density
    
    theta_rad = math.radians(getattr(cfg, "inclination_deg", 0.0))
    dp_hydrostatic_pa = cfg.density * 9.81 * effective_length * math.sin(theta_rad)
    
    simulated_dp_pa = dp_friction_pa + dp_hydrostatic_pa

    # 3. Extração real do y+ (min, max, avg)
    yplus_data = get_wall_yplus_metrics(CASE_DIR)

    return round(simulated_dp_pa, 4), num_cells, yplus_data


def write_report_instantly(records: list):
    """Grava o relatório isolado no disco e força sincronismo com o sistema de ficheiros."""
    if not records:
        return

    fieldnames = [
        "mesh_factor",
        "num_cells",
        "simulated_dp_pa",
        "variation_from_previous_pct",
        "yplus_min",
        "yplus_max",
        "yplus_avg",
        "execution_time",
        "convergence_status"
    ]

    with open(REPORT_CSV, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
        f.flush()
        os.fsync(f.fileno())


def run_mesh_independence():
    mesh_factors = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    tolerance_pct = 1.0  # Critério de convergência inter-malhas (< 1.0%)

    results = []
    previous_dp = None
    independent_factor = None

    print("=" * 75)
    print(" ESTUDO DE INDEPENDÊNCIA DE MALHA (GRID CONVERGENCE STUDY)")
    print(f" Planilha de Saída       : {REPORT_CSV.name}")
    print(f" Fatores de refinamento : {mesh_factors}")
    print(f" Tolerância inter-malhas: < {tolerance_pct}%")
    print("=" * 75)

    for idx, factor in enumerate(mesh_factors, 1):
        print("\n" + "=" * 70)
        print(f" [{idx}/{len(mesh_factors)}] EXECUTANDO SIMULAÇÃO MESH FACTOR = {factor:.2f}")
        print("=" * 70)

        update_simulation_config(factor)
        cfg = SimulationConfig()

        start_time = time.time()

        custom_env = os.environ.copy()
        custom_env["SKIP_SIMULATION_RESULTS_CSV"] = "1"

        cmd = [sys.executable, str(ROOT_DIR / "run_pipeline.py")]
        proc = subprocess.run(cmd, env=custom_env)

        elapsed_seconds = time.time() - start_time
        mins, secs = divmod(int(elapsed_seconds), 60)
        formatted_time = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

        if proc.returncode != 0:
            print(f"[ERRO CRÍTICO] A simulação falhou para mesh_factor = {factor:.2f}")
            sys.exit(1)

        current_dp, num_cells, yplus_data = extract_case_metrics(cfg)

        if previous_dp is None or previous_dp == 0.0:
            variation_pct = 0.0
            status = "Malha Base (Coarsest)"
        else:
            variation_pct = abs(current_dp - previous_dp) / previous_dp * 100.0 if previous_dp > 0 else 0.0
            if variation_pct <= tolerance_pct:
                status = f"INDEPENDENTE (Variação < {tolerance_pct}%)"
                if independent_factor is None:
                    independent_factor = factor
            else:
                status = "Em Refinamento"

        record = {
            "mesh_factor": factor,
            "num_cells": num_cells,
            "simulated_dp_pa": round(current_dp, 4),
            "variation_from_previous_pct": round(variation_pct, 4),
            "yplus_min": yplus_data["min"],
            "yplus_max": yplus_data["max"],
            "yplus_avg": yplus_data["avg"],
            "execution_time": formatted_time,
            "convergence_status": status
        }

        results.append(record)
        write_report_instantly(results)

        print(f"\n  [DADOS REGISTADOS - MESH FACTOR {factor:.2f}]")
        print(f"  ├─ Células               : {num_cells}")
        print(f"  ├─ Pressão Simulada (Pa) : {current_dp:.4f} Pa")
        print(f"  ├─ y+ (min / max / avg)  : {yplus_data['min']} / {yplus_data['max']} / {yplus_data['avg']}")
        print(f"  ├─ Tempo Real Decorrido  : {formatted_time}")
        if idx > 1:
            print(f"  ├─ Variação Inter-Malhas : {variation_pct:.3f}%")
        print(f"  └─ Status                : {status}")

        previous_dp = current_dp

    print("\n" + "=" * 75)
    print(" ESTUDO DE INDEPENDÊNCIA DE MALHA CONCLUÍDO COM SUCESSO!")
    print(f" Relatório final gravado exclusivamente em: {REPORT_CSV.resolve()}")
    print("=" * 75)


if __name__ == "__main__":
    run_mesh_independence()