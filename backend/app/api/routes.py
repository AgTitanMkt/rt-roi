from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..schemas.metrics_schema import HourlyMetricResponse, SummaryResponse
from ..services.redis_service import get_summary_cached, get_hourly_cached
from ..services.metrics_service import get_metrics_by_period

router = APIRouter(prefix="/metrics", tags=["metrics"])

def _get_value(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def _empty_summary_payload():
    return {
        "today": {"cost": 0, "profit": 0, "revenue": 0, "roi": 0},
        "yesterday": {"cost": 0, "profit": 0, "revenue": 0, "roi": 0},
        "comparison": {"cost_change": 0, "profit_change": 0, "revenue_change": 0, "roi_change": 0},
    }

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get(
    "/summary",
    summary="Retorna KPIs agregados",
    description=(
        "Retorna os valores agregados de custo, lucro e ROI.\n\n"
        "- `source` (opcional): filtra os dados por origem de tráfego.\n"
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
            description="Origem de tráfego para filtrar os dados (ex.: mediago)",
            examples=["mediago"],
        ),
        db: Session = Depends(get_db)
):
    result = get_summary_cached(db, source, period)

    if not isinstance(result, dict) or "today" not in result:
        result = _empty_summary_payload()

    print(f"RETORNANDO PARA O FRONT: {result}")
    return {
        "today": {
            "cost": float((result.get("today") or {}).get("cost") or 0),
            "profit": float((result.get("today") or {}).get("profit") or 0),
            "revenue": float((result.get("today") or {}).get("revenue") or 0),
            "roi": float((result.get("today") or {}).get("roi") or 0),
        },
        "yesterday": {
            "cost": float((result.get("yesterday") or {}).get("cost") or 0),
            "profit": float((result.get("yesterday") or {}).get("profit") or 0),
            "revenue": float((result.get("yesterday") or {}).get("revenue") or 0),
            "roi": float((result.get("yesterday") or {}).get("roi") or 0),
        },
        "comparison": {
            "cost_change": float((result.get("comparison") or {}).get("cost_change") or 0),
            "profit_change": float((result.get("comparison") or {}).get("profit_change") or 0),
            "revenue_change": float((result.get("comparison") or {}).get("revenue_change") or 0),
            "roi_change": float((result.get("comparison") or {}).get("roi_change") or 0),
        }
    }

@router.get(
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
        description="Origem de tráfego para filtrar os dados (ex.: YTD)",
        examples=["YTD"],
    ),
    db: Session = Depends(get_db)
):
    rows = get_hourly_cached(db, source)
    print(rows)

    return [
        {
            "slot": str(_get_value(row, "slot", "")),
            "day": str(_get_value(row, "day", "")),
            "hour": str(_get_value(row, "hour", "")),
            "checkout_conversion": float(_get_value(row, "checkout_conversion", 0) or 0),
            "cost": float(_get_value(row, "cost", 0) or 0),
            "profit": float(_get_value(row, "profit", 0) or 0),
            "revenue": float(_get_value(row, "revenue", 0) or 0),
            "roi": float(_get_value(row, "roi", 0) or 0),
        }
        for row in rows
    ]

@router.get(
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
        description="Origem de tráfego para filtrar os dados",
        examples=["FBR"],
    ),
    db: Session = Depends(get_db)
):
    """
    Retorna métricas agregadas por hora para um período específico.
    
    - 24h: últimas 24 horas
    - daily: hoje inteiro
    - weekly: últimos 7 dias
    - monthly: últimos 30 dias
    """
    rows = get_metrics_by_period(db, period, source)
    
    return [
        {
            "slot": str(_get_value(row, "slot", "")),
            "day": str(_get_value(row, "day", "")),
            "hour": str(_get_value(row, "hour", "")),
            "checkout_conversion": float(_get_value(row, "checkout_conversion", 0) or 0),
            "cost": float(_get_value(row, "cost", 0) or 0),
            "profit": float(_get_value(row, "profit", 0) or 0),
            "revenue": float(_get_value(row, "revenue", 0) or 0),
            "roi": float(_get_value(row, "roi", 0) or 0),
        }
        for row in rows
    ]
