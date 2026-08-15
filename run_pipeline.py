import os
import subprocess
import sys
import shutil
from pathlib import Path

# Diretórios base
ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

CASE_DIR = ROOT_DIR / "template_case"
NUM_PROCESSORS = 10  # Número de subdomínios para o decomposePar / mpirun


def get_openfoam_env() -> str:
    """Busca o arquivo bashrc do OpenFOAM em caminhos padrão para garantir portabilidade entre diferentes PCs."""
    possible_paths = [
        "/usr/lib/openfoam/openfoam2606/etc/bashrc",
        "/opt/openfoam2606/etc/bashrc",
        os.path.expanduser("~/OpenFOAM/openfoam2606/etc/bashrc"),
        "/usr/lib/openfoam/openfoam/etc/bashrc",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return f"source {path} && "
    # Caminho fallback
    return "source /usr/lib/openfoam/openfoam2606/etc/bashrc && "


OF_ENV = get_openfoam_env()


def clean_previous_runs():
    """Remove pastas de tempo antigas, diretórios de processadores e artefatos de pós-processamento."""
    print("Cleaning previous simulation runs...")
    
    if CASE_DIR.exists():
        for item in CASE_DIR.iterdir():
            if item.is_dir():
                # Apaga pastas numeradas (ex: 0.1, 100, etc) mantendo apenas a pasta "0"
                if (item.name.replace('.', '', 1).isdigit() and item.name != "0") or item.name.startswith("processor"):
                    shutil.rmtree(item)
                    print(f"   Removed directory: {item.name}")
        
        post_dir = CASE_DIR / "postProcessing"
        if post_dir.exists():
            shutil.rmtree(post_dir)
            print("   Removed postProcessing directory")


def run_step(description: str, command: list[str]):
    """Executa um comando do sistema garantindo o carregamento correto do ambiente."""
    print(f"\nRunning: {description}")
    
    current_env = os.environ.copy()
    
    # Se for um script Python interno do projeto
    if command[0] == sys.executable or command[0].endswith("python3") or command[0].endswith("python"):
        result = subprocess.run(command, capture_output=False, text=True, env=current_env)
    else:
        # Se for um utilitário do OpenFOAM ou MPI
        full_cmd = OF_ENV + " " + " ".join(command)
        result = subprocess.run(
            full_cmd,
            shell=True,
            executable="/bin/bash",
            capture_output=False,
            text=True,
            env=current_env
        )
    
    if result.returncode != 0:
        print(f"\nError during step: {description}")
        sys.exit(1)


def main():
    print("=" * 60)
    print("STARTING PARALLEL CFD PIPELINE (OpenFOAM v2606)")
    print("=" * 60)

    clean_previous_runs()

    # Steps de configuração e geração de malha
    run_step("Configuring physics and boundary conditions", [sys.executable, "scripts/setup_physics.py"])
    run_step("Generating blockMeshDict and mesh", [sys.executable, "scripts/generate_mesh.py"])
    run_step("Setting up numerical schemes and solvers", [sys.executable, "scripts/setup_system.py"])
    run_step("Configuring turbulence model parameters", [sys.executable, "scripts/setup_turbulence.py"])
    
    # Steps do solver em paralelo
    run_step("Decomposing domain with Scotch", ["decomposePar", "-case", str(CASE_DIR)])
    run_step(
        f"Running simpleFoam in parallel on {NUM_PROCESSORS} cores", 
        ["mpirun", "-np", str(NUM_PROCESSORS), "simpleFoam", "-parallel", "-case", str(CASE_DIR)]
    )
    run_step("Reconstructing parallel domain fields", ["reconstructPar", "-latestTime", "-case", str(CASE_DIR)])
    
    # Step de pós-processamento
    run_step("Processing results and generating verification report", [sys.executable, "scripts/post_process.py"])

    print("=" * 60)
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    main()