from datetime import date, timedelta

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Path, HTTPException, status
from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..schemas.metrics_schema import (
    HourlyMetricResponse,
    SummaryResponse,
    CheckoutSummaryItem,
    ProductSummaryItem,
    SquadSummaryItem,
    ConversionBreakdownItem,
    OfferResponse,
    ChartComparisonResponse,
)
from ..schemas.auth_schema import LoginRequest, TokenResponse, CurrentUserResponse, TokenPayload
from ..services.redis_service import get_summary_cached, get_hourly_cached
from ..services.metrics_service import (
    get_metrics_by_period,
    get_checkout_summary,
    get_product_summary,
    get_squad_checkout_summary,
    get_conversion_breakdown,
)
from ..services.offer_service import sync_fetch_offer_data
from ..services.filter_service import FilterService
from ..services.auth_service import AuthService
from ..core.auth_middleware import get_current_user, require_admin
from ..core.user_scope import resolve_user_squad_scope

# Routers
router = APIRouter()
metrics_router = APIRouter(prefix="/metrics", tags=["metrics"], dependencies=[Depends(get_current_user)])
auth_router = APIRouter(prefix="/auth", tags=["auth"])

VALID_PERIODS = {"24h", "daily", "weekly", "monthly"}

def _validate_period(period: str) -> str:
    if period not in VALID_PERIODS:
        raise HTTPException(
            status_code=422,
            detail=f"Período inválido: {period}. Use um dos: {', '.join(VALID_PERIODS)}"
        )
    return period

def _enforce_squad_filter_permission(current_user: TokenPayload, source: str | None = None, squad: str | None = None) -> None:
    if current_user.role != "admin" and (source or squad):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Filtro de squad permitido apenas para administradores",
        )


def _parse_iso_date(value: str | None, field_name: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{field_name} invalido. Use YYYY-MM-DD") from exc


def _resolve_period_range(anchor_date: date, period: str) -> tuple[date, date]:
    if period == "weekly":
        return anchor_date - timedelta(days=6), anchor_date
    if period == "monthly":
        return anchor_date - timedelta(days=29), anchor_date
    return anchor_date, anchor_date

def _get_value(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _as_float(value, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return float(default)

def _empty_summary_payload():
    return {
        "today": {"cost": 0, "profit": 0, "revenue": 0, "checkout": 0, "roi": 0},
        "yesterday": {"cost": 0, "profit": 0, "revenue": 0, "checkout": 0, "roi": 0},
        "comparison": {"cost_change": 0, "profit_change": 0, "revenue_change": 0, "checkout_change": 0, "roi_change": 0},
    }


def _resolve_user_scope(current_user: TokenPayload) -> str | None:
    return current_user.sector or AuthService.resolve_user_sector(current_user.username)


def _resolve_effective_source(current_user: TokenPayload, source: str | None) -> str | None:
    if current_user.role == "admin":
        return source
    return _resolve_user_scope(current_user)


def _resolve_effective_squad(current_user: TokenPayload, squad: str | None) -> str | None:
    if current_user.role == "admin":
        return squad
    return _resolve_user_scope(current_user)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@metrics_router.get(
    "/summary",
    summary="Retorna KPIs agregados",
    description=(
        "Retorna os valores agregados de custo, lucro e ROI.\n\n"
        "- `source` (opcional): filtra os dados por origem de tráfego.\n"
        "- `checkout` (opcional): filtra por tipo de checkout.\n"
        "- `product` (opcional): filtra por produto.\n"
        "- Sem autenticação no estado atual do projeto."
    ),
    response_model=SummaryResponse,
    response_description="KPIs agregados para os cards principais do dashboard",
    responses={
        200: {
            "description": "Métricas agregadas retornadas com sucesso",
            "content": {
                "application/json": {
                    "example": {"cost": 169.21, "profit": 60.79, "roi": 0.36}
                }
            },
        }
    },
)
def get_summary(
        period: str = Query(
            default="24h",
            description="Período: 24h, daily, weekly, monthly",
            examples=["24h", "daily", "weekly", "monthly"],
        ),
        source: str | None = Query(
            default=None,
            description="Squad/Origem de tráfego para filtrar os dados (ex.: yts, ytf)",
            examples=["yts", "ytf"],
        ),
        checkout: str | None = Query(
            default=None,
            description="Filtro opcional de checkout (ex.: Cartpanda, Clickbank)",
        ),
        product: str | None = Query(
            default=None,
            description="Filtro opcional de produto",
        ),
        force_refresh: bool = Query(
            default=False,
            description="Quando true, ignora cache e recalcula o summary atualizado",
        ),
        db: Session = Depends(get_db),
        current_user: TokenPayload = Depends(get_current_user),
):

    _validate_period(period)
    _enforce_squad_filter_permission(current_user, source=source)
    # Validação explícita do parâmetro period
    valid_periods = {"24h", "daily", "weekly", "monthly"}
    if period not in valid_periods:
        raise HTTPException(status_code=422, detail=f"Período inválido: {period}. Use um dos: {', '.join(valid_periods)}")

    # Normalizar filtros usando FilterService
    if current_user.role == "admin":
        effective_source = source
    else:
        # Para usuário comum, resolve todos os squads permitidos pelo setor
        squads = resolve_user_squad_scope(current_user.sector or current_user.username)
        if squads and len(squads) > 1:
            # Se houver mais de um squad, envia o setor (ex: 'native', 'youtube') para o filtro, que já agrega corretamente
            effective_source = current_user.sector or current_user.username
        else:
            # Se só houver um squad, envia ele diretamente
            effective_source = squads[0] if squads else None
    filters = FilterService.build_filters(period=period, source=effective_source, checkout=checkout, product=product)

    result = get_summary_cached(
        db,
        filters.source,
        filters.period,
        checkout=filters.checkout,
        product=filters.product,
        force_refresh=force_refresh,
    )

    if not isinstance(result, dict) or "today" not in result:
        result = _empty_summary_payload()

    summary_data = {
        "today": {
            "cost": float((result.get("today") or {}).get("cost") or 0),
            "profit": float((result.get("today") or {}).get("profit") or 0),
            "revenue": float((result.get("today") or {}).get("revenue") or 0),
            "checkout": float((result.get("today") or {}).get("checkout") or 0),
            "roi": float((result.get("today") or {}).get("roi") or 0),
        },
        "yesterday": {
            "cost": float((result.get("yesterday") or {}).get("cost") or 0),
            "profit": float((result.get("yesterday") or {}).get("profit") or 0),
            "revenue": float((result.get("yesterday") or {}).get("revenue") or 0),
            "checkout": float((result.get("yesterday") or {}).get("checkout") or 0),
            "roi": float((result.get("yesterday") or {}).get("roi") or 0),
        },
        "comparison": {
            "cost_change": float((result.get("comparison") or {}).get("cost_change") or 0),
            "profit_change": float((result.get("comparison") or {}).get("profit_change") or 0),
            "revenue_change": float((result.get("comparison") or {}).get("revenue_change") or 0),
            "checkout_change": float((result.get("comparison") or {}).get("checkout_change") or 0),
            "roi_change": float((result.get("comparison") or {}).get("roi_change") or 0),
        },
    }
    return summary_data

@metrics_router.get(
    "/hourly",
    summary="Retorna métricas por hora",
    description=(
        "Retorna uma série temporal por hora com custo, lucro e ROI das ultimas 24 horas para gráficos.\n\n"
        "- `source` (opcional): filtra por origem de tráfego.\n"
        "- Sem autenticação no estado atual do projeto."
    ),
    response_model=list[HourlyMetricResponse],
    response_description="Série temporal por hora para gráficos do dashboard",
    responses={
        200: {
            "description": "Lista de pontos horários",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "slot": "2026-03-28T14:00:00",
                            "day": "today",
                            "hour": "14",
                            "checkout_conversion": 18.0,
                            "cost": 12.1,
                            "profit": 4.2,
                            "revenue": 45.0,
                            "roi": 0.35,
                        },
                        {
                            "slot": "2026-03-27T23:00:00",
                            "day": "yesterday",
                            "hour": "23",
                            "checkout_conversion": 9.0,
                            "cost": 10.4,
                            "profit": 3.1,
                            "revenue": 30.0,
                            "roi": 0.30,
                        },
                    ]
                }
            },
        }
    },
)
def get_hourly(
    source: str | None = Query(
        default=None,
        description="Squad/Origem de tráfego para filtrar os dados (ex.: yts, ytf)",
        examples=["yts", "ytf"],
    ),
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
):
    _enforce_squad_filter_permission(current_user, source=source)
    filters = FilterService.build_filters(source=_resolve_effective_source(current_user, source))
    rows = get_hourly_cached(db, filters.source)

    data = [
        {
            "squad": str(_get_value(row, "squad", "")),
            "slot": str(_get_value(row, "slot", "")),
            "day": str(_get_value(row, "day", "")),
            "hour": str(_get_value(row, "hour", "")),
            "checkout_conversion": _as_float(_get_value(row, "checkout_conversion", 0)),
            "cost": _as_float(_get_value(row, "cost", 0)),
            "profit": _as_float(_get_value(row, "profit", 0)),
            "revenue": _as_float(_get_value(row, "revenue", 0)),
            "roi": _as_float(_get_value(row, "roi", 0)) * 100,
        }
        for row in rows
    ]

    return data

@metrics_router.get(
    "/hourly/period",
    summary="Retorna métricas por período",
    description=(
        "Retorna uma série temporal por hora para diferentes períodos.\n\n"
        "- `period`: 24h, daily, weekly, ou monthly\n"
        "- `source` (opcional): filtra por origem de tráfego."
    ),
    response_model=list[HourlyMetricResponse],
    response_description="Série temporal por período para gráficos",
)
def get_hourly_period(
    period: str = Query(
        default="24h",
        description="Período: 24h, daily, weekly, ou monthly",
        examples=["24h", "daily", "weekly", "monthly"],
    ),
    source: str | None = Query(
        default=None,
        description="Squad/Origem de tráfego para filtrar os dados",
        examples=["yts", "ytf"],
    ),
    checkout: str | None = Query(
        default=None,
        description="Filtro opcional de checkout (ex.: Cartpanda, Clickbank)",
    ),
    product: str | None = Query(
        default=None,
        description="Filtro opcional de produto",
    ),
    date_start: str | None = Query(default=None, description="Data inicial opcional (YYYY-MM-DD)"),
    date_end: str | None = Query(default=None, description="Data final opcional (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
):
    _validate_period(period)
    _enforce_squad_filter_permission(current_user, source=source)
    """
    Retorna métricas agregadas por hora para um período específico.
    
    - 24h: últimas 24 horas
    - daily: hoje inteiro
    - weekly: últimos 7 dias
    - monthly: últimos 30 dias
    """
    filters = FilterService.build_filters(
        period=period,
        source=_resolve_effective_source(current_user, source),
        checkout=checkout,
        product=product,
        date_start=date_start,
        date_end=date_end,
    )

    parsed_start = _parse_iso_date(filters.date_start, "date_start")
    parsed_end = _parse_iso_date(filters.date_end, "date_end")

    if (parsed_start and not parsed_end) or (parsed_end and not parsed_start):
        raise HTTPException(status_code=422, detail="Envie date_start e date_end juntos")

    rows = get_metrics_by_period(
        db,
        start_date=parsed_start,
        end_date=parsed_end,
        squad=filters.source,
        checkout=filters.checkout,
        product=filters.product,
        period=period,
    )

    # Para weekly/monthly, garantir compatibilidade de estrutura para o frontend (série contínua de dias, hour='0')
    if period in ("weekly", "monthly"):
        rows = sorted(rows, key=lambda r: getattr(r, "metric_date", ""))
    data = [
        {
            "squad": str(_get_value(row, "squad", "")),
            "metric_date": str(_get_value(row, "metric_date", "") or ""),
            "slot": str(_get_value(row, "slot", "")),
            "day": str(_get_value(row, "day", "")),
            "hour": str(_get_value(row, "hour", "")),
            "checkout_conversion": _as_float(_get_value(row, "checkout_conversion", 0)),
            "cost": _as_float(_get_value(row, "cost", 0)),
            "profit": _as_float(_get_value(row, "profit", 0)),
            "revenue": _as_float(_get_value(row, "revenue", 0)),
            "roi": _as_float(_get_value(row, "roi", 0)) * 100,
        }
        for row in rows
    ]

    return data


@metrics_router.get(
    "/by-checkout",
            response_model=list[CheckoutSummaryItem],
    summary="Retorna conversão por checkout (Cartpanda, Clickbank)",
    description=(
        "Retorna as métricas de conversão agrupadas por checkout.\n\n"
        "- `period`: 24h, daily, weekly, monthly\n"
        "- `source` (opcional): filtra por squad"
    ),
    responses={
        200: {
            "description": "Conversões por checkout",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "checkout": "Cartpanda",
                            "initiate_checkout": 150,
                            "purchase": 45,
                            "checkout_conversion": 30.0
                        },
                        {
                            "checkout": "Clickbank",
                            "initiate_checkout": 80,
                            "purchase": 20,
                            "checkout_conversion": 25.0
                        }
                    ]
                }
            },
        }
    },
)
def get_by_checkout(
    period: str = Query(
        default="24h",
        description="Período: 24h, daily, weekly, monthly",
        examples=["24h", "daily", "weekly", "monthly"],
    ),
    source: str | None = Query(
        default=None,
        description="Squad para filtrar os dados (ex.: yts, ytf)",
        examples=["yts", "ytf"],
    ),
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
):
    _validate_period(period)
    _enforce_squad_filter_permission(current_user, source=source)
    """
    Retorna conversão por checkout (Cartpanda vs Clickbank).
    """
    filters = FilterService.build_filters(period=period, source=_resolve_effective_source(current_user, source))
    data = get_checkout_summary(db, filters.source, filters.period)
    return data


@metrics_router.get(
    "/by-product",
            response_model=list[ProductSummaryItem],
    summary="Retorna conversão por produto",
    description=(
        "Retorna as métricas de conversão agrupadas por produto.\n\n"
        "- `period`: 24h, daily, weekly, monthly\n"
        "- `source` (opcional): filtra por squad"
    ),
    responses={
        200: {
            "description": "Conversões por produto",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "product": "ErosLift",
                            "initiate_checkout": 120,
                            "purchase": 36,
                            "checkout_conversion": 30.0
                        },
                        {
                            "product": "VitaBoost",
                            "initiate_checkout": 100,
                            "purchase": 25,
                            "checkout_conversion": 25.0
                        }
                    ]
                }
            },
        }
    },
)
def get_by_product(
    period: str = Query(
        default="24h",
        description="Período: 24h, daily, weekly, monthly",
        examples=["24h", "daily", "weekly", "monthly"],
    ),
    source: str | None = Query(
        default=None,
        description="Squad para filtrar os dados (ex.: yts, ytf)",
        examples=["yts", "ytf"],
    ),
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
):
    _validate_period(period)
    _enforce_squad_filter_permission(current_user, source=source)
    """
    Retorna conversão por produto.
    """
    filters = FilterService.build_filters(period=period, source=_resolve_effective_source(current_user, source))
    data = get_product_summary(db, filters.source, filters.period)
    return data


@metrics_router.get(
    "/by-squad",
            response_model=list[SquadSummaryItem],
    summary="Retorna métricas por squad",
    description=(
        "Retorna as métricas de custo, lucro, ROI e conversão agrupadas por squad.\n\n"
        "- `period`: 24h, daily, weekly, monthly"
    ),
    responses={
        200: {
            "description": "Métricas por squad",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "squad": "FBR",
                            "cost": 5000.00,
                            "profit": 2500.00,
                            "revenue": 7500.00,
                            "checkout_conversion": 28.5,
                            "roi": 0.50
                        }
                    ]
                }
            },
        }
    },
)
def get_by_squad(
    period: str = Query(
        default="24h",
        description="Período: 24h, daily, weekly, monthly",
        examples=["24h", "daily", "weekly", "monthly"],
    ),
    db: Session = Depends(get_db),
    _: TokenPayload = Depends(require_admin),
):
    """
    Retorna métricas agregadas por squad.
    """
    filters = FilterService.build_filters(period=period)
    data = get_squad_checkout_summary(db, filters.period)
    return data


@metrics_router.get(
    "/conversion-breakdown",
    summary="Retorna conversão por combinação de squad, checkout e produto",
    description=(
        "Retorna volume e taxa de conversão com filtros opcionais combináveis.\n\n"
        "- `period`: 24h, daily, weekly, monthly\n"
        "- `squad` (opcional)\n"
        "- `checkout` (opcional)\n"
        "- `product` (opcional)"
    ),
    response_model=list[ConversionBreakdownItem],
)
def get_conversion_breakdown_route(
    period: str = Query(
        default="24h",
        description="Período: 24h, daily, weekly, monthly",
        examples=["24h", "daily", "weekly", "monthly"],
    ),
    squad: str | None = Query(default=None, description="Filtro opcional de squad (ex.: yts, ytf)"),
    checkout: str | None = Query(default=None, description="Filtro opcional de checkout (ex.: Cartpanda, Clickbank)"),
    product: str | None = Query(default=None, description="Filtro opcional de produto"),
    date_start: str | None = Query(default=None, description="Data inicial opcional (YYYY-MM-DD)"),
    date_end: str | None = Query(default=None, description="Data final opcional (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
):
    _enforce_squad_filter_permission(current_user, squad=squad)
    effective_squad = _resolve_effective_squad(current_user, squad)
    filters = FilterService.build_filters(
        period=period,
        squad=effective_squad,
        checkout=checkout,
        product=product,
        date_start=date_start,
        date_end=date_end,
    )

    parsed_start = _parse_iso_date(filters.date_start, "date_start")
    parsed_end = _parse_iso_date(filters.date_end, "date_end")

    if (parsed_start and not parsed_end) or (parsed_end and not parsed_start):
        raise HTTPException(status_code=422, detail="Envie date_start e date_end juntos")

    data = get_conversion_breakdown(
        db,
        period=filters.period,
        squad=filters.squad,
        checkout=filters.checkout,
        product=filters.product,
        date_start=parsed_start,
        date_end=parsed_end,
    )
    return data


@metrics_router.get(
    "/charts/compare",
    summary="Compara dois períodos para os gráficos",
    description=(
        "Retorna dados comparativos de gráficos para dois períodos.\n\n"
        "- Para `period` em ['24h', 'daily']: use `base_date` e `compare_date` (YYYY-MM-DD)\n"
        "- Para `period` em ['weekly', 'monthly']: periodo comparará automaticamente períodos anteriores\n"
        "- `base_date`: data base para comparação ou período atual (YYYY-MM-DD)\n"
        "- `compare_date`: data para comparar (YYYY-MM-DD)\n"
        "- `period`: período para a comparação (24h, daily, weekly, monthly)\n"
        "- filtros opcionais: `source`, `checkout`, `product`"
    ),
    response_model=ChartComparisonResponse,
)
def get_charts_compare(
    base_date: str = Query(..., description="Data base para comparacao (YYYY-MM-DD)"),
    compare_date: str = Query(..., description="Data comparada (YYYY-MM-DD)"),
    period: str = Query(default="daily", description="Período: 24h, daily, weekly, ou monthly"),
    source: str | None = Query(default=None, description="Squad/Origem opcional"),
    checkout: str | None = Query(default=None, description="Filtro opcional de checkout"),
    product: str | None = Query(default=None, description="Filtro opcional de produto"),
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
):
    _validate_period(period)
    _enforce_squad_filter_permission(current_user, source=source)
    effective_source = _resolve_effective_source(current_user, source)
    filters = FilterService.build_filters(
        period=period,
        source=effective_source,
        checkout=checkout,
        product=product,
    )

    parsed_base = _parse_iso_date(base_date, "base_date")
    parsed_compare = _parse_iso_date(compare_date, "compare_date")

    if parsed_base is None or parsed_compare is None:
        raise HTTPException(status_code=422, detail="base_date e compare_date devem ser fornecidos e validos.")

    base_start, base_end = _resolve_period_range(parsed_base, period)
    compare_start, compare_end = _resolve_period_range(parsed_compare, period)

    base_hourly_rows = get_metrics_by_period(
        db,
        start_date=base_start,
        end_date=base_end,
        squad=filters.source,
        checkout=filters.checkout,
        product=filters.product,
        period=period,
    )
    compare_hourly_rows = get_metrics_by_period(
        db,
        start_date=compare_start,
        end_date=compare_end,
        squad=filters.source,
        checkout=filters.checkout,
        product=filters.product,
        period=period,
    )

    def _to_hourly_payload(rows: list) -> list[dict[str, object]]:
        return [
            {
                "squad": str(_get_value(row, "squad", "")),
                "metric_date": str(_get_value(row, "metric_date", "") or ""),
                "slot": str(_get_value(row, "slot", "")),
                "day": str(_get_value(row, "day", "")),
                "hour": str(_get_value(row, "hour", "")),
                "checkout_conversion": _as_float(_get_value(row, "checkout_conversion", 0)),
                "cost": _as_float(_get_value(row, "cost", 0)),
                "profit": _as_float(_get_value(row, "profit", 0)),
                "revenue": _as_float(_get_value(row, "revenue", 0)),
                "roi": _as_float(_get_value(row, "roi", 0)) * 100,
            }
            for row in rows
        ]

    base_conversion = get_conversion_breakdown(
        db,
        period=period,
        squad=filters.squad,
        checkout=filters.checkout,
        product=filters.product,
        date_start=base_start,
        date_end=base_end,
    )
    compare_conversion = get_conversion_breakdown(
        db,
        period=period,
        squad=filters.squad,
        checkout=filters.checkout,
        product=filters.product,
        date_start=compare_start,
        date_end=compare_end,
    )

    return {
        "base_date": parsed_base.isoformat(),
        "compare_date": parsed_compare.isoformat(),
        "base": {
            "date": parsed_base.isoformat(),
            "hourly": _to_hourly_payload(base_hourly_rows),
            "conversion_breakdown": base_conversion,
        },
        "compare": {
            "date": parsed_compare.isoformat(),
            "hourly": _to_hourly_payload(compare_hourly_rows),
            "conversion_breakdown": compare_conversion,
        },
    }


@metrics_router.get(
    "/cartpanda/offer/{offer_id}",
    summary="Busca dados de uma oferta Cartpanda",
    description=(
        "Busca informações de uma oferta Cartpanda específica do Redtrack.\n\n"
        "- `offer_id`: ID da oferta a buscar\n"
        "- Retorna os dados completos da oferta ou erro 404 se não encontrada"
    ),
    response_model=OfferResponse,
    responses={
        200: {
            "description": "Dados da oferta retornados com sucesso",
            "content": {
                "application/json": {
                    "example": {
                        "offer_id": "123456",
                        "name": "Minha Oferta Cartpanda",
                        "status": "active",
                        "data": {
                            "id": "123456",
                            "name": "Minha Oferta Cartpanda",
                            "status": "active",
                            # ... outros dados da oferta ...
                        }
                    }
                }
            },
        },
        404: {"description": "Oferta não encontrada ou requisição inválida"},
    },
)
def get_cartpanda_offer(
    offer_id: str = Path(
        ...,
        description="ID da oferta Cartpanda a buscar",
        examples=["123456"],
    )
):
    """
    Busca dados de uma oferta Cartpanda no Redtrack.
    
    Quando o checkout é Cartpanda, esse endpoint busca os detalhes completos
    da oferta usando o offer_id armazenado nas métricas.
    """
    if not offer_id or not offer_id.strip():
        return {
            "offer_id": "",
            "name": "N/A",
            "status": "invalid",
            "data": {"error": "offer_id vazio ou inválido"}
        }
    
    # Chamar o serviço para buscar dados da oferta
    offer_data = sync_fetch_offer_data(offer_id)
    
    if not offer_data:
        return {
            "offer_id": offer_id,
            "name": "N/A",
            "status": "not_found",
            "data": {"error": f"Oferta {offer_id} não encontrada no Redtrack"}
        }
    
    # Extrair campos úteis da resposta
    name = "N/A"
    if isinstance(offer_data, dict):
        name = offer_data.get("name") or offer_data.get("offer_name") or "N/A"
    
    return {
        "offer_id": offer_id,
        "name": name,
        "status": "found",
        "data": offer_data
    }

# ✅ ROTA DE LOGIN (pública - sem proteção)
@router.post("/login", response_model=TokenResponse, tags=["auth"])
@auth_router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    """
    Endpoint de login

    Valida credenciais do usuário admin e retorna um token JWT válido por 72 horas.

    **Credenciais de teste:**
    - Username: Admin
    - Password: #agenciatitan2026
    """
    user = AuthService.authenticate_user(db, credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos",
        )

    token, expires_in = AuthService.create_access_token(user)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in
    )


@auth_router.get("/me", response_model=CurrentUserResponse)
async def me(current_user: Annotated[TokenPayload, Depends(get_current_user)]):
    return CurrentUserResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        sector=current_user.sector or AuthService.resolve_user_sector(current_user.username),
    )


# ✅ Adicionar rotas de autenticação ao router principal
router.include_router(auth_router)
router.include_router(metrics_router)
