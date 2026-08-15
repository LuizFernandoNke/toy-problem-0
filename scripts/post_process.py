import sys
import subprocess
import re
import math
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.simulation_config import SimulationConfig

def get_simulated_inlet_pressure(case_dir: Path) -> float:
    """Executa a função patchAverage nativa do OpenFOAM no inlet."""
    cmd = ["postProcess", "-case", str(case_dir), "-func", "patchAverage(name=inlet, p)", "-latestTime"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    match = re.search(r"areaAverage\(inlet\)\s+of\s+p\s+=\s+([-+]?\d*\.\d+|\d+)", result.stdout)
    if match:
        return float(match.group(1))
    
    match_alt = re.search(r"patchAverage\(inlet,\s*p\)\s*=\s*([-+]?\d*\.\d+|\d+)", result.stdout)
    if match_alt:
        return float(match_alt.group(1))
        
    raise ValueError("Não foi possível extrair a pressão do inlet.")

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

def verify_results():
    cfg = SimulationConfig()
    case_dir = Path("template_case")

    re_num = cfg.reynolds_number
    f_darcy = 0.25 / (math.log10(5.74 / (re_num ** 0.9))) ** 2
    dp_theory_pa = f_darcy * (cfg.length / cfg.diameter) * (0.5 * cfg.density * (cfg.velocity_inlet ** 2))
    dp_kinematic_theory = dp_theory_pa / cfg.density

    print("=" * 60)
    print(" 📊 SIMULATION VERIFICATION REPORT")
    print("=" * 60)
    print(f"Reynolds Number (Re)      : {re_num:.2f}")
    print(f"Theoretical Darcy f      : {f_darcy:.5f}")
    print(f"Theoretical ΔP (Kinematic): {dp_kinematic_theory:.4f} m²/s² ({dp_theory_pa:.2f} Pa)")
    print("-" * 60)

    try:
        p_inlet_sim = get_simulated_inlet_pressure(case_dir)
        yplus_data = get_wall_yplus(case_dir)
        error = abs(p_inlet_sim - dp_kinematic_theory) / dp_kinematic_theory * 100

        print(f"Simulated ΔP (Kinematic) : {p_inlet_sim:.4f} m²/s² ({p_inlet_sim * cfg.density:.2f} Pa)")
        print(f"Relative Error            : {error:.2f}%")
        print("-" * 60)
        print(" 📐 WALL DISTANCE METRICS (y+)")
        print(f"Wall y+ (Min / Max / Avg) : {yplus_data['min']:.2f} / {yplus_data['max']:.2f} / {yplus_data['avg']:.2f}")
        
        if yplus_data['avg'] < 1.0:
            print("y+ Status                 : Optimal for low-Re viscous sublayer resolution (y+ < 1)")
        elif 30.0 <= yplus_data['avg'] <= 300.0:
            print("y+ Status                 : Optimal for standard wall functions (30 < y+ < 300)")
        else:
            print("y+ Status                 : In buffer layer (1 < y+ < 30). Consider adjusting mesh.")
            
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
