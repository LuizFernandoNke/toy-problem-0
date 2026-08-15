from pydantic import BaseModel, Field

class SimulationConfig(BaseModel):
    # Identificação da simulação
    case_name: str = "PipeFlow_Case0"
    
    # Propriedades da Geometria (Tubo)
    diameter: float = Field(default=0.05, gt=0, description="Diâmetro em metros")
    length: float = Field(default=2.0, gt=0, description="Comprimento em metros")
    
    # Condições de Escoamento
    velocity_inlet: float = Field(default=1.5, gt=0, description="Velocidade de entrada em m/s")
    kinematic_viscosity: float = Field(default=1e-6, gt=0, description="Viscosidade cinemática (nu)")
    density: float = Field(default=998.2, gt=0, description="Massa específica do fluido kg/m3")
    
    # Modelo de Turbulência
    turbulence_model: str = "kEpsilon"  # ex: kEpsilon, kOmegaSST
    
    @property
    def reynolds_number(self) -> float:
        """Calcula o Número de Reynolds automaticamente."""
        return (self.velocity_inlet * self.diameter) / self.kinematic_viscosity

if __name__ == "__main__":
    # Teste rápido do modelo
    cfg = SimulationConfig()
    print(" Configuração carregada com sucesso!")
    print(f"Caso: {cfg.case_name}")
    print(f"Número de Reynolds: {cfg.reynolds_number:.2f}")