import logging

from ...core.database import SessionLocal
from ..metrics_service import insert_metrics
from ...schemas.redtrack_schema import RedtrackResponse

logger = logging.getLogger(__name__)


def persist_metrics_report(data: RedtrackResponse) -> None:
    payload = [
        {
            "id": item.campaign_id,
            "squad": item.squad,
            "checkout": item.checkout,
            "product": item.product,
            "metric_at": item.date,
            "cost": item.cost,
            "profit": item.profit,
            "revenue": item.revenue,
            "roi": item.roi,
            "checkout_conversion": item.conversion,
        }
        for item in data
    ]

    if not payload:
        logger.info("💾 Nenhum dado para persistir (payload vazio)")
        return

    logger.info("💾 Iniciando persistência de %s registros no banco de dados...", len(payload))
    db = SessionLocal()
    try:
        result = insert_metrics(db, payload)
        logger.info(
            "✅ Persistencia finalizada: inseridos=%s, atualizados=%s, ignorados=%s",
            result["inserted"],
            result["updated"],
            result["ignored"],
        )
    except Exception as exc:
        logger.error("❌ Erro ao persistir métricas: %s: %s", type(exc).__name__, exc)
        raise
    finally:
        db.close()

