from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta, date
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session
from sqlalchemy import func, text
from ..models.metrics import DailySummary, HourlyMetric


SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")


def _q2(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q4(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _normalize_squad(value: str | None) -> str:
    squad = str(value or "").strip()
    return squad or "unknown"


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
            func.coalesce(func.sum(HourlyMetric.checkout_conversion), 1).label("checkout_conversion"),
        ).filter(
            HourlyMetric.metric_at >= day_start,
            HourlyMetric.metric_at < day_end,
            HourlyMetric.squad == squad,
        ).first()

        cost = _q2(getattr(agg, "cost", 0))
        profit = _q2(getattr(agg, "profit", 0))
        revenue = _q2(getattr(agg, "revenue", 0))
        checkout_conversion = _q2(getattr(agg, "checkout_conversion", 1))
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
        if not campaign_id or metric_at is None:
            continue

        unique_payload[(campaign_id, metric_at)] = {
            "campaign_id": campaign_id,
            "metric_at": metric_at,
            "squad": _normalize_squad(item.get("squad")),
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
            existing.squad = item["squad"]
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
                    metric_at=item["metric_at"],
                    squad=item["squad"],
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

    _refresh_daily_summary(db, affected_summary_keys)
    db.commit()

    return {
        "inserted": inserted,
        "updated": updated,
        "ignored": max(len(data) - len(unique_payload), 0),
    }


def get_summary(db: Session, source: str = None, period: str = "24h"):
    sp_today = datetime.now(SAO_PAULO_TZ).date()

    if period == "weekly":
        current_start = sp_today - timedelta(days=6)
        current_end = sp_today
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=6)
    elif period == "monthly":
        current_start = sp_today - timedelta(days=29)
        current_end = sp_today
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=29)
    else:
        # 24h/daily seguem o comportamento original (hoje vs ontem)
        current_start = sp_today
        current_end = sp_today
        previous_start = sp_today - timedelta(days=1)
        previous_end = sp_today - timedelta(days=1)

    def _fetch_range_agg(start_date: date, end_date: date):
        query = """
            SELECT
                SUM(cost) as cost,
                SUM(profit) as profit,
                SUM(revenue) as revenue,
                ROUND(AVG(checkout_conversion), 2) as checkout,
                ROUND(SUM(profit) / NULLIF(SUM(cost), 0), 4) as roi
            FROM tb_daily_metrics_summary
            WHERE metric_date BETWEEN :start_date AND :end_date
        """

        params: dict[str, object] = {
            "start_date": start_date,
            "end_date": end_date,
        }

        if source:
            query += " AND UPPER(squad) = UPPER(:source)"
            params["source"] = source

        return db.execute(text(query), params).fetchone()

    current_data = _fetch_range_agg(current_start, current_end)
    previous_data = _fetch_range_agg(previous_start, previous_end)

    result_obj = {
        "today": {
            "cost": _q2(getattr(current_data, "cost", 0) or 0),
            "profit": _q2(getattr(current_data, "profit", 0) or 0),
            "revenue": _q2(getattr(current_data, "revenue", 0) or 0),
            "checkout": _q2(getattr(current_data, "checkout", 0) or 0),
            "roi": _q4(getattr(current_data, "roi", 0) or 0),
        },
        "yesterday": {
            "cost": _q2(getattr(previous_data, "cost", 0) or 0),
            "profit": _q2(getattr(previous_data, "profit", 0) or 0),
            "revenue": _q2(getattr(previous_data, "revenue", 0) or 0),
            "checkout": _q2(getattr(previous_data, "checkout", 0) or 0),
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
    current_checkout = float(getattr(current_data, "checkout", 0) or 0)
    current_roi = float(getattr(current_data, "roi", 0) or 0)

    previous_cost = float(getattr(previous_data, "cost", 0) or 0)
    previous_profit = float(getattr(previous_data, "profit", 0) or 0)
    previous_revenue = float(getattr(previous_data, "revenue", 0) or 0)
    previous_checkout = float(getattr(previous_data, "checkout", 0) or 0)
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


def get_metrics_by_period(db: Session, period: str = "24h", source: str = None):
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
    }
    
    result = db.execute(text(query), params)
    rows = result.fetchall()
    
    # Reverter ordem para crescente (mais antigo primeiro)
    return list(reversed(rows)) if rows else []

