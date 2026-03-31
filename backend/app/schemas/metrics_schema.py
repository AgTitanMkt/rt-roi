from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    Status: str = Field(..., examples=["Online"], description="Status geral da API")


class MetricsData(BaseModel):
    cost: float | None = Field(..., examples=[169.21], description="Custo total agregado")
    profit: float | None = Field(..., examples=[60.79], description="Lucro total agregado")
    revenue: float | None = Field(..., examples=[60.79], description="Faturamento total agregado")
    checkout: float | None = Field(..., examples=[45.0], description="Checkout total agregado")
    roi: float | None = Field(..., examples=[0.36], description="ROI agregado")


class ComparisonData(BaseModel):
    cost_change: float | None = Field(..., examples=[10.5], description="Variação percentual do custo em relação a ontem")
    profit_change: float | None = Field(..., examples=[5.3], description="Variação percentual do lucro em relação a ontem")
    checkout_change: float | None = Field(..., examples=[2.7], description="Variação percentual do checkout em relação a ontem")
    roi_change: float | None = Field(..., examples=[2.1], description="Variação percentual do ROI em relação a ontem")
    revenue_change: float | None = Field(..., examples=[2.1], description="Variação percentual do Faturamento em relação a ontem")


class SummaryResponse(BaseModel):
    today: MetricsData = Field(..., description="Métricas de hoje")
    yesterday: MetricsData = Field(..., description="Métricas de ontem")
    comparison: ComparisonData = Field(..., description="Variação percentual entre hoje e ontem")


class HourlyMetricResponse(BaseModel):
    squad: str = Field("", examples=["FBR"], description="Squad associado ao filtro aplicado")
    slot: str = Field(..., examples=["2026-03-28T14:00:00"], description="Timestamp da janela horaria em America/Sao_Paulo")
    day: str = Field(..., examples=["today", "yesterday"], description="Identifica se o ponto pertence a hoje ou ontem")
    hour: str = Field(..., examples=["14"], description="Hora do dia (formato HH, 0-23)")
    checkout_conversion: float = Field(..., examples=[45.0], description="Total de checkout conversion na hora")
    cost: float = Field(..., examples=[12.1], description="Custo agregado da hora")
    profit: float = Field(..., examples=[4.2], description="Lucro agregado da hora")
    revenue: float = Field(..., examples=[45.0], description="Receita agregada da hora")
    roi: float = Field(..., examples=[0.35], description="ROI agregado da hora")


class CheckoutSummaryItem(BaseModel):
    checkout: str = Field(..., examples=["Cartpanda"], description="Nome do checkout")
    initiate_checkout: int = Field(..., examples=[150], description="Total de initiate checkout")
    purchase: int = Field(..., examples=[45], description="Total de purchase")
    checkout_conversion: float = Field(..., examples=[30.0], description="Taxa de conversao em %")


class ProductSummaryItem(BaseModel):
    product: str = Field(..., examples=["ErosLift"], description="Nome do produto")
    initiate_checkout: int = Field(..., examples=[120], description="Total de initiate checkout")
    purchase: int = Field(..., examples=[36], description="Total de purchase")
    checkout_conversion: float = Field(..., examples=[30.0], description="Taxa de conversao em %")


class SquadSummaryItem(BaseModel):
    squad: str = Field(..., examples=["FBR"], description="Squad")
    cost: float = Field(..., examples=[5000.0], description="Custo agregado")
    profit: float = Field(..., examples=[2500.0], description="Lucro agregado")
    revenue: float = Field(..., examples=[7500.0], description="Receita agregada")
    checkout_conversion: float = Field(..., examples=[28.5], description="Taxa de conversao em %")
    roi: float = Field(..., examples=[0.5], description="ROI agregado")

