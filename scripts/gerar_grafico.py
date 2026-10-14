import sys
import math
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.simulation_config import SimulationConfig


def gerar_grafico_pressao():
    """
    1. GRÁFICO INDIVIDUAL (run_pipeline.py -> perfil_pressao.png)
    Compara o modelo de turbulência ativo no simulation_config.py contra a Reta Teórica
    e destaca o ponto de medição (z = 1.0 m).
    """
    cfg = SimulationConfig()
    inclination = getattr(cfg, "inclination_deg", 0.0)
    theta_rad = math.radians(inclination)
    g_acc = 9.81
    model_name = cfg.turbulence_model

    sampling_percentage = 50
    z_target = cfg.length * (sampling_percentage / 100.0)

    profile_file = ROOT_DIR / "profiles" / f"perfil_{model_name}.dat"
    
    if profile_file.exists():
        data = np.loadtxt(profile_file, comments="#")
        z_coords = data[:, 0]
        p_kinematic = data[:, 1]
        p_simulated = (p_kinematic * cfg.density) + (cfg.density * g_acc * (cfg.length - z_coords) * math.sin(theta_rad))
    else:
        z_coords = np.linspace(0, cfg.length, 50)
        p_simulated = np.zeros_like(z_coords)

    # Reta Teórica (Darcy-Weisbach + Hidrostática)
    re_num = cfg.reynolds_number
    if re_num < 2300:
        f_darcy = 64.0 / re_num
    elif re_num <= 100000:
        f_darcy = 0.3164 / (re_num ** 0.25)
    else:
        f_darcy = 0.0055 * (1.0 + (20000.0 / re_num) ** (1.0 / 3.0))

    u_avg = cfg.velocity_inlet
    dp_f_per_m = f_darcy * (1.0 / cfg.diameter) * (0.5 * cfg.density * (u_avg ** 2))
    dp_h_per_m = cfg.density * g_acc * math.sin(theta_rad)
    p_theoretical = (dp_f_per_m + dp_h_per_m) * (cfg.length - z_coords)

    # Plotagem do Gráfico Individual
    plt.figure(figsize=(9, 5.5))
    
    plt.plot(
        z_coords, p_simulated, 
        color='blue', linestyle='-', linewidth=2, 
        label=f'Simulado (OpenFOAM - {model_name} @ {inclination}°)'
    )
    plt.plot(
        z_coords, p_theoretical, 
        color='red', linestyle='--', linewidth=2, 
        label=f'Teórico (Darcy-Weisbach + Hydro @ {inclination}°)'
    )
    plt.axvline(
        x=z_target, color='green', linestyle=':', linewidth=1.5, 
        label=f'Ponto de Medição (z = {z_target:.2f} m)'
    )

    plt.xlabel('Posição z (m)', fontsize=11)
    plt.ylabel('Pressão Manométrica Total (Pa)', fontsize=11)
    plt.title(f'Perfil de Queda de Pressão ao Longo do Duto ({inclination}°)', fontsize=12, fontweight='bold')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(loc='upper right', fontsize=10)

    output_png = ROOT_DIR / "perfil_pressao.png"
    plt.savefig(output_png, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[Gráfico Individual] Salvo em: {output_png}")


def gerar_grafico_comparativo():
    """
    2. GRÁFICO COMPARATIVO (run_modelos.py -> comparacao_modelos_turbulencia.png)
    Plota as curvas de k-Epsilon E k-Omega SST juntas contra a Reta Teórica.
    """
    cfg = SimulationConfig()
    inclination = getattr(cfg, "inclination_deg", 0.0)
    theta_rad = math.radians(inclination)
    g_acc = 9.81

    profiles_dir = ROOT_DIR / "profiles"
    file_keps = profiles_dir / "perfil_kEpsilon.dat"
    file_komega = profiles_dir / "perfil_kOmegaSST.dat"

    plt.figure(figsize=(9, 5.5))
    z_coords = None

    # Curve 1: kEpsilon
    if file_keps.exists():
        data_keps = np.loadtxt(file_keps, comments="#")
        z_coords = data_keps[:, 0]
        p_kin = data_keps[:, 1]
        p_tot = (p_kin * cfg.density) + (cfg.density * g_acc * (cfg.length - z_coords) * math.sin(theta_rad))
        plt.plot(z_coords, p_tot, 's-', color='blue', linewidth=2, label=f'k-Epsilon ({inclination}°)')

    # Curve 2: kOmegaSST
    if file_komega.exists():
        data_komega = np.loadtxt(file_komega, comments="#")
        if z_coords is None:
            z_coords = data_komega[:, 0]
        p_kin = data_komega[:, 1]
        p_tot = (p_kin * cfg.density) + (cfg.density * g_acc * (cfg.length - z_coords) * math.sin(theta_rad))
        plt.plot(z_coords, p_tot, 'o-', color='orange', linewidth=2, label=f'k-Omega SST ({inclination}°)')

    # Curve 3: Reta Teórica de referência
    if z_coords is not None:
        re_num = cfg.reynolds_number
        if re_num < 2300:
            f_darcy = 64.0 / re_num
        elif re_num <= 100000:
            f_darcy = 0.3164 / (re_num ** 0.25)
        else:
            f_darcy = 0.0055 * (1.0 + (20000.0 / re_num) ** (1.0 / 3.0))

        u_avg = cfg.velocity_inlet
        dp_f_per_m = f_darcy * (1.0 / cfg.diameter) * (0.5 * cfg.density * (u_avg ** 2))
        dp_h_per_m = cfg.density * g_acc * math.sin(theta_rad)
        p_theoretical = (dp_f_per_m + dp_h_per_m) * (cfg.length - z_coords)

        plt.plot(
            z_coords, p_theoretical, 
            color='red', linestyle='--', linewidth=2, 
            label=f'Teórico (Darcy-Weisbach + Hydro @ {inclination}°)'
        )

    plt.xlabel('Posição z (m)', fontsize=11)
    plt.ylabel('Pressão Manométrica Total (Pa)', fontsize=11)
    plt.title(f'Comparação de Modelos de Turbulência vs Teoria ({inclination}°)', fontsize=12, fontweight='bold')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(loc='upper right', fontsize=10)

    output_png = ROOT_DIR / "comparacao_modelos_turbulencia.png"
    plt.savefig(output_png, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[Gráfico Comparativo] Salvo em: {output_png}")


if __name__ == "__main__":
    gerar_grafico_pressao()
    gerar_grafico_comparativo()