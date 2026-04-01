"""
Aggregators: Centraliza lógica de agregação de métricas de conversão.

Responsabilidade única: agregar métricas por dimensões (squad, checkout, produto, etc)
"""
from .models import ConversionMetrics, AggregatedConversions


def ensure_metric_key(metrics_dict: dict[str, ConversionMetrics], key: str) -> None:
    """Garante que uma chave existe no dicionário de métricas."""
    if key not in metrics_dict:
        metrics_dict[key] = ConversionMetrics()


def increment_conversion_metric(
    metric: ConversionMetrics,
    is_purchase: bool,
    count: int,
) -> None:
    """Incrementa métrica de conversão (purchase ou initiate checkout)."""
    if is_purchase:
        metric.purchase += count
    else:
        metric.initiate_checkout += count


def aggregate_by_dimension(
    aggregated: AggregatedConversions,
    dimension_dict: dict[str, ConversionMetrics],
    key: str,
    is_purchase: bool,
    count: int,
) -> None:
    """
    Agrega métrica em uma dimensão específica.

    Útil para evitar repetição ao agregar por squad, checkout, produto, etc.
    """
    ensure_metric_key(dimension_dict, key)
    increment_conversion_metric(dimension_dict[key], is_purchase, count)
    increment_conversion_metric(aggregated.total, is_purchase, count)

