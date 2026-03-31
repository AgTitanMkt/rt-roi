from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import logging
from typing import Optional

import httpx

from ...core.database import SessionLocal
from ...models.metrics import DailySummary, DailyCheckoutSummary, DailyProductSummary
from ..metrics_service import get_summary as get_summary_metrics
from .conversions import AggregatedConversions, extract_campaign_info
from .http_client import make_request_with_retry
from .settings import REDTRACK_API_KEY, REDTRACK_REPORT_URL

logger = logging.getLogger(__name__)


def _q2(value: float | Decimal) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q4(value: float | Decimal) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _q0(value: int | float | Decimal) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _extract_squad_from_campaign_name(campaign_name: str) -> str:
    parts = [part.strip() for part in str(campaign_name or "").split("|") if part.strip()]
    responsible = parts[1] if len(parts) > 1 else (parts[0] if parts else "unknown")
    return (responsible.split("-")[0] or "unknown").strip() or "unknown"


async def fetch_daily_summary_rows(
    client: httpx.AsyncClient,
    *,
    target_date: str,
) -> list[dict]:
    params = {
        "api_key": REDTRACK_API_KEY,
        "group": "campaign,date",
        "date_from": target_date,
        "date_to": target_date,
        "timezone": "America/Sao_Paulo",
        "per": 1000,
        "page": 1,
    }

    rows_acc: list[dict] = []
    while True:
        rows = await make_request_with_retry(client, REDTRACK_REPORT_URL, params)
        if not isinstance(rows, list):
            raise RuntimeError("Resposta inesperada da API Redtrack para summary diario.")

        rows_acc.extend(rows)
        if len(rows) < params["per"]:
            break
        params["page"] += 1

    return rows_acc


def persist_daily_summary_snapshot(
    rows: list[dict],
    metric_date: date,
    events_by_campaign: dict[str, dict[str, int]] | None = None,
    conversions: Optional[AggregatedConversions] = None,
) -> None:
    """
    Persiste os dados de resumo diário.
    
    Args:
        rows: Linhas do relatório de campanhas
        metric_date: Data do relatório
        events_by_campaign: Formato legado de eventos (será usado se conversions for None)
        conversions: Novo formato com agregações por checkout e produto
    """
    if not rows:
        return

    by_squad: dict[str, dict[str, Decimal | int]] = {}
    
    for row in rows:
        campaign_name = str(row.get("campaign") or "")
        squad = _extract_squad_from_campaign_name(campaign_name)
        
        if squad not in by_squad:
            by_squad[squad] = {
                "cost": Decimal("0"),
                "profit": Decimal("0"),
                "revenue": Decimal("0"),
                "initiate": 0,
                "purchase": 0,
            }

        by_squad[squad]["cost"] += _q2(float(row.get("cost", 0) or 0))
        by_squad[squad]["profit"] += _q2(float(row.get("profit", 0) or 0))
        by_squad[squad]["revenue"] += _q2(float(row.get("revenue", 0) or 0))

        campaign_id = str(row.get("campaign_id") or row.get("campaignId") or row.get("campaign") or "").strip()
        if campaign_id:
            # Usar eventos do formato legado se disponível
            if events_by_campaign and campaign_id in events_by_campaign:
                events = events_by_campaign[campaign_id]
                by_squad[squad]["initiate"] += int(events.get("InitiateCheckout", 0) or 0)
                by_squad[squad]["purchase"] += int(events.get("Purchase", 0) or 0)
            # Ou usar o novo formato de conversions
            elif conversions and campaign_id in conversions.by_campaign:
                metrics = conversions.by_campaign[campaign_id]
                by_squad[squad]["initiate"] += metrics.initiate_checkout
                by_squad[squad]["purchase"] += metrics.purchase

    db = SessionLocal()
    try:
        # Persistir sumário por squad
        for squad, agg in by_squad.items():
            cost = _q2(agg["cost"])
            profit = _q2(agg["profit"])
            revenue = _q2(agg["revenue"])
            roi = _q4((profit / cost) if cost > 0 else 0)
            initiate_total = int(agg.get("initiate", 0) or 0)
            purchase_total = int(agg.get("purchase", 0) or 0)
            checkout = _q2((purchase_total / initiate_total) * 100 if initiate_total > 0 else 0)

            existing = db.query(DailySummary).filter(
                DailySummary.metric_date == metric_date,
                DailySummary.squad == squad,
            ).one_or_none()

            if existing:
                existing.cost = cost
                existing.profit = profit
                existing.revenue = revenue
                existing.roi = roi
                existing.checkout_conversion = checkout
            else:
                db.add(
                    DailySummary(
                        metric_date=metric_date,
                        squad=squad,
                        cost=cost,
                        profit=profit,
                        revenue=revenue,
                        roi=roi,
                        checkout_conversion=checkout,
                    )
                )

        # Persistir sumário por checkout (Cartpanda, Clickbank) se tiver conversions
        if conversions:
            _persist_checkout_summary(db, metric_date, conversions)
            _persist_product_summary(db, metric_date, conversions)

        db.commit()
        
        # Log de resumo
        total_cost = _q2(sum((values["cost"] for values in by_squad.values()), Decimal("0")))
        total_profit = _q2(sum((values["profit"] for values in by_squad.values()), Decimal("0")))
        total_revenue = _q2(sum((values["revenue"] for values in by_squad.values()), Decimal("0")))
        total_initiate = sum(int(values.get("initiate", 0) or 0) for values in by_squad.values())
        total_purchase = sum(int(values.get("purchase", 0) or 0) for values in by_squad.values())
        total_checkout = _q2((total_purchase / total_initiate) * 100 if total_initiate > 0 else 0)
        total_roi = _q4((total_profit / total_cost) if total_cost > 0 else 0)
        
        logger.info("✅ Snapshot diário salvo: %s squads para %s", len(by_squad), metric_date)
        logger.info(
            "📌 SUMMARY DIÁRIO (base dos cards) %s | cost=%s revenue=%s profit=%s checkout=%s roi=%s",
            metric_date,
            f"{total_cost:.2f}",
            f"{total_revenue:.2f}",
            f"{total_profit:.2f}",
            f"{total_checkout:.2f}",
            f"{total_roi:.4f}",
        )
        
        if conversions:
            logger.info("📊 Checkouts salvos: %s", list(conversions.by_checkout.keys()))
            logger.info("📊 Produtos salvos: %s", list(conversions.by_product.keys()))
            
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _persist_checkout_summary(
    db,
    metric_date: date,
    conversions: AggregatedConversions,
) -> None:
    """Persiste dados de conversão por checkout (Cartpanda, Clickbank)."""
    
    # Geral por checkout
    for checkout, metrics in conversions.by_checkout.items():
        if checkout == "unknown":
            continue
            
        conversion_rate = _q2(metrics.conversion_rate)
        
        existing = db.query(DailyCheckoutSummary).filter(
            DailyCheckoutSummary.metric_date == metric_date,
            DailyCheckoutSummary.checkout == checkout,
            DailyCheckoutSummary.squad == "ALL",
        ).one_or_none()
        
        if existing:
            existing.initiate_checkout = _q0(metrics.initiate_checkout)
            existing.purchase = _q0(metrics.purchase)
            existing.checkout_conversion = conversion_rate
        else:
            db.add(
                DailyCheckoutSummary(
                    metric_date=metric_date,
                    checkout=checkout,
                    squad="ALL",
                    initiate_checkout=_q0(metrics.initiate_checkout),
                    purchase=_q0(metrics.purchase),
                    checkout_conversion=conversion_rate,
                )
            )
    
    logger.info(
        "📊 Checkout Summary: %s checkouts persistidos",
        len([c for c in conversions.by_checkout.keys() if c != "unknown"])
    )


def _persist_product_summary(
    db,
    metric_date: date,
    conversions: AggregatedConversions,
) -> None:
    """Persiste dados de conversão por produto."""
    
    for product, metrics in conversions.by_product.items():
        if product == "unknown":
            continue
            
        conversion_rate = _q2(metrics.conversion_rate)
        
        existing = db.query(DailyProductSummary).filter(
            DailyProductSummary.metric_date == metric_date,
            DailyProductSummary.product == product,
            DailyProductSummary.squad == "ALL",
        ).one_or_none()
        
        if existing:
            existing.initiate_checkout = _q0(metrics.initiate_checkout)
            existing.purchase = _q0(metrics.purchase)
            existing.checkout_conversion = conversion_rate
        else:
            db.add(
                DailyProductSummary(
                    metric_date=metric_date,
                    product=product,
                    squad="ALL",
                    initiate_checkout=_q0(metrics.initiate_checkout),
                    purchase=_q0(metrics.purchase),
                    checkout_conversion=conversion_rate,
                )
            )
    
    logger.info(
        "📊 Product Summary: %s produtos persistidos",
        len([p for p in conversions.by_product.keys() if p != "unknown"])
    )


def log_cards_preview() -> None:
    db = SessionLocal()
    try:
        summary = get_summary_metrics(db, None, "24h")
        today = (summary or {}).get("today") or {}
        yesterday = (summary or {}).get("yesterday") or {}
        comparison = (summary or {}).get("comparison") or {}

        logger.info(
            "🧾 CARDS PREVIEW | today(cost=%s revenue=%s profit=%s roi=%s) | "
            "yesterday(cost=%s revenue=%s profit=%s roi=%s)",
            f"{float(today.get('cost') or 0):.2f}",
            f"{float(today.get('revenue') or 0):.2f}",
            f"{float(today.get('profit') or 0):.2f}",
            f"{float(today.get('roi') or 0):.4f}",
            f"{float(yesterday.get('cost') or 0):.2f}",
            f"{float(yesterday.get('revenue') or 0):.2f}",
            f"{float(yesterday.get('profit') or 0):.2f}",
            f"{float(yesterday.get('roi') or 0):.4f}",
        )
        logger.info(
            "🧾 CARDS PREVIEW COMPARISON | cost_change=%s%% revenue_change=%s%% profit_change=%s%% roi_change=%s%%",
            f"{float(comparison.get('cost_change') or 0):.2f}",
            f"{float(comparison.get('revenue_change') or 0):.2f}",
            f"{float(comparison.get('profit_change') or 0):.2f}",
            f"{float(comparison.get('roi_change') or 0):.2f}",
        )
    finally:
        db.close()
