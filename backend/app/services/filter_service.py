"""
FilterService: Centraliza lógica de filtros para todas as rotas.

Responsabilidade única:
- Validar, normalizar e aplicar filtros
- Integrar com mappings (squad, checkout)
- Garantir consistência em todas as rotas
"""
from typing import Optional, Any
from dataclasses import dataclass

from ..services.redtrack.mappings import resolve_squad, resolve_checkout, resolve_product


@dataclass
class FilterParams:
    """Parâmetros de filtro normalizados."""
    period: str = "24h"
    source: Optional[str] = None  # Squad/Traffic source
    squad: Optional[str] = None
    checkout: Optional[str] = None
    product: Optional[str] = None
    offer: Optional[str] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None


class FilterService:
    """Serviço centralizado de filtros."""

    VALID_PERIODS = {"24h", "daily", "weekly", "monthly"}

    @staticmethod
    def normalize_string(value: Optional[str]) -> Optional[str]:
        """Normaliza string: trim + lowercase."""
        if not value:
            return None
        return str(value).strip().lower()

    @staticmethod
    def validate_period(period: str) -> str:
        """Valida período, retorna default se inválido."""
        if period in FilterService.VALID_PERIODS:
            return period
        return "24h"

    @staticmethod
    def resolve_squad_filter(squad: Optional[str]) -> Optional[str]:
        """Resolve squad para canônico via settings."""
        if not squad:
            return None
        raw = FilterService.normalize_string(squad)
        if not raw:
            return None

        resolved = resolve_squad(raw)
        return resolved if resolved != "unknown" else raw

    @staticmethod
    def resolve_checkout_filter(checkout: Optional[str]) -> Optional[str]:
        """Resolve checkout para canônico via settings."""
        if not checkout:
            return None
        raw = FilterService.normalize_string(checkout)
        if not raw:
            return None

        resolved = resolve_checkout(raw)
        return resolved if resolved != "unknown" else raw

    @staticmethod
    def resolve_product_filter(product: Optional[str]) -> Optional[str]:
        """Resolve product para canônico via settings."""
        if not product:
            return None
        raw = FilterService.normalize_string(product)
        if not raw:
            return None

        resolved = resolve_product(raw)
        return resolved if resolved != "unknown" else raw

    @classmethod
    def build_filters(
        cls,
        period: Optional[str] = None,
        source: Optional[str] = None,
        squad: Optional[str] = None,
        checkout: Optional[str] = None,
        product: Optional[str] = None,
        offer: Optional[str] = None,
        country: Optional[str] = None,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
    ) -> FilterParams:
        """
        Constrói filtros normalizados e resolvidos.

        Retorna FilterParams com valores validados, normalizados e mapeados.
        """
        return FilterParams(
            period=cls.validate_period(period or "24h"),
            source=cls.resolve_squad_filter(source or squad),  # Suporta ambos
            squad=cls.resolve_squad_filter(squad or source),
            checkout=cls.resolve_checkout_filter(checkout),
            product=cls.resolve_product_filter(product),
            offer=cls.normalize_string(offer),
            date_start=cls.normalize_string(date_start),
            date_end=cls.normalize_string(date_end),
        )

    @staticmethod
    def filters_to_dict(filters: FilterParams) -> dict:
        """Converte FilterParams para dict, removendo None values."""
        return {
            k: v for k, v in {
                "period": filters.period,
                "source": filters.source,
                "squad": filters.squad,
                "checkout": filters.checkout,
                "product": filters.product,
                "offer": filters.offer,
                "date_start": filters.date_start,
                "date_end": filters.date_end,
            }.items()
            if v is not None
        }


@dataclass
class ApiResponse:
    """Resposta padronizada de APIs."""
    data: Any
    meta: dict

    def to_dict(self) -> dict:
        """Converte para dicionário."""
        return {
            "data": self.data,
            "meta": self.meta,
        }


class ResponseBuilder:
    """Builder para respostas padronizadas."""

    @staticmethod
    def build_list_response(
        data: list,
        filters: FilterParams,
        total: Optional[int] = None,
    ) -> dict:
        """
        Constrói resposta padronizada para lista de dados.

        Exemplo:
        {
            "data": [...],
            "meta": {
                "filters": {...},
                "total": 42
            }
        }
        """
        return {
            "data": data,
            "meta": {
                "filters": FilterService.filters_to_dict(filters),
                "total": total or len(data),
            }
        }

    @staticmethod
    def build_single_response(
        data: dict,
        filters: FilterParams,
    ) -> dict:
        """Constrói resposta padronizada para um único objeto."""
        return {
            "data": data,
            "meta": {
                "filters": FilterService.filters_to_dict(filters),
            }
        }

