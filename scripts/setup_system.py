import sys
import subprocess
import re
import math
from pathlib import Path

# Add root directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.simulation_config import SimulationConfig

def get_simulated_inlet_pressure(case_dir: Path) -> float:
    """Executes OpenFOAM patchAverage utility to get average pressure at the inlet."""
    cmd = ["postProcess", "-case", str(case_dir), "-func", "patchAverage(name=inlet, p)", "-latestTime"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    match = re.search(r"areaAverage\(inlet\)\s+of\s+p\s+=\s+([-+]?\d*\.\d+|\d+)", result.stdout)
    if match:
        return float(match.group(1))
    
    match_alt = re.search(r"patchAverage\(inlet,\s*p\)\s*=\s*([-+]?\d*\.\d+|\d+)", result.stdout)
    if match_alt:
        return float(match_alt.group(1))
        
    raise ValueError("Could not parse inlet pressure from postProcess output.")

def get_wall_yplus(case_dir: Path) -> dict:
    """Executes simpleFoam yPlus utility and parses min, max, and average y+ for the wall patch."""
    cmd = ["simpleFoam", "-case", str(case_dir), "-postProcess", "-func", "yPlus", "-latestTime"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    stdout = result.stdout

    # Pattern 1: Standard patch output (e.g., "Patch walls y+ : min = 12.3, max = 45.6, average = 28.4")
    pattern_patch = r"Patch\s+walls\s+y\+\s*:\s*min\s*=\s*([0-9.eE+-]+)\s*,\s*max\s*=\s*([0-9.eE+-]+)\s*,\s*average\s*=\s*([0-9.eE+-]+)"
    match = re.search(pattern_patch, stdout, re.IGNORECASE)
    
    if match:
        return {
            "min": float(match.group(1)),
            "max": float(match.group(2)),
            "avg": float(match.group(3))
        }

    # Pattern 2: v2606 multi-line format where 'walls' is printed before min/max/avg lines
    pattern_multiline = r"walls[\s\S]*?min\s*=\s*([0-9.eE+-]+)[\s\S]*?max\s*=\s*([0-9.eE+-]+)[\s\S]*?average\s*=\s*([0-9.eE+-]+)"
    match_multi = re.search(pattern_multiline, stdout, re.IGNORECASE)

    if match_multi:
        return {
            "min": float(match_multi.group(1)),
            "max": float(match_multi.group(2)),
            "avg": float(match_multi.group(3))
        }

    # Pattern 3: Generic mesh overall y+ summary line
    pattern_generic = r"y\+\s*:\s*min\s*=\s*([0-9.eE+-]+)\s*,\s*max\s*=\s*([0-9.eE+-]+)\s*,\s*average\s*=\s*([0-9.eE+-]+)"
    match_gen = re.search(pattern_generic, stdout, re.IGNORECASE)

    if match_gen:
        return {
            "min": float(match_gen.group(1)),
            "max": float(match_gen.group(2)),
            "avg": float(match_gen.group(3))
        }

    return {"min": 0.0, "max": 0.0, "avg": 0.0}

def verify_results():
    cfg = SimulationConfig()
    case_dir = Path("template_case")

    # Theoretical calculations
    re_num = cfg.reynolds_number
    f_darcy = 0.25 / (math.log10(5.74 / (re_num ** 0.9))) ** 2
    dp_theory_pa = f_darcy * (cfg.length / cfg.diameter) * (0.5 * cfg.density * (cfg.velocity_inlet ** 2))
    dp_kinematic_theory = dp_theory_pa / cfg.density

    print("=" * 55)
    print("SIMULATION VERIFICATION REPORT")
    print("=" * 55)
    print(f"Reynolds Number (Re)      : {re_num:.2f}")
    print(f"Theoretical Darcy f      : {f_darcy:.5f}")
    print(f"Theoretical ΔP (Kinematic): {dp_kinematic_theory:.4f} m²/s² ({dp_theory_pa:.2f} Pa)")
    print("-" * 55)

    try:
        p_inlet_sim = get_simulated_inlet_pressure(case_dir)
        yplus_data = get_wall_yplus(case_dir)
        error = abs(p_inlet_sim - dp_kinematic_theory) / dp_kinematic_theory * 100

        print(f"Simulated ΔP (Kinematic) : {p_inlet_sim:.4f} m²/s² ({p_inlet_sim * cfg.density:.2f} Pa)")
        print(f"Relative Error            : {error:.2f}%")
        print("-" * 55)
        print("WALL DISTANCE METRICS (y+)")
        print(f"Wall y+ (Min / Max / Avg) : {yplus_data['min']:.2f} / {yplus_data['max']:.2f} / {yplus_data['avg']:.2f}")
        
        # y+ regime advice
        if yplus_data['avg'] < 1.0:
            print("y+ Status                 : Optimal for low-Re viscous sublayer resolution (y+ < 1)")
        elif 30.0 <= yplus_data['avg'] <= 300.0:
            print("y+ Status                 : Optimal for standard wall functions (30 < y+ < 300)")
        else:
            print("y+ Status                 : In buffer layer (1 < y+ < 30). Consider adjusting mesh.")
            
        print("=" * 55)

        # Comparative evaluation and status output
        if error < 5.0:
            print("VERIFICATION SUCCESS: CFD results match theory within 5% error!")
        else:
            print(f"Difference exceeds 5% (Current: {error:.2f}%).")
            if yplus_data['avg'] > 30.0:
                print("Tip: High y+ uses wall functions. To reduce error below 5%, refine mesh near walls towards y+ ~ 1.")
            else:
                print("Tip: Check mesh resolution or evaluate ΔP across the fully developed region.")
        print("=" * 55)

    except Exception as err:
        print(f"Post-processing error: {err}")

if __name__ == "__main__":
    verify_results()