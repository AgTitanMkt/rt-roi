"""
Models: Dataclasses compartilhadas para conversão e agregação.

Responsabilidade única: Definir estruturas de dados sem lógica de negócio.
"""
from dataclasses import dataclass, field


@dataclass
class ConversionMetrics:
    """Métricas de conversão agregadas."""
    initiate_checkout: int = 0
    purchase: int = 0

    @property
    def conversion_rate(self) -> float:
        if self.initiate_checkout == 0:
            return 0.0
        return (self.purchase / self.initiate_checkout) * 100


@dataclass
class CampaignInfo:
    """Informações extraídas da nomenclatura da campanha."""
    campaign_id: str
    campaign_name: str
    offer_id: str | None = None
    squad: str = "unknown"
    checkout: str = "unknown"  # Cartpanda, Clickbank, etc.
    product: str = "unknown"   # ErosLift, etc.
    niche: str = "unknown"     # ED, etc.
    platform: str = "unknown"  # FB, etc.


@dataclass
class AggregatedConversions:
    """Conversões agregadas por diferentes dimensões."""
    by_campaign: dict[str, ConversionMetrics] = field(default_factory=dict)
    campaign_info: dict[str, CampaignInfo] = field(default_factory=dict)
    by_squad: dict[str, ConversionMetrics] = field(default_factory=dict)
    by_checkout: dict[str, ConversionMetrics] = field(default_factory=dict)
    by_product: dict[str, ConversionMetrics] = field(default_factory=dict)
    total: ConversionMetrics = field(default_factory=ConversionMetrics)

