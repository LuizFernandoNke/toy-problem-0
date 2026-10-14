from pydantic import BaseModel, Field

class SimulationConfig(BaseModel):
    # case properties
    case_name: str = "PipeFlow_Case0"

    # geometry properties
    diameter: float = Field(default=0.05, gt=0, description="diameter in meters")
    length: float = Field(default=2.0, gt=0, description="length in meters")
    
    # ==============================================================================
    # INCLINAÇÃO DO DUTO (ÂNGULO EM GRAUS)
    # -  0.0 graus : O escoamento é totalmente horizontal.
    # - 30.0, 45.0, 60.0 graus : A frente do tubo (saída/outlet) ergue-se nestes 
    #                            graus em relação à entrada (inlet).
    # - 90.0 graus : O escoamento passa a ser totalmente vertical (subida).
    # - Valores negativos (ex: -30.0) : Escoamento em declive (descida).
    # 
    # Altere apenas o valor de 'default' abaixo para mudar a inclinação:
    # ==============================================================================
    inclination_deg: float = Field(
        default=0, # Altere apenas aqui
        ge=-90.0, 
        le=90.0, 
        description="pipe inclination angle in degrees (-90 to 90)"
    )

    # flow properties
    velocity_inlet: float = Field(default=0.2, gt=0, description="inlet velocity in m/s")
    kinematic_viscosity: float = Field(default=1e-6, gt=0, description="kinematic viscosity (nu)")
    density: float = Field(default=998.2, gt=0, description="density of the fluid in kg/m3")

    # turbulence model (optional, default is kEpsilon)
    turbulence_model: str = "kOmegaSST"

    # mesh size
    mesh_factor: float = 0.9

    @property
    def reynolds_number(self) -> float:
        u_avg = self.velocity_inlet  # Use velocity_inlet for U_max
        return (u_avg * self.diameter) / self.kinematic_viscosity


if __name__ == "__main__":
    # model test
    cfg = SimulationConfig()
    print("Simulation configuration ready:")
    print(f"Case: {cfg.case_name}")
    print(f"Reynolds Number: {cfg.reynolds_number:.2f}")
    print(f"Inclination Angle: {cfg.inclination_deg}°")