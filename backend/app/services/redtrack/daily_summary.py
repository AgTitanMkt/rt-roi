from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import logging
from typing import Optional

import httpx

from ...core.database import SessionLocal
from ...models.metrics import DailySummary, DailyCheckoutSummary, DailyProductSummary, DailyConversionEntity
from .aggregators import aggregate_by_dimension
from ..metrics_service import get_summary as get_summary_metrics
from .conversions import AggregatedConversions, extract_campaign_info
from .http_client import make_request_with_retry
from .mappings import resolve_squad, resolve_checkout, resolve_product
from .settings import REDTRACK_API_KEY, REDTRACK_REPORT_URL
from .models import CampaignInfo

logger = logging.getLogger(__name__)


def _q2(value: float | Decimal) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q4(value: float | Decimal) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _q0(value: int | float | Decimal) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _normalize_and_format(raw_value: str | None, normalized_value: str | None) -> str:
    """
    Normaliza um valor para UPPERCASE.
    Se o valor normalizado for "unknown", retorna "UNKNOWN (valor_original)"

    Args:
        raw_value: Valor bruto recebido
        normalized_value: Valor após normalização/resolução

    Returns:
        Valor normalizado ou "UNKNOWN (valor_original)" se desconhecido
    """
    if not normalized_value or normalized_value.upper() == "UNKNOWN":
        raw_str = str(raw_value or "").strip() if raw_value else ""
        if raw_str and raw_str.upper() != "UNKNOWN":
            return raw_str.upper()
        return "UNKNOWN"

    return normalized_value.strip().upper()


def _extract_squad_from_campaign_name(campaign_name: str) -> str:
    return extract_campaign_info(campaign_name).squad


def load_daily_conversions_snapshot(metric_date: date) -> AggregatedConversions:
    """Carrega as conversões diárias já persistidas no banco para reutilização sem nova requisição."""
    db = SessionLocal()
    try:
        rows = db.query(DailyConversionEntity).filter(
            DailyConversionEntity.metric_date == metric_date,
        ).all()

        result = AggregatedConversions()
        for row in rows:
            campaign_id = str(row.campaign_id or "").strip()
            if not campaign_id:
                continue

            squad = _normalize_and_format(row.squad, resolve_squad(str(row.squad or "")))
            checkout = _normalize_and_format(row.checkout, resolve_checkout(str(row.checkout or "")))
            product = _normalize_and_format(row.product, resolve_product(str(row.product or "")))
            info = CampaignInfo(
                campaign_id=campaign_id,
                campaign_name=campaign_id,
                offer_id=str(row.offer_id).strip() or None,
                squad=squad.lower() if squad != "UNKNOWN" else squad,
                checkout=checkout,
                product=product,
            )

            result.campaign_info[campaign_id] = info

            initiate_total = int(row.initiate_checkout or 0)
            purchase_total = int(row.purchase or 0)

            aggregate_by_dimension(result, result.by_campaign, campaign_id, False, initiate_total)
            aggregate_by_dimension(result, result.by_campaign, campaign_id, True, purchase_total)
            aggregate_by_dimension(result, result.by_squad, squad, False, initiate_total)
            aggregate_by_dimension(result, result.by_squad, squad, True, purchase_total)
            aggregate_by_dimension(result, result.by_checkout, checkout, False, initiate_total)
            aggregate_by_dimension(result, result.by_checkout, checkout, True, purchase_total)
            aggregate_by_dimension(result, result.by_product, product, False, initiate_total)
            aggregate_by_dimension(result, result.by_product, product, True, purchase_total)

        logger.info("💾 Conversões carregadas do banco para %s: %s campanhas", metric_date, len(result.by_campaign))
        return result
    finally:
        db.close()


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
        current_page = int(params.get("page", 1) or 1)
        logger.info("📄 [daily_summary] Buscando página %s para %s", current_page, target_date)
        try:
            rows = await make_request_with_retry(client, REDTRACK_REPORT_URL, params)
        except Exception as exc:
            logger.error(
                "❌ [daily_summary] Falha na página %s para %s: %s",
                current_page,
                target_date,
                exc,
            )
            raise

        if not isinstance(rows, list):
            raise RuntimeError("Resposta inesperada da API Redtrack para summary diario.")

        rows_acc.extend(rows)
        logger.info(
            "✅ [daily_summary] Página %s concluída (%s linhas)",
            current_page,
            len(rows),
        )
        if len(rows) < params["per"]:
            logger.info("✅ [daily_summary] Fim da paginação em %s (página %s)", target_date, current_page)
            break
        params["page"] += 1

    return rows_acc


def persist_daily_summary_snapshot(
    rows: list[dict],
    metric_date: date,
    events_by_campaign: dict[str, dict[str, int]] | None = None,
    conversions: Optional[AggregatedConversions] = None,
) -> dict[str, int]:
    """
    Persiste os dados de resumo diário.
    
    Args:
        rows: Linhas do relatório de campanhas
        metric_date: Data do relatório
        events_by_campaign: Formato legado de eventos (será usado se conversions for None)
        conversions: Novo formato com agregações por checkout e produto
    """
    if not rows:
        return {"saved_checkout": 0, "saved_purchase": 0}

    by_squad: dict[str, dict[str, Decimal | int]] = {}
    
    for row in rows:
        campaign_name = str(row.get("campaign") or row.get("campaign_name") or "")
        offer_name = str(row.get("offer") or row.get("offer_name") or "")
        source_candidates = [value.strip() for value in (campaign_name, offer_name) if str(value or "").strip()]
        source_name = " | ".join(source_candidates)
        squad_raw = _extract_squad_from_campaign_name(source_name)
        squad_resolved = resolve_squad(source_name or squad_raw)
        # Normalizar squad para UPPERCASE e adicionar valor original se desconhecido
        squad = _normalize_and_format(squad_raw, squad_resolved)

        if squad not in by_squad:
            by_squad[squad] = {
                "cost": Decimal("0"),
                "profit": Decimal("0"),
                "revenue": Decimal("0"),
                "initiate": int(0),
                "purchase": int(0),
            }

        # Snapshot diário precisa representar o total do dia por squad.
        by_squad[squad]["cost"] = _q2(by_squad[squad]["cost"] + _q2(float(row.get("cost", 0) or 0)))
        by_squad[squad]["profit"] = _q2(by_squad[squad]["profit"] + _q2(float(row.get("profit", 0) or 0)))
        by_squad[squad]["revenue"] = _q2(by_squad[squad]["revenue"] + _q2(float(row.get("revenue", 0) or 0)))

        campaign_id = str(row.get("campaign_id") or row.get("campaignId") or row.get("campaign") or "").strip()
        offer_id = str(row.get("offer_id") or row.get("offerId") or row.get("offer") or "").strip()

        identifier_candidates = [value for value in (campaign_id, offer_id) if value]
        for identifier in identifier_candidates:
            # Usar eventos do formato legado se disponível
            if events_by_campaign and identifier in events_by_campaign:
                events = events_by_campaign[identifier]
                by_squad[squad]["initiate"] += int(events.get("InitiateCheckout", 0) or 0)
                by_squad[squad]["purchase"] += int(events.get("Purchase", 0) or 0)
                break

            # Ou usar o novo formato de conversions
            if conversions and identifier in conversions.by_campaign:
                metrics = conversions.by_campaign[identifier]
                by_squad[squad]["initiate"] += metrics.initiate_checkout
                by_squad[squad]["purchase"] += metrics.purchase
                break

    db = SessionLocal()
    try:
        # Snapshot diario deve substituir totalmente o estado da data,
        # evitando linhas legadas que inflavam totais.
        db.query(DailySummary).filter(DailySummary.metric_date == metric_date).delete(synchronize_session=False)
        db.query(DailyCheckoutSummary).filter(DailyCheckoutSummary.metric_date == metric_date).delete(synchronize_session=False)
        db.query(DailyProductSummary).filter(DailyProductSummary.metric_date == metric_date).delete(synchronize_session=False)
        db.query(DailyConversionEntity).filter(DailyConversionEntity.metric_date == metric_date).delete(synchronize_session=False)

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

            _upsert_daily_checkout_totals(
                db=db,
                metric_date=metric_date,
                squad=squad,
                initiate_total=initiate_total,
                purchase_total=purchase_total,
            )

        total_initiate = sum(int(values.get("initiate", 0) or 0) for values in by_squad.values())
        total_purchase = sum(int(values.get("purchase", 0) or 0) for values in by_squad.values())
        _upsert_daily_checkout_totals(
            db=db,
            metric_date=metric_date,
            squad="ALL",
            initiate_total=total_initiate,
            purchase_total=total_purchase,
        )

        # Persistir sumário por checkout (Cartpanda, Clickbank) se tiver conversions
        if conversions:
            _persist_conversion_breakdown(db, metric_date, conversions)
            _persist_checkout_summary(db, metric_date, conversions)
            _persist_product_summary(db, metric_date, conversions)

        db.commit()
        
        # Log de resumo
        total_cost = _q2(sum((values["cost"] for values in by_squad.values()), Decimal("0")))
        total_profit = _q2(sum((values["profit"] for values in by_squad.values()), Decimal("0")))
        total_revenue = _q2(sum((values["revenue"] for values in by_squad.values()), Decimal("0")))
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

        return {
            "saved_checkout": int(total_initiate),
            "saved_purchase": int(total_purchase),
        }
            
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _upsert_daily_checkout_totals(
    db,
    metric_date: date,
    squad: str,
    initiate_total: int,
    purchase_total: int,
) -> None:
    conversion_rate = _q2((purchase_total / initiate_total) * 100 if initiate_total > 0 else 0)

    existing = db.query(DailyCheckoutSummary).filter(
        DailyCheckoutSummary.metric_date == metric_date,
        DailyCheckoutSummary.checkout == "ALL",
        DailyCheckoutSummary.squad == squad,
    ).one_or_none()

    if existing:
        existing.initiate_checkout = _q0(initiate_total)
        existing.purchase = _q0(purchase_total)
        existing.checkout_conversion = conversion_rate
    else:
        db.add(
            DailyCheckoutSummary(
                metric_date=metric_date,
                checkout="ALL",
                squad=squad,
                initiate_checkout=_q0(initiate_total),
                purchase=_q0(purchase_total),
                checkout_conversion=conversion_rate,
            )
        )


def _persist_checkout_summary(
    db,
    metric_date: date,
    conversions: AggregatedConversions,
) -> None:
    """Persiste dados de conversão por checkout (Cartpanda, Clickbank)."""
    
    # Geral por checkout
    for checkout, metrics in conversions.by_checkout.items():
        # Normalizar checkout para UPPERCASE e adicionar valor original se desconhecido
        checkout_normalized = _normalize_and_format(checkout, checkout)
        conversion_rate = _q2(metrics.conversion_rate)
        
        existing = db.query(DailyCheckoutSummary).filter(
            DailyCheckoutSummary.metric_date == metric_date,
            DailyCheckoutSummary.checkout == checkout_normalized,
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
                    checkout=checkout_normalized,
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


def _persist_conversion_breakdown(
    db,
    metric_date: date,
    conversions: AggregatedConversions,
) -> None:
    """Persiste conversão por entidade (campaign_id + offer_id) com dimensões."""
    persisted = 0

    for campaign_id, metrics in conversions.by_campaign.items():
        info = conversions.campaign_info.get(campaign_id)
        if not info:
            continue

        mapping_source = " | ".join(
            [
                value.strip()
                for value in (info.campaign_name, info.squad, info.checkout, info.product)
                if str(value or "").strip()
            ]
        )

        # Re-resolve via settings antes de persistir para evitar dados fora do padrão.
        squad = _normalize_and_format(info.squad, resolve_squad(mapping_source or info.squad))
        checkout = _normalize_and_format(info.checkout, resolve_checkout(mapping_source or info.checkout))
        product = _normalize_and_format(info.product, resolve_product(mapping_source or info.product))

        existing = db.query(DailyConversionEntity).filter(
            DailyConversionEntity.metric_date == metric_date,
            DailyConversionEntity.campaign_id == campaign_id,
        ).one_or_none()

        initiate_total = int(metrics.initiate_checkout or 0)
        purchase_total = int(metrics.purchase or 0)
        conversion_rate = _q2((purchase_total / initiate_total) * 100 if initiate_total > 0 else 0)

        if existing:
            existing.offer_id = info.offer_id
            existing.squad = squad
            existing.checkout = checkout
            existing.product = product
            existing.initiate_checkout = _q0(initiate_total)
            existing.purchase = _q0(purchase_total)
            existing.checkout_conversion = conversion_rate
        else:
            db.add(
                DailyConversionEntity(
                    metric_date=metric_date,
                    campaign_id=campaign_id,
                    offer_id=info.offer_id,
                    squad=squad,
                    checkout=checkout,
                    product=product,
                    initiate_checkout=_q0(initiate_total),
                    purchase=_q0(purchase_total),
                    checkout_conversion=conversion_rate,
                )
            )

        persisted += 1

    logger.info("📊 Breakdown Summary: %s combinações persistidas", persisted)


def _persist_product_summary(
    db,
    metric_date: date,
    conversions: AggregatedConversions,
) -> None:
    """Persiste dados de conversão por produto."""
    
    for product, metrics in conversions.by_product.items():

        # Normalizar product para UPPERCASE e adicionar valor original se desconhecido
        product_normalized = _normalize_and_format(product, product)
        conversion_rate = _q2(metrics.conversion_rate)
        
        existing = db.query(DailyProductSummary).filter(
            DailyProductSummary.metric_date == metric_date,
            DailyProductSummary.product == product_normalized,
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
                    product=product_normalized,
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
