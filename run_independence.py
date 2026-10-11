import csv
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

from run_pipeline import main as run_pipeline_main
from scripts.post_process import verify_results


def set_mesh_factor_in_config(factor: float):
    """Atualiza a linha do mesh_factor diretamente no config/simulation_config.py."""
    config_file = ROOT_DIR / "config" / "simulation_config.py"
    if not config_file.exists():
        print(f"Erro: Ficheiro {config_file} não encontrado.")
        sys.exit(1)

    content = config_file.read_text(encoding="utf-8")

    # Substitui a linha do mesh_factor no arquivo simulation_config.py
    updated_content = re.sub(
        r"(mesh_factor\s*:\s*float\s*=\s*)[0-9.]+",
        rf"\g<1>{factor}",
        content
    )

    config_file.write_text(updated_content, encoding="utf-8")


def save_csv_report(csv_filename: Path, results: list):
    """Grava a lista de resultados no ficheiro CSV ignorando entradas nulas."""
    valid_results = [r for r in results if isinstance(r, dict)]
    if not valid_results:
        return

    fieldnames = list(valid_results[0].keys())
    with open(csv_filename, mode="w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(valid_results)


def run_mesh_independence():
    mesh_factors = [1.0, 1.5, 2.0, 2.5, 3.0]
    csv_filename = ROOT_DIR / "mesh_independence_report.csv"
    results = []

    print("#" * 70)
    print(" ESTUDO DE INDEPENDÊNCIA DE MALHA ")
    print(f" Fatores a testar: {mesh_factors}")
    print("#" * 70)

    # 1. Executa os 5 testes de sensibilidade
    for factor in mesh_factors:
        print(f"\n" + "=" * 60)
        print(f" EXECUTANDO TESTE COM MESH FACTOR = {factor}")
        print("=" * 60 + "\n")

        set_mesh_factor_in_config(factor)
        run_pipeline_main()

        metrics = verify_results()
        results.append(metrics)

        # Salva/atualiza o CSV imediatamente após CADA simulação individual
        save_csv_report(csv_filename, results)
        print(f"\n[CSV ATUALIZADO] Fator {factor} adicionado ao relatório: {csv_filename}")

    if results:
        # 2. Encontra a simulação que obteve o menor erro relativo
        best_run = min(results, key=lambda x: abs(x.get("relative_error_pct", float("inf"))))
        best_factor = best_run["mesh_factor"]
        best_error = best_run["relative_error_pct"]

        print("\n" + "=" * 70)
        print(f" MELHOR CONFIGURAÇÃO: Mesh Factor = {best_factor} (Erro Relativo: {best_error:.2f}%)")
        print("=" * 70)

        # 3. Atualiza o config/simulation_config.py com o melhor fator
        set_mesh_factor_in_config(best_factor)

        # 4. Roda o pipeline final com a melhor malha
        print("\n" + "=" * 70)
        print(f" EXECUTANDO SIMULAÇÃO FINAL COM O MELHOR MESH FACTOR ({best_factor})")
        print("=" * 70 + "\n")
        run_pipeline_main()

        # 5. Coleta as métricas finais e atualiza o CSV com a última linha
        final_metrics = verify_results()
        results.append(final_metrics)
        save_csv_report(csv_filename, results)
        print(f"\n[CSV ATUALIZADO] Resultado da simulação final gravado no relatório.")

    print("\n" + "=" * 70)
    print(" ESTUDO DE INDEPENDÊNCIA E SIMULAÇÃO FINAL CONCLUÍDOS")
    print(f" Relatório CSV completo salvo em: {csv_filename}")
    print("=" * 70)


if __name__ == "__main__":
    run_mesh_independence()