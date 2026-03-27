from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    Status: str = Field(..., examples=["Online"], description="Status geral da API")


class MetricsData(BaseModel):
    cost: float | None = Field(..., examples=[169.21], description="Custo total agregado")
    profit: float | None = Field(..., examples=[60.79], description="Lucro total agregado")
    revenue: float | None = Field(..., examples=[60.79], description="Faturamento total agregado")
    roi: float | None = Field(..., examples=[0.36], description="ROI agregado")


class ComparisonData(BaseModel):
    cost_change: float | None = Field(..., examples=[10.5], description="Variação percentual do custo em relação a ontem")
    profit_change: float | None = Field(..., examples=[5.3], description="Variação percentual do lucro em relação a ontem")
    roi_change: float | None = Field(..., examples=[2.1], description="Variação percentual do ROI em relação a ontem")
    revenue_change: float | None = Field(..., examples=[2.1], description="Variação percentual do Faturamento em relação a ontem")


class SummaryResponse(BaseModel):
    today: MetricsData = Field(..., description="Métricas de hoje")
    yesterday: MetricsData = Field(..., description="Métricas de ontem")
    comparison: ComparisonData = Field(..., description="Variação percentual entre hoje e ontem")


class HourlyMetricResponse(BaseModel):
    hour: str = Field(..., examples=["14"], description="Hora do dia (formato HH, 0-23)")
    cost: float = Field(..., examples=[12.1], description="Custo agregado da hora")
    profit: float = Field(..., examples=[4.2], description="Lucro agregado da hora")
    revenue: float = Field(..., examples=[45.0], description="Receita agregada da hora")
    roi: float = Field(..., examples=[0.35], description="ROI agregado da hora")
