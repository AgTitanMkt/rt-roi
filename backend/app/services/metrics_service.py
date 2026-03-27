from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session
from sqlalchemy import text, tuple_
from ..models.metrics import MetricsSnapshot


SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")


def _q2(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q4(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

def insert_metrics(db: Session, data: list):
    if not data:
        return {"inserted": 0, "ignored": 0}

    # Ignora somente quando ROI/Profit/Cost forem iguais (com a mesma precisao do banco).
    unique_payload = {}
    for item in data:
        norm_item = {
            **item,
            "cost": _q2(item["cost"]),
            "profit": _q2(item["profit"]),
            "roi": _q4(item["roi"]),
        }
        key = (norm_item["cost"], norm_item["profit"], norm_item["roi"])
        unique_payload.setdefault(key, norm_item)

    keys = list(unique_payload.keys())

    existing_rows = db.query(
        MetricsSnapshot.cost,
        MetricsSnapshot.profit,
        MetricsSnapshot.roi,
    ).filter(
        tuple_(MetricsSnapshot.cost, MetricsSnapshot.profit, MetricsSnapshot.roi).in_(keys)
    ).all()

    existing_keys = {(row.cost, row.profit, row.roi) for row in existing_rows}

    rows_to_insert = [
        item
        for key, item in unique_payload.items()
        if key not in existing_keys
    ]

    if not rows_to_insert:
        return {"inserted": 0, "ignored": len(data)}

    objects = [
        MetricsSnapshot(
            metric_at=item["metric_at"],
            source_alias=item["source_alias"],
            cost=item["cost"],
            profit=item["profit"],
            roi=item["roi"],
        )
        for item in rows_to_insert
    ]

    db.bulk_save_objects(objects)
    db.commit()
    return {
        "inserted": len(rows_to_insert),
        "ignored": len(data) - len(rows_to_insert),
    }

def get_summary(db: Session, source: str = None):
    sp_today = datetime.now(SAO_PAULO_TZ).date()
    sp_yesterday = sp_today - timedelta(days=1)

    query = """
        SELECT
            timezone('America/Sao_Paulo', metric_at)::date as date,
            SUM(cost) as cost,
            SUM(profit) as profit,
            ROUND(SUM(profit) / NULLIF(SUM(cost), 0), 2) as roi
        FROM tb_metrics_snapshots
        WHERE timezone('America/Sao_Paulo', metric_at)::date IN (:sp_today, :sp_yesterday)
    """

    params = {
        "sp_today": sp_today,
        "sp_yesterday": sp_yesterday,
    }

    if source:
        query += " AND source_alias = :source"
        params["source"] = source

    query += " GROUP BY timezone('America/Sao_Paulo', metric_at)::date ORDER BY timezone('America/Sao_Paulo', metric_at)::date DESC"

    result = db.execute(text(query), params)
    rows = result.fetchall()
    
    if not rows:
        return {
            "today": {"cost": None, "profit": None, "roi": None},
            "yesterday": {"cost": None, "profit": None, "roi": None},
            "comparison": {"cost_change": None, "profit_change": None, "roi_change": None}
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
            "roi": _q4(today_data.roi) if today_data else None,
        },
        "yesterday": {
            "cost": _q2(yesterday_data.cost) if yesterday_data else None,
            "profit": _q2(yesterday_data.profit) if yesterday_data else None,
            "roi": _q4(yesterday_data.roi) if yesterday_data else None,
        },
        "comparison": {
            "cost_change": None,
            "profit_change": None,
            "roi_change": None
        }
    }

    # Calcular variação percentual
    today_cost_value = float(today_data.cost) if (today_data and today_data.cost is not None) else 0.0
    today_profit_value = float(today_data.profit) if (today_data and today_data.profit is not None) else 0.0
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

    return result_obj

def get_metrics_by_hour(db: Session, source: str = None):
    sp_today = datetime.now(SAO_PAULO_TZ).date()

    query = """
        SELECT
            EXTRACT(HOUR FROM timezone('America/Sao_Paulo', metric_at))::text as hour,
            SUM(cost) as cost,
            SUM(profit) as profit,
            ROUND(SUM(profit) / NULLIF(SUM(cost), 0), 2) as roi
        FROM tb_metrics_snapshots
        WHERE timezone('America/Sao_Paulo', metric_at)::date = :sp_today
    """

    params = {"sp_today": sp_today}

    if source:
        query += " AND source_alias = :source"
        params["source"] = source

    query += " GROUP BY hour ORDER BY hour"

    result = db.execute(text(query), params)

    rows = result.fetchall()
    return rows
