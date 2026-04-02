from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta, date
from typing import Any
from zoneinfo import ZoneInfo
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func, text
from ..models.metrics import DailySummary, HourlyMetric
from .redtrack.mappings import resolve_product, resolve_squad, resolve_checkout
from .redtrack.settings import SQUAD_MAPPINGS

logger = logging.getLogger(__name__)


SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")


def _q2(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q4(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


ALLOWED_SQUADS = {
    str(entry.get("value") or "").strip().upper()
    for entry in SQUAD_MAPPINGS
    if str(entry.get("value") or "").strip()
}


def _normalize_dimension_value(raw: str | None, resolved: str | None) -> str:
    raw_value = str(raw or "").strip()
    if not raw_value:
        return "UNKNOWN"

    resolved_value = str(resolved or "").strip()
    if resolved_value and resolved_value.lower() != "unknown":
        return resolved_value.upper()

    # Mantem o valor original quando o mapeamento nao encontra alias.
    return raw_value.upper()


def _normalize_squad(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return "UNKNOWN"

    resolved = resolve_squad(raw)
    normalized = _normalize_dimension_value(raw, resolved)

    # Se esta entre os squads canonicos, mantem formato esperado.
    if normalized in ALLOWED_SQUADS:
        return normalized

    return normalized


def _normalize_checkout(value: str | None) -> str:
    raw = str(value or "").strip()
    resolved = resolve_checkout(raw)
    return _normalize_dimension_value(raw, resolved)


def _normalize_product(value: str | None) -> str:
    raw = str(value or "").strip()
    resolved = resolve_product(raw)
    return _normalize_dimension_value(raw, resolved)


def _table_exists(db: Session, table_name: str) -> bool:
    exists = db.execute(
        text("SELECT to_regclass(:table_name) IS NOT NULL"),
        {"table_name": f"public.{table_name}"},
    ).scalar()
    return bool(exists)


def _get_checkout_conversion_range(
    db: Session,
    start_date: date,
    end_date: date,
    source: str | None,
) -> Decimal | None:
    if not _table_exists(db, "tb_daily_checkout_summary"):
        return None

    query = """
        SELECT
            SUM(initiate_checkout) AS initiate_checkout,
            SUM(purchase) AS purchase
        FROM tb_daily_checkout_summary
        WHERE metric_date BETWEEN :start_date AND :end_date
          AND checkout = 'ALL'
    """

    params: dict[str, object] = {
        "start_date": start_date,
        "end_date": end_date,
    }

    if source:
        query += " AND UPPER(squad) = UPPER(:source)"
        params["source"] = source
    else:
        query += " AND squad = 'ALL'"

    row = db.execute(text(query), params).fetchone()
    initiate = float(getattr(row, "initiate_checkout", 0) or 0)
    purchase = float(getattr(row, "purchase", 0) or 0)
    if initiate <= 0:
        return _q2(0)
    return _q2((purchase / initiate) * 100)


def _refresh_daily_summary(db: Session, affected_keys: set[tuple[date, str]]) -> None:
    if not affected_keys:
        return

    for metric_date, squad in affected_keys:
        day_start = datetime.combine(metric_date, datetime.min.time(), tzinfo=SAO_PAULO_TZ)
        day_end = day_start + timedelta(days=1)

        agg = db.query(
            func.coalesce(func.sum(HourlyMetric.cost), 0).label("cost"),
            func.coalesce(func.sum(HourlyMetric.profit), 0).label("profit"),
            func.coalesce(func.sum(HourlyMetric.revenue), 0).label("revenue"),
            func.coalesce(func.sum(HourlyMetric.checkout_conversion), 0).label("checkout_conversion"),
        ).filter(
            HourlyMetric.metric_at >= day_start,
            HourlyMetric.metric_at < day_end,
            HourlyMetric.squad == squad,
        ).first()

        cost = _q2(getattr(agg, "cost", 0))
        profit = _q2(getattr(agg, "profit", 0))
        revenue = _q2(getattr(agg, "revenue", 0))
        checkout_conversion = _q2(getattr(agg, "checkout_conversion", 0))
        roi = _q4((profit / cost) if cost > 0 else 0)

        summary_row = db.query(DailySummary).filter(
            DailySummary.metric_date == metric_date,
            DailySummary.squad == squad,
        ).one_or_none()

        if summary_row:
            summary_row.cost = cost
            summary_row.profit = profit
            summary_row.revenue = revenue
            summary_row.checkout_conversion = checkout_conversion
            summary_row.roi = roi
        else:
            db.add(
                DailySummary(
                    metric_date=metric_date,
                    squad=squad,
                    cost=cost,
                    profit=profit,
                    revenue=revenue,
                    checkout_conversion=checkout_conversion,
                    roi=roi,
                )
            )


def insert_metrics(db: Session, data: list):
    if not data:
        return {"inserted": 0, "updated": 0, "ignored": 0}

    unique_payload: dict[tuple[str, datetime], dict] = {}
    for item in data:
        campaign_id = str(item.get("id") or "").strip()
        metric_at = item.get("metric_at")
        normalized_squad = _normalize_squad(item.get("squad"))
        if not campaign_id or metric_at is None:
            continue

        unique_payload[(campaign_id, metric_at)] = {
            "campaign_id": campaign_id,
            "offer_id": str(item.get("offer_id") or "").strip() or None,
            "metric_at": metric_at,
            "squad": normalized_squad,
            "checkout": _normalize_checkout(item.get("checkout")),
            "product": _normalize_product(item.get("product")),
            "cost": _q2(item.get("cost")),
            "profit": _q2(item.get("profit")),
            "revenue": _q2(item.get("revenue")),
            "roi": _q4(item.get("roi")),
            "checkout_conversion": _q2(item.get("checkout_conversion")),
            # Delta logic is applied only when source values are cumulative.
            "is_cumulative": bool(item.get("is_cumulative", False)),
        }

    if not unique_payload:
        return {"inserted": 0, "updated": 0, "ignored": len(data)}

    previous_targets: list[tuple[str, datetime]] = []
    for _, item in unique_payload.items():
        metric_at = item["metric_at"]
        metric_at_sp = metric_at.astimezone(SAO_PAULO_TZ)
        if not item["is_cumulative"]:
            continue
        if metric_at_sp.hour == 0:
            continue
        previous_targets.append((item["campaign_id"], metric_at - timedelta(hours=1)))

    previous_by_key: dict[tuple[object, object], Any] = {}
    if previous_targets:
        previous_campaign_ids = list({campaign_id for campaign_id, _ in previous_targets})
        previous_metric_ats = list({metric_at for _, metric_at in previous_targets})
        previous_rows = db.query(HourlyMetric).filter(
            HourlyMetric.campaign_id.in_(previous_campaign_ids),
            HourlyMetric.metric_at.in_(previous_metric_ats),
        ).all()
        for row in previous_rows:
            previous_by_key[(row.campaign_id, row.metric_at)] = row

    for key, item in unique_payload.items():
        metric_at = item["metric_at"]
        metric_at_sp = metric_at.astimezone(SAO_PAULO_TZ)
        if not item["is_cumulative"]:
            continue
        if metric_at_sp.hour == 0:
            continue

        previous_row = previous_by_key.get((item["campaign_id"], metric_at - timedelta(hours=1)))
        if not previous_row:
            continue

        for field, prev_raw in (
            ("cost", previous_row.cost),
            ("profit", previous_row.profit),
            ("revenue", previous_row.revenue),
            ("checkout_conversion", previous_row.checkout_conversion),
        ):
            current_value = Decimal(str(item[field] or 0))
            previous_value = Decimal(str(prev_raw or 0))
            item[field] = _q2(max(current_value - previous_value, Decimal("0")))

        item["roi"] = _q4((item["profit"] / item["cost"]) if item["cost"] > 0 else 0)

    campaign_ids = list({k[0] for k in unique_payload})
    metric_ats = list({k[1] for k in unique_payload})

    existing_rows = db.query(HourlyMetric).filter(
        HourlyMetric.campaign_id.in_(campaign_ids),
        HourlyMetric.metric_at.in_(metric_ats),
    ).all()
    existing_by_key = {(row.campaign_id, row.metric_at): row for row in existing_rows}

    inserted = 0
    updated = 0
    affected_summary_keys: set[tuple[date, str]] = set()

    for key, item in unique_payload.items():
        existing = existing_by_key.get(key)
        if existing:
            existing.offer_id = item["offer_id"]
            existing.squad = item["squad"]
            existing.checkout = item["checkout"]
            existing.product = item["product"]
            existing.cost = item["cost"]
            existing.profit = item["profit"]
            existing.revenue = item["revenue"]
            existing.roi = item["roi"]
            existing.checkout_conversion = item["checkout_conversion"]
            updated += 1
        else:
            db.add(
                HourlyMetric(
                    campaign_id=item["campaign_id"],
                    offer_id=item["offer_id"],
                    metric_at=item["metric_at"],
                    squad=item["squad"],
                    checkout=item["checkout"],
                    product=item["product"],
                    cost=item["cost"],
                    profit=item["profit"],
                    revenue=item["revenue"],
                    roi=item["roi"],
                    checkout_conversion=item["checkout_conversion"],
                )
            )
            inserted += 1

        metric_date = item["metric_at"].astimezone(SAO_PAULO_TZ).date()
        affected_summary_keys.add((metric_date, item["squad"]))

    # Fonte de verdade do summary deve ser o snapshot diário (report diário),
    # não a agregação da tabela horária.
    # Mantemos o refresh desativado para não contaminar os cards com dados hourly.
    # _refresh_daily_summary(db, affected_summary_keys)
    db.commit()

    return {
        "inserted": inserted,
        "updated": updated,
        "ignored": max(len(data) - len(unique_payload), 0),
    }


def get_summary(
    db: Session,
    source: str = None,
    period: str = "24h",
    checkout: str | None = None,
    product: str | None = None,
):
    sp_today = datetime.now(SAO_PAULO_TZ).date()

    use_hourly_for_summary = bool(checkout or product)

    # Sem filtros de checkout/produto, usa o snapshot diário mais recente disponível.
    if not use_hourly_for_summary:
        latest_date_query = """
            SELECT MAX(metric_date) AS latest_date
            FROM tb_daily_metrics_summary
        """
        latest_params: dict[str, object] = {}
        if source:
            latest_date_query += " WHERE UPPER(squad) = UPPER(:source)"
            latest_params["source"] = source

        latest_row = db.execute(text(latest_date_query), latest_params).fetchone()
        latest_daily_date = getattr(latest_row, "latest_date", None) if latest_row else None
        reference_date = latest_daily_date or sp_today
    else:
        # Com filtros de checkout/produto, usa base horária (única com essas dimensões).
        reference_date = sp_today

    if period == "weekly":
        current_start = reference_date - timedelta(days=6)
        current_end = reference_date
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=6)
    elif period == "monthly":
        current_start = reference_date - timedelta(days=29)
        current_end = reference_date
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=29)
    else:
        # 24h/daily devem refletir o snapshot diário fechado (base dos cards).
        current_start = reference_date
        current_end = reference_date
        previous_start = reference_date - timedelta(days=1)
        previous_end = reference_date - timedelta(days=1)

    def _fetch_range_agg(start_date: date, end_date: date):
        if use_hourly_for_summary:
            query = """
                SELECT
                    SUM(cost) as cost,
                    SUM(profit) as profit,
                    SUM(revenue) as revenue,
                    ROUND(AVG(checkout_conversion), 2) as checkout_avg,
                    ROUND(SUM(profit) / NULLIF(SUM(cost), 0), 4) as roi
                FROM tb_hourly_metrics
                WHERE timezone('America/Sao_Paulo', metric_at)::date BETWEEN :start_date AND :end_date
                  AND (:source IS NULL OR UPPER(squad) = UPPER(:source))
                  AND (:checkout IS NULL OR UPPER(checkout_type) = UPPER(:checkout))
                  AND (:product IS NULL OR UPPER(product) = UPPER(:product))
            """
            params: dict[str, object] = {
                "start_date": start_date,
                "end_date": end_date,
                "source": source,
                "checkout": checkout,
                "product": product,
            }
            return db.execute(text(query), params).fetchone()

        query = """
            SELECT
                SUM(cost) as cost,
                SUM(profit) as profit,
                SUM(revenue) as revenue,
                ROUND(AVG(checkout_conversion), 2) as checkout_avg,
                ROUND(SUM(profit) / NULLIF(SUM(cost), 0), 4) as roi
            FROM tb_daily_metrics_summary
            WHERE metric_date BETWEEN :start_date AND :end_date
        """

        params = {
            "start_date": start_date,
            "end_date": end_date,
        }

        if source:
            query += " AND UPPER(squad) = UPPER(:source)"
            params["source"] = source

        return db.execute(text(query), params).fetchone()

    current_data = _fetch_range_agg(current_start, current_end)
    previous_data = _fetch_range_agg(previous_start, previous_end)
    if use_hourly_for_summary:
        current_checkout = _q2(getattr(current_data, "checkout_avg", 0) or 0)
        previous_checkout = _q2(getattr(previous_data, "checkout_avg", 0) or 0)
    else:
        current_checkout = _get_checkout_conversion_range(db, current_start, current_end, source)
        previous_checkout = _get_checkout_conversion_range(db, previous_start, previous_end, source)

    result_obj = {
        "today": {
            "cost": _q2(getattr(current_data, "cost", 0) or 0),
            "profit": _q2(getattr(current_data, "profit", 0) or 0),
            "revenue": _q2(getattr(current_data, "revenue", 0) or 0),
            "checkout": current_checkout if current_checkout is not None else _q2(getattr(current_data, "checkout_avg", 0) or 0),
            "roi": _q4(getattr(current_data, "roi", 0) or 0),
        },
        "yesterday": {
            "cost": _q2(getattr(previous_data, "cost", 0) or 0),
            "profit": _q2(getattr(previous_data, "profit", 0) or 0),
            "revenue": _q2(getattr(previous_data, "revenue", 0) or 0),
            "checkout": previous_checkout if previous_checkout is not None else _q2(getattr(previous_data, "checkout_avg", 0) or 0),
            "roi": _q4(getattr(previous_data, "roi", 0) or 0),
        },
        "comparison": {
            "cost_change": 0,
            "profit_change": 0,
            "revenue_change": 0,
            "checkout_change": 0,
            "roi_change": 0,
        }
    }

    current_cost = float(getattr(current_data, "cost", 0) or 0)
    current_profit = float(getattr(current_data, "profit", 0) or 0)
    current_revenue = float(getattr(current_data, "revenue", 0) or 0)
    current_checkout = float(result_obj["today"]["checkout"] or 0)
    current_roi = float(getattr(current_data, "roi", 0) or 0)

    previous_cost = float(getattr(previous_data, "cost", 0) or 0)
    previous_profit = float(getattr(previous_data, "profit", 0) or 0)
    previous_revenue = float(getattr(previous_data, "revenue", 0) or 0)
    previous_checkout = float(result_obj["yesterday"]["checkout"] or 0)
    previous_roi = float(getattr(previous_data, "roi", 0) or 0)

    if previous_cost != 0:
        result_obj["comparison"]["cost_change"] = _q2(((current_cost - previous_cost) / abs(previous_cost)) * 100)
    if previous_profit != 0:
        result_obj["comparison"]["profit_change"] = _q2(((current_profit - previous_profit) / abs(previous_profit)) * 100)
    if previous_revenue != 0:
        result_obj["comparison"]["revenue_change"] = _q2(((current_revenue - previous_revenue) / abs(previous_revenue)) * 100)
    if previous_checkout != 0:
        result_obj["comparison"]["checkout_change"] = _q2(((current_checkout - previous_checkout) / abs(previous_checkout)) * 100)
    if previous_roi != 0:
        result_obj["comparison"]["roi_change"] = _q2(((current_roi - previous_roi) / abs(previous_roi)) * 100)

    return result_obj


def get_metrics_by_hour(db: Session, source: str = None):
    now_sp = datetime.now(SAO_PAULO_TZ)
    sp_today = now_sp.date()
    sp_yesterday = sp_today - timedelta(days=1)

    query = """
        WITH hourly AS (
            SELECT
                CASE WHEN :source IS NULL THEN NULL::text ELSE :source END as squad,
                to_char(date_trunc('hour', timezone('America/Sao_Paulo', metric_at)), 'YYYY-MM-DD"T"HH24:00:00') as slot,
                CASE
                    WHEN timezone('America/Sao_Paulo', metric_at)::date = :sp_today THEN 'today'
                    ELSE 'yesterday'
                END as day,
                EXTRACT(HOUR FROM timezone('America/Sao_Paulo', metric_at))::text as hour,
                ROUND(AVG(checkout_conversion), 2) as checkout_conversion,
                SUM(cost) as cost,
                SUM(profit) as profit,
                SUM(revenue) as revenue,
                ROUND(SUM(profit) / NULLIF(SUM(cost), 0), 2) as roi
            FROM tb_hourly_metrics
            WHERE timezone('America/Sao_Paulo', metric_at)::date IN (:sp_today, :sp_yesterday)
              AND (:source IS NULL OR UPPER(squad) = UPPER(:source))
            GROUP BY
                date_trunc('hour', timezone('America/Sao_Paulo', metric_at)),
                timezone('America/Sao_Paulo', metric_at)::date,
                EXTRACT(HOUR FROM timezone('America/Sao_Paulo', metric_at))
        )
        SELECT *
        FROM (
            SELECT *
            FROM hourly
            ORDER BY slot DESC
            LIMIT 24
        ) latest
        ORDER BY slot
    """

    params: dict[str, object] = {
        "sp_today": sp_today,
        "sp_yesterday": sp_yesterday,
        "source": source,
    }

    result = db.execute(text(query), params)
    return result.fetchall()


def get_metrics_by_period(
    db: Session,
    period: str = "24h",
    source: str = None,
    checkout: str | None = None,
    product: str | None = None,
):
    """
    Retorna métricas para um período específico.
    
    period: "24h", "daily", "weekly", ou "monthly"
    
    - 24h: últimas 24 horas (últimas 24 horas do dia atual + anterior)
    - daily: hoje inteiro (00:00 até agora)
    - weekly: últimos 7 dias
    - monthly: últimos 30 dias
    """
    now_sp = datetime.now(SAO_PAULO_TZ)
    sp_today = now_sp.date()
    
    # Determinar intervalo de datas conforme o período
    if period == "24h":
        date_start = sp_today - timedelta(days=1)
        date_end = sp_today
        limit_hours = 24
    elif period == "daily":
        date_start = sp_today
        date_end = sp_today
        limit_hours = 24
    elif period == "weekly":
        date_start = sp_today - timedelta(days=7)
        date_end = sp_today
        limit_hours = None  # Sem limite
    elif period == "monthly":
        date_start = sp_today - timedelta(days=30)
        date_end = sp_today
        limit_hours = None  # Sem limite
    else:
        date_start = sp_today - timedelta(days=1)
        date_end = sp_today
        limit_hours = 24
    
    sp_yesterday = sp_today - timedelta(days=1)

    # Construir query dinâmica
    limit_clause = f"LIMIT {limit_hours}" if limit_hours else ""
    
    query = f"""
        SELECT
            to_char(date_trunc('hour', timezone('America/Sao_Paulo', metric_at)), 'YYYY-MM-DD"T"HH24:00:00') as slot,
            EXTRACT(HOUR FROM timezone('America/Sao_Paulo', metric_at))::text as hour,
            CASE
                WHEN timezone('America/Sao_Paulo', metric_at)::date = :sp_today THEN 'today'
                WHEN timezone('America/Sao_Paulo', metric_at)::date = :sp_yesterday THEN 'yesterday'
                ELSE 'past'
            END as day,
            ROUND(AVG(checkout_conversion), 2) as checkout_conversion,
            SUM(cost) as cost,
            SUM(profit) as profit,
            SUM(revenue) as revenue,
            ROUND(SUM(profit) / NULLIF(SUM(cost), 0), 4) as roi,
            CASE WHEN :source IS NULL THEN NULL::text ELSE :source END as squad
        FROM tb_hourly_metrics
        WHERE timezone('America/Sao_Paulo', metric_at)::date BETWEEN :date_start AND :date_end
          AND (:source IS NULL OR UPPER(squad) = UPPER(:source))
          AND (:checkout IS NULL OR UPPER(checkout_type) = UPPER(:checkout))
          AND (:product IS NULL OR UPPER(product) = UPPER(:product))
        GROUP BY
            date_trunc('hour', timezone('America/Sao_Paulo', metric_at)),
            EXTRACT(HOUR FROM timezone('America/Sao_Paulo', metric_at)),
            timezone('America/Sao_Paulo', metric_at)::date
        ORDER BY slot DESC
        {limit_clause}
    """
    
    params: dict[str, object] = {
        "sp_today": sp_today,
        "sp_yesterday": sp_yesterday,
        "date_start": date_start,
        "date_end": date_end,
        "source": source,
        "checkout": checkout,
        "product": product,
    }
    
    result = db.execute(text(query), params)
    rows = result.fetchall()
    
    # Reverter ordem para crescente (mais antigo primeiro)
    return list(reversed(rows)) if rows else []


def get_checkout_summary(db: Session, squad: str = None, period: str = "24h"):
    """
    Retorna métricas de conversão por checkout (Cartpanda, Clickbank).
    """
    if not _table_exists(db, "tb_daily_checkout_summary"):
        return []

    sp_today = datetime.now(SAO_PAULO_TZ).date()
    
    if period == "weekly":
        date_start = sp_today - timedelta(days=6)
        date_end = sp_today
    elif period == "monthly":
        date_start = sp_today - timedelta(days=29)
        date_end = sp_today
    else:  # 24h ou daily
        date_start = sp_today
        date_end = sp_today
    
    query = """
        SELECT
            checkout,
            SUM(initiate_checkout) as initiate_checkout,
            SUM(purchase) as purchase,
            CASE 
                WHEN SUM(initiate_checkout) > 0 
                THEN ROUND((SUM(purchase)::numeric / SUM(initiate_checkout)) * 100, 2)
                ELSE 0 
            END as checkout_conversion
        FROM tb_daily_checkout_summary
        WHERE metric_date BETWEEN :date_start AND :date_end
    """
    
    params: dict[str, object] = {
        "date_start": date_start,
        "date_end": date_end,
    }
    
    if squad:
        query += " AND (UPPER(squad) = UPPER(:squad) OR squad = 'ALL')"
        params["squad"] = squad
    
    query += " GROUP BY checkout ORDER BY checkout_conversion DESC"
    
    result = db.execute(text(query), params)
    rows = result.fetchall()
    
    return [
        {
            "checkout": row.checkout,
            "initiate_checkout": int(row.initiate_checkout or 0),
            "purchase": int(row.purchase or 0),
            "checkout_conversion": float(row.checkout_conversion or 0),
        }
        for row in rows
    ]


def get_product_summary(db: Session, squad: str = None, period: str = "24h"):
    """
    Retorna métricas de conversão por produto.
    """
    if not _table_exists(db, "tb_daily_product_summary"):
        return []

    sp_today = datetime.now(SAO_PAULO_TZ).date()
    
    if period == "weekly":
        date_start = sp_today - timedelta(days=6)
        date_end = sp_today
    elif period == "monthly":
        date_start = sp_today - timedelta(days=29)
        date_end = sp_today
    else:  # 24h ou daily
        date_start = sp_today
        date_end = sp_today
    
    query = """
        SELECT
            product,
            SUM(initiate_checkout) as initiate_checkout,
            SUM(purchase) as purchase,
            CASE 
                WHEN SUM(initiate_checkout) > 0 
                THEN ROUND((SUM(purchase)::numeric / SUM(initiate_checkout)) * 100, 2)
                ELSE 0 
            END as checkout_conversion
        FROM tb_daily_product_summary
        WHERE metric_date BETWEEN :date_start AND :date_end
    """
    
    params: dict[str, object] = {
        "date_start": date_start,
        "date_end": date_end,
    }
    
    if squad:
        query += " AND (UPPER(squad) = UPPER(:squad) OR squad = 'ALL')"
        params["squad"] = squad
    
    query += " GROUP BY product ORDER BY checkout_conversion DESC"
    
    result = db.execute(text(query), params)
    rows = result.fetchall()
    
    # Consolida aliases no mesmo produto canônico para resposta consistente.
    grouped: dict[str, dict[str, int | float]] = {}
    for row in rows:
        product_raw = str(row.product or "").strip()
        product_resolved = resolve_product(product_raw)
        product = product_resolved if product_resolved != "unknown" else (product_raw or "UNKNOWN")

        agg = grouped.setdefault(
            product,
            {
                "initiate_checkout": 0,
                "purchase": 0,
            },
        )
        agg["initiate_checkout"] = int(agg["initiate_checkout"] or 0) + int(row.initiate_checkout or 0)
        agg["purchase"] = int(agg["purchase"] or 0) + int(row.purchase or 0)

    normalized_rows: list[dict[str, object]] = []
    for product, agg in grouped.items():
        initiate = int(agg["initiate_checkout"] or 0)
        purchase = int(agg["purchase"] or 0)
        conversion = round((purchase / initiate) * 100, 2) if initiate > 0 else 0.0
        normalized_rows.append(
            {
                "product": product,
                "initiate_checkout": initiate,
                "purchase": purchase,
                "checkout_conversion": conversion,
            }
        )

    normalized_rows.sort(
        key=lambda item: (float(item["checkout_conversion"]), int(item["purchase"]), int(item["initiate_checkout"])),
        reverse=True,
    )
    return normalized_rows


def get_squad_checkout_summary(db: Session, period: str = "24h"):
    """
    Retorna métricas de conversão por checkout e squad.
    """
    sp_today = datetime.now(SAO_PAULO_TZ).date()
    
    if period == "weekly":
        date_start = sp_today - timedelta(days=6)
        date_end = sp_today
    elif period == "monthly":
        date_start = sp_today - timedelta(days=29)
        date_end = sp_today
    else:
        date_start = sp_today
        date_end = sp_today
    
    if _table_exists(db, "tb_daily_checkout_summary"):
        query = """
            WITH cost_profit AS (
                SELECT
                    squad,
                    SUM(cost) AS cost,
                    SUM(profit) AS profit,
                    SUM(revenue) AS revenue
                FROM tb_daily_metrics_summary
                WHERE metric_date BETWEEN :date_start AND :date_end
                GROUP BY squad
            ),
            conversions AS (
                SELECT
                    squad,
                    CASE
                        WHEN SUM(initiate_checkout) > 0
                        THEN ROUND((SUM(purchase)::numeric / SUM(initiate_checkout)) * 100, 2)
                        ELSE 0
                    END AS checkout_conversion
                FROM tb_daily_checkout_summary
                WHERE metric_date BETWEEN :date_start AND :date_end
                  AND checkout = 'ALL'
                  AND squad != 'ALL'
                GROUP BY squad
            )
            SELECT
                cp.squad,
                cp.cost,
                cp.profit,
                cp.revenue,
                COALESCE(c.checkout_conversion, 0) AS checkout_conversion,
                ROUND(cp.profit / NULLIF(cp.cost, 0), 4) AS roi
            FROM cost_profit cp
            LEFT JOIN conversions c ON c.squad = cp.squad
            ORDER BY cp.profit DESC
        """
    else:
        query = """
            SELECT
                squad,
                SUM(cost) as cost,
                SUM(profit) as profit,
                SUM(revenue) as revenue,
                ROUND(AVG(checkout_conversion), 2) as checkout_conversion,
                ROUND(SUM(profit) / NULLIF(SUM(cost), 0), 4) as roi
            FROM tb_daily_metrics_summary
            WHERE metric_date BETWEEN :date_start AND :date_end
            GROUP BY squad
            ORDER BY profit DESC
        """
    
    params = {"date_start": date_start, "date_end": date_end}
    result = db.execute(text(query), params)
    rows = result.fetchall()
    
    return [
        {
            "squad": row.squad,
            "cost": float(row.cost or 0),
            "profit": float(row.profit or 0),
            "revenue": float(row.revenue or 0),
            "checkout_conversion": float(row.checkout_conversion or 0),
            "roi": float(row.roi or 0),
        }
        for row in rows
    ]


def get_conversion_breakdown(
    db: Session,
    *,
    period: str = "24h",
    squad: str | None = None,
    checkout: str | None = None,
    product: str | None = None,
) -> list[dict[str, object]]:
    if not _table_exists(db, "tb_daily_conversion_entities"):
        logger.warning("⚠️ Tabela tb_daily_conversion_entities não existe")
        return []

    sp_today = datetime.now(SAO_PAULO_TZ).date()

    if period == "weekly":
        date_start = sp_today - timedelta(days=6)
        date_end = sp_today
    elif period == "monthly":
        date_start = sp_today - timedelta(days=29)
        date_end = sp_today
    else:  # 24h ou daily
        date_start = sp_today
        date_end = sp_today

    logger.info(f"🔍 Buscando conversion breakdown: period={period}, squad={squad}, checkout={checkout}, product={product}")
    logger.info(f"   Data range: {date_start} a {date_end}")

    query = """
        SELECT
            squad,
            checkout,
            product,
            SUM(initiate_checkout) AS initiate_checkout,
            SUM(purchase) AS purchase,
            CASE
                WHEN SUM(initiate_checkout) > 0
                THEN ROUND((SUM(purchase)::numeric / SUM(initiate_checkout)) * 100, 2)
                ELSE 0
            END AS checkout_conversion
        FROM tb_daily_conversion_entities
        WHERE metric_date BETWEEN :date_start AND :date_end
          AND (:squad IS NULL OR UPPER(squad) = UPPER(:squad))
          AND (:checkout IS NULL OR UPPER(checkout) = UPPER(:checkout))
          AND (:product IS NULL OR UPPER(product) = UPPER(:product))
        GROUP BY squad, checkout, product
        ORDER BY purchase DESC, initiate_checkout DESC
    """

    rows = db.execute(
        text(query),
        {
            "date_start": date_start,
            "date_end": date_end,
            "squad": squad,
            "checkout": checkout,
            "product": product,
        },
    ).fetchall()

    logger.info(f"   Resultados da query: {len(rows)} linhas retornadas")

    normalized: list[dict[str, object]] = []
    for row in rows:
        product_raw = str(row.product or "").strip()
        product_resolved = resolve_product(product_raw)
        product_value = product_resolved if product_resolved != "unknown" else (product_raw or "UNKNOWN")

        if product and str(product_value).upper() != str(product).upper():
            continue

        normalized.append(
            {
                "squad": str(row.squad or "unknown"),
                "checkout": str(row.checkout or "unknown"),
                "product": product_value,
                "initiate_checkout": int(row.initiate_checkout or 0),
                "purchase": int(row.purchase or 0),
                "checkout_conversion": float(row.checkout_conversion or 0),
            }
        )

    logger.info(f"   Resultados após normalização: {len(normalized)} registros")

    return normalized


