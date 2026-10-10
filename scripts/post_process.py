import sys
import subprocess
import os
import re
import math
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.simulation_config import SimulationConfig

def run_openfoam_postprocess(case_dir: Path):
    """Executa as funções de pós-processamento diretamente via simpleFoam."""
    # Calcula a pressão média no patch inlet
    cmd_p = ["simpleFoam", "-case", str(case_dir), "-postProcess", "-func", "patchAverage(name=inlet, p)", "-latestTime"]
    subprocess.run(cmd_p, capture_output=True, text=True, check=True)

    # Calcula as estatísticas de y+
    cmd_yplus = ["simpleFoam", "-case", str(case_dir), "-postProcess", "-func", "yPlus", "-latestTime"]
    subprocess.run(cmd_yplus, capture_output=True, text=True)


def get_simulated_inlet_pressure(case_dir: Path) -> float:
    """Lê o valor da pressão média no inlet a partir do arquivo gerado pelo OpenFOAM ou stdout."""
    # 1. Tenta ler o arquivo de dados gerado em postProcess/
    post_dir = case_dir / "postProcess" / "patchAverage(name=inlet, p)"
    if post_dir.exists():
        time_dirs = sorted([d for d in post_dir.iterdir() if d.is_dir()], key=lambda x: float(x.name) if x.name.replace('.', '', 1).isdigit() else 0)
        if time_dirs:
            latest_file = time_dirs[-1] / "surfaceFieldValue.dat"
            if latest_file.exists():
                with open(latest_file, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                    if lines:
                        last_line = lines[-1].split()
                        return float(last_line[1])

    # 2. Fallback via execução direta com captura do stdout
    cmd = ["simpleFoam", "-case", str(case_dir), "-postProcess", "-func", "patchAverage(name=inlet, p)", "-latestTime"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    match = re.search(r"areaAverage\(inlet\)\s+of\s+p\s+=\s+([-+]?\d*\.\d+|\d+e[-+]?\d+|\d+)", result.stdout, re.IGNORECASE)
    if match:
        return float(match.group(1))
    
    match_alt = re.search(r"patchAverage\(inlet,\s*p\)\s*=\s*([-+]?\d*\.\d+|\d+e[-+]?\d+|\d+)", result.stdout, re.IGNORECASE)
    if match_alt:
        return float(match_alt.group(1))
    raise ValueError("Could not find simulated inlet pressure in postProcess output or stdout.")


def get_wall_yplus(case_dir: Path) -> dict:
    """Calcula e extrai as métricas de y+ da parede."""
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
    """Extrai número de núcleos, tamanho da malha e tempo de execução."""
    # 1. Tamanho da malha (número de células em polyMesh/owner)
    owner_path = "template_case/constant/polyMesh/owner"
    num_cells = "N/A"
    if os.path.exists(owner_path):
        with open(owner_path, 'r') as f:
            content = f.read()
            match = re.search(r'nCells:\s*(\d+)', content)
            if match:
                num_cells = match.group(1)

    # 2. Número de núcleos usados
    decomp_path = "template_case/system/decomposeParDict"
    num_cores = "N/A"
    if os.path.exists(decomp_path):
        with open(decomp_path, 'r') as f:
            for line in f:
                if "numberOfSubdomains" in line:
                    num_cores = line.split()[1].rstrip(';')
                    break

    # 3. Tempo total gasto (extraído do log do solver)
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

    #re_num = cfg.reynolds_number

    # 1. Fator de atrito laminar (Hagen-Poiseuille)
    f_darcy = 64.0 / re_num

    # 2. Velocidade média real do escoamento (sem dividir por 2)
    u_avg = cfg.velocity_inlet  

    # 3. Queda de pressão teórica
    dp_theory_pa = f_darcy * (cfg.length / cfg.diameter) * (0.5 * cfg.density * (u_avg ** 2))
    dp_kinematic_theory = dp_theory_pa / cfg.density

    print("=" * 60)
    print("SIMULATION VERIFICATION REPORT")
    print("=" * 60)
    print(f"Reynolds Number (Re)      : {re_num:.2f}")
    print(f"Theoretical Darcy f      : {f_darcy:.5f}")
    print(f"Theoretical ΔP (Kinematic): {dp_kinematic_theory:.6f} m²/s² ({dp_theory_pa:.2f} Pa)")
    print("-" * 60)

    try:
        run_openfoam_postprocess(case_dir)

        p_inlet_sim = get_simulated_inlet_pressure(case_dir)
        yplus_data = get_wall_yplus(case_dir)
        error = abs(p_inlet_sim - dp_kinematic_theory) / dp_kinematic_theory * 100

        print(f"Simulated ΔP (Kinematic) : {p_inlet_sim:.4f} m²/s² ({p_inlet_sim * cfg.density:.2f} Pa)")
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

    except Exception as err:
        print(f"Post-processing error: {err}")


if __name__ == "__main__":
    verify_results()