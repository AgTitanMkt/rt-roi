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
        }

    if not unique_payload:
        return {"inserted": 0, "updated": 0, "ignored": len(data)}

    previous_targets: list[tuple[str, datetime]] = []
    for campaign_id, metric_at in unique_payload.keys():
        metric_at_sp = metric_at.astimezone(SAO_PAULO_TZ)
        if metric_at_sp.hour == 0:
            continue
        previous_targets.append((campaign_id, metric_at - timedelta(hours=1)))

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


def get_summary(db: Session, source: str = None):
    sp_today = datetime.now(SAO_PAULO_TZ).date()
    sp_yesterday = sp_today - timedelta(days=1)

    query = """
        SELECT
            metric_date as date,
            SUM(cost) as cost,
            SUM(profit) as profit,
            SUM(revenue) as revenue,
            ROUND(SUM(profit) / NULLIF(SUM(cost), 0), 2) as roi
        FROM tb_daily_metrics_summary
        WHERE metric_date IN (:sp_today, :sp_yesterday)
    """

    params: dict[str, object] = {
        "sp_today": sp_today,
        "sp_yesterday": sp_yesterday,
    }

    if source:
        query += " AND UPPER(squad) = UPPER(:source)"
        params["source"] = source

    query += " GROUP BY metric_date ORDER BY metric_date DESC"

    result = db.execute(text(query), params)
    rows = result.fetchall()

    if not rows:
        return {
            "today": {"cost": None, "profit": None, "revenue": None, "roi": None},
            "yesterday": {"cost": None, "profit": None, "revenue": None, "roi": None},
            "comparison": {"cost_change": None, "profit_change": None, "revenue_change": None, "roi_change": None}
        }

    today_data = None
    yesterday_data = None
    today_date = str(sp_today)
    yesterday_date = str(sp_yesterday)

    for row in rows:
        if row.date and str(row.date) == today_date:
            today_data = row
        elif row.date and str(row.date) == yesterday_date:
            yesterday_data = row

    result_obj = {
        "today": {
            "cost": _q2(today_data.cost) if today_data else None,
            "profit": _q2(today_data.profit) if today_data else None,
            "revenue": _q2(today_data.revenue) if today_data else None,
            "roi": _q4(today_data.roi) if today_data else None,

        },
        "yesterday": {
            "cost": _q2(yesterday_data.cost) if yesterday_data else None,
            "profit": _q2(yesterday_data.profit) if yesterday_data else None,
            "revenue": _q2(yesterday_data.revenue) if yesterday_data else None,
            "roi": _q4(yesterday_data.roi) if yesterday_data else None,
        },
        "comparison": {
            "cost_change": None,
            "profit_change": None,
            "revenue_change": None,
            "roi_change": None
        }
    }

    today_cost_value = float(today_data.cost) if (today_data and today_data.cost is not None) else 0.0
    today_profit_value = float(today_data.profit) if (today_data and today_data.profit is not None) else 0.0
    today_revenue_value = float(today_data.revenue) if (today_data and today_data.revenue is not None) else 0.0
    today_roi_value = float(today_data.roi) if (today_data and today_data.roi is not None) else 0.0

    if yesterday_data:
        if yesterday_data.cost and yesterday_data.cost != 0:
            cost_change = ((today_cost_value - float(yesterday_data.cost)) / float(yesterday_data.cost)) * 100
            result_obj["comparison"]["cost_change"] = _q2(cost_change)

        if yesterday_data.profit and yesterday_data.profit != 0:
            profit_change = ((today_profit_value - float(yesterday_data.profit)) / float(yesterday_data.profit)) * 100
            result_obj["comparison"]["profit_change"] = _q2(profit_change)

        if yesterday_data.roi and yesterday_data.roi != 0:
            roi_change = ((today_roi_value - float(yesterday_data.roi)) / float(yesterday_data.roi)) * 100
            result_obj["comparison"]["roi_change"] = _q2(roi_change)

        if yesterday_data.revenue and yesterday_data.revenue != 0:
            revenue_change = ((today_revenue_value - float(yesterday_data.revenue)) / float(yesterday_data.revenue)) * 100
            result_obj["comparison"]["revenue_change"] = _q2(revenue_change)

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

