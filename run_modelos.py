import csv
import os
import shutil
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.simulation_config import SimulationConfig
from run_pipeline import main as run_pipeline_main
from scripts.post_process import (
    verify_results,
    run_foam_cmd,
    create_plane_dict,
    read_surface_field_value,
)
from scripts.gerar_grafico import gerar_grafico_comparativo


def set_turbulence_model_in_config(model_name: str):
    config_file = ROOT_DIR / "config" / "simulation_config.py"
    if not config_file.exists():
        sys.exit(1)

    lines = config_file.read_text(encoding="utf-8").splitlines()
    new_lines = []
    for line in lines:
        if line.strip().startswith("turbulence_model"):
            new_lines.append(f'    turbulence_model: str = "{model_name}"')
        else:
            new_lines.append(line)

    config_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def save_csv_report(csv_filename: Path, results: list):
    valid_results = [r for r in results if isinstance(r, dict)]
    if not valid_results:
        return

    fieldnames = list(valid_results[0].keys())
    with open(csv_filename, mode="w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(valid_results)


def extract_and_save_profile_planes(case_dir: Path, cfg: SimulationConfig, model_name: str, num_planes: int = 15):
    """
    Calcula a pressão média em múltiplos planos transversais
    reutilizando exatamente as funções create_plane_dict e read_surface_field_value do post_process.py.
    """
    z_positions = [cfg.length * (i / (num_planes + 1)) for i in range(1, num_planes + 1)]
    profile_data = []

    print(f"  [Amostragem] Calculando pressão média em {num_planes} planos transversais...")

    for z in z_positions:
        # Garante leitura limpa do postProcessing
        post_plane_dir = case_dir / "postProcessing" / "planeSample"
        if post_plane_dir.exists():
            shutil.rmtree(post_plane_dir, ignore_errors=True)

        # Utiliza a função original do teu post_process.py
        create_plane_dict(case_dir, z)
        cmd_plane = f"postProcess -case {case_dir} -func planeSample -latestTime"
        run_foam_cmd(cmd_plane)

        p_val = read_surface_field_value(case_dir)
        if p_val is not None:
            profile_data.append((z, p_val))

    profiles_dir = ROOT_DIR / "profiles"
    profiles_dir.mkdir(exist_ok=True)
    dest_file = profiles_dir / f"perfil_{model_name}.dat"

    with open(dest_file, "w", encoding="utf-8") as f:
        f.write("# z_m p_kinematic\n")
        for z, p in profile_data:
            f.write(f"{z:.6f} {p:.8e}\n")

    print(f"  [Perfil Salvo] {len(profile_data)} planos médios salvos em: {dest_file}")


def run_turbulence_study():
    models_to_test = ["kEpsilon", "kOmegaSST"]
    csv_filename = ROOT_DIR / "turbulence_models_report.csv"
    results = []
    cfg = SimulationConfig()

    print("#" * 70)
    print(" ESTUDO COMPARATIVO DE MODELOS DE TURBULÊNCIA ")
    print(f" Modelos a testar: {models_to_test}")
    print("#" * 70)

    for model in models_to_test:
        print(f"\n" + "=" * 60)
        print(f" EXECUTANDO SIMULAÇÃO COM MODELO = {model}")
        print("=" * 60 + "\n")

        set_turbulence_model_in_config(model)
        run_pipeline_main()

        metrics = verify_results()
        if isinstance(metrics, dict):
            metrics["turbulence_model"] = model
            results.append(metrics)

        case_dir = ROOT_DIR / "template_case"
        extract_and_save_profile_planes(case_dir, cfg, model)

        save_csv_report(csv_filename, results)
        print(f"\n[CSV ATUALIZADO] Modelo '{model}' adicionado ao relatório: {csv_filename}")

        gerar_grafico_comparativo()

    print("\n" + "=" * 70)
    print(" ESTUDO COMPARATIVO CONCLUÍDO")
    print("=" * 70)


if __name__ == "__main__":
    run_turbulence_study()