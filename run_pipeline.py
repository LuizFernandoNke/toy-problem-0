import subprocess
import sys
import shutil
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

CASE_DIR = ROOT_DIR / "template_case"

def clean_previous_runs():
    """Remove previous time directories and post-processing artifacts."""
    print("Cleaning previous simulation runs...")
    
    if CASE_DIR.exists():
        for item in CASE_DIR.iterdir():
            if item.is_dir() and item.name.replace('.', '', 1).isdigit() and item.name != "0":
                shutil.rmtree(item)
                print(f"   Removed time directory: {item.name}")
        
        post_dir = CASE_DIR / "postProcessing"
        if post_dir.exists():
            shutil.rmtree(post_dir)
            print("   Removed postProcessing directory")

def run_step(description: str, command: list[str]):
    """Execute a system command and terminate if an error occurs."""
    print(f"\nRunning: {description}")
    result = subprocess.run(command, capture_output=False, text=True)
    
    if result.returncode != 0:
        print(f"\nError during step: {description}")
        sys.exit(1)

def main():
    print("=" * 60)
    print("STARTING END-TO-END CFD PIPELINE (OpenFOAM v2606)")
    print("=" * 60)

    clean_previous_runs()

    run_step("Configuring physics and boundary conditions", [sys.executable, "scripts/setup_physics.py"])
    run_step("Generating blockMeshDict and mesh", [sys.executable, "scripts/generate_mesh.py"])
    run_step("Setting up numerical schemes and solvers", [sys.executable, "scripts/setup_system.py"])
    run_step("Configuring turbulence model parameters", [sys.executable, "scripts/setup_turbulence.py"])
    run_step("Running simpleFoam solver", ["simpleFoam", "-case", str(CASE_DIR)])
    run_step("Processing results and generating verification report", [sys.executable, "scripts/post_process.py"])

    print("\n=" * 60)
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 60)

if __name__ == "__main__":
    main()
