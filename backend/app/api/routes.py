from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..schemas.metrics_schema import HourlyMetricResponse, SummaryResponse
from ..services.metrics_service import (
    get_metrics_by_hour,
    get_summary as get_summary_service,
)

router = APIRouter(prefix="/metrics", tags=["metrics"])

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
        source: str | None = Query(
            default=None,
            description="Origem de tráfego para filtrar os dados (ex.: mediago)",
            examples=["mediago"],
        ),
        db: Session = Depends(get_db)
):
    result = get_summary_service(db, source)

    print(f"RETORNANDO PARA O FRONT: {result}")
    return {
        "today": {
            "cost": float(result["today"]["cost"] or 0),
            "profit": float(result["today"]["profit"] or 0),
            "roi": float(result["today"]["roi"] or 0),
        },
        "yesterday": {
            "cost": float(result["yesterday"]["cost"] or 0),
            "profit": float(result["yesterday"]["profit"] or 0),
            "roi": float(result["yesterday"]["roi"] or 0),
        },
        "comparison": {
            "cost_change": float(result["comparison"]["cost_change"] or 0),
            "profit_change": float(result["comparison"]["profit_change"] or 0),
            "roi_change": float(result["comparison"]["roi_change"] or 0),
        }
    }

@router.get(
    "/hourly",
    summary="Retorna métricas por hora",
    description=(
        "Retorna uma série temporal por hora com custo, lucro e ROI para gráficos.\n\n"
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
                            "hour": "14",
                            "cost": 12.1,
                            "profit": 4.2,
                            "roi": 0.35,
                        },
                        {
                            "hour": "15",
                            "cost": 10.4,
                            "profit": 3.1,
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
        description="Origem de tráfego para filtrar os dados (ex.: mediago)",
        examples=["mediago"],
    ),
    db: Session = Depends(get_db)
):
    rows = get_metrics_by_hour(db, source)

    return [
        {
            "hour": row.hour,
            "cost": float(row.cost or 0),
            "profit": float(row.profit or 0),
            "roi": float(row.roi or 0),
        }
        for row in rows
    ]