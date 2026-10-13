import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import numpy as np
import matplotlib.pyplot as plt
from config.simulation_config import SimulationConfig
from scripts.post_process import SAMPLING_PERCENTAGE


def carregar_perfil_planos(filepath: Path, density: float):
    z_vals, p_vals = [], []
    if not filepath.exists():
        return z_vals, p_vals

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    z = float(parts[0])
                    p_kin = float(parts[1])
                    z_vals.append(z)
                    p_vals.append(p_kin * density)
                except ValueError:
                    continue

    return z_vals, p_vals


def gerar_grafico_comparativo():
    cfg = SimulationConfig()
    output_path = ROOT_DIR / "comparacao_modelos_turbulencia.png"
    profiles_dir = ROOT_DIR / "profiles"

    plt.figure(figsize=(9, 5.5))

    sampling_ratio = max(0.0, min(100.0, SAMPLING_PERCENTAGE)) / 100.0
    z_target = cfg.length * sampling_ratio

    # Curva Teórica (Darcy-Weisbach)
    re_num = cfg.reynolds_number
    if re_num < 2300:
        f_darcy = 64.0 / re_num
    elif re_num <= 100000:
        f_darcy = 0.3164 / (re_num ** 0.25)
    else:
        f_darcy = 0.0055 * (1.0 + (20000.0 / re_num) ** (1.0 / 3.0))

    dp_total_theory = f_darcy * (cfg.length / cfg.diameter) * (0.5 * cfg.density * (cfg.velocity_inlet ** 2))
    z_theory = np.linspace(0, cfg.length, 200)
    p_theory = dp_total_theory * (1.0 - z_theory / cfg.length)

    plt.plot(z_theory, p_theory, "r--", linewidth=2.0, label="Teórico (Darcy-Weisbach)")

    # Configuração de estilos distintos para permitir diferenciação visual
    modelos = {
        "kEpsilon": {
            "color": "#1f77b4",
            "ls": "-",
            "marker": "o",
            "lw": 2.5,
            "ms": 6,
            "zorder": 3,
            "file": profiles_dir / "perfil_kEpsilon.dat",
        },
        "kOmegaSST": {
            "color": "#e76f51",
            "ls": "--",
            "marker": "s",
            "lw": 1.8,
            "ms": 5,
            "zorder": 4,
            "file": profiles_dir / "perfil_kOmegaSST.dat",
        },
    }

    perfis_encontrados = False
    max_p_sim = dp_total_theory

    for model_name, info in modelos.items():
        z_vals, p_vals = carregar_perfil_planos(info["file"], cfg.density)
        if z_vals and p_vals:
            perfis_encontrados = True
            plt.plot(
                z_vals,
                p_vals,
                color=info["color"],
                linestyle=info["ls"],
                marker=info["marker"],
                linewidth=info["lw"],
                markersize=info["ms"],
                zorder=info["zorder"],
                label=f"Simulado ({model_name})",
            )
            max_p_sim = max(max_p_sim, max(p_vals))

    if not perfis_encontrados:
        print(f"[Aviso] Nenhum perfil .dat encontrado na pasta {profiles_dir}.")
        plt.close()
        return

    plt.axvline(
        x=z_target,
        color="g",
        linestyle=":",
        linewidth=1.8,
        label=f"Ponto de Medição (z = {z_target:.2f} m)",
    )

    plt.title(r"Perfil de Pressão Média Transversal ($\Delta P$) ao Longo do Duto", fontsize=12, fontweight="bold", pad=15)
    plt.xlabel("Posição z (m)", fontsize=10)
    plt.ylabel("Pressão Manométrica Média (Pa)", fontsize=10)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(loc="upper right", frameon=True)
    plt.ylim(-1.0, max_p_sim * 1.25)
    plt.tight_layout()

    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"✅ [GRÁFICO ATUALIZADO] Guardado em: {output_path}")


if __name__ == "__main__":
    gerar_grafico_comparativo()