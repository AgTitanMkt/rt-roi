from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta, date
from typing import TypedDict
from zoneinfo import ZoneInfo
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func, text
from ..models.metrics import DailySummary, HourlyMetric
from ..core.user_scope import resolve_user_squad_scope
from .redtrack.mappings import resolve_product, resolve_squad, resolve_checkout, normalize_mapping_token
from .redtrack.settings import SQUAD_MAPPINGS

logger = logging.getLogger(__name__)


SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")


def _product_token(value: str | None) -> str:
    return normalize_mapping_token(value)


def _as_int(value, default: int = 0) -> int:
    try:
        return int(value if value is not None else default)
    except (TypeError, ValueError):
        return default


def _roi_percent(value) -> Decimal:
    raw = Decimal(str(value or 0))
    # Alguns fluxos antigos já salvam ROI em percentual (ex.: 25.6),
    # enquanto os novos gravam como razão (ex.: 0.256).
    # Normalizamos apenas quando ainda está em razão.
    if abs(raw) <= Decimal("1.5"):
        return _q2(raw * 100)
    return _q2(raw)


def _roi_percent_from_cost_profit(cost, profit) -> Decimal:
    cost_decimal = Decimal(str(cost or 0))
    profit_decimal = Decimal(str(profit or 0))
    if cost_decimal <= 0:
        return _q2(0)
    return _q2((profit_decimal / cost_decimal) * 100)


def _q2(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q4(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


ALLOWED_SQUADS = {
    str(entry.get("value") or "").strip().upper()
    for entry in SQUAD_MAPPINGS
    if str(entry.get("value") or "").strip()
}


def _build_squad_scope_clause(source: str | None, column_name: str = "squad", param_name: str = "source") -> tuple[str, dict[str, object]]:
    scope = normalize_mapping_token(source)
    if not scope:
        return "", {}

    # Suporte especial para filtro YouTube agregado
    if scope in ("youtube", "yt"):
        squads = ("YTS", "YTF")
        placeholders = ", ".join(f":{param_name}_{idx}" for idx in range(len(squads)))
        clause = f" AND UPPER({column_name}) IN ({placeholders})"
        params = {f"{param_name}_{idx}": squad for idx, squad in enumerate(squads)}
        return clause, params
    # Suporte especial para filtro Native agregado
    if scope == "native":
        squads = ("NTE", "NTL")
        placeholders = ", ".join(f":{param_name}_{idx}" for idx in range(len(squads)))
        clause = f" AND UPPER({column_name}) IN ({placeholders})"
        params = {f"{param_name}_{idx}": squad for idx, squad in enumerate(squads)}
        return clause, params

    squads = resolve_user_squad_scope(scope)
    if squads:
        placeholders = ", ".join(f":{param_name}_{idx}" for idx in range(len(squads)))
        clause = f" AND UPPER({column_name}) IN ({placeholders})"
        params = {f"{param_name}_{idx}": squad for idx, squad in enumerate(squads)}
        return clause, params

    return f" AND UPPER({column_name}) = UPPER(:{param_name})", {param_name: source}


def _normalize_dimension_value(raw: str | None, resolved: str | None) -> str:
    raw_value = str(raw or "").strip()
    if not raw_value:
        return "UNKNOWN"

    resolved_value = str(resolved or "").strip()
    if resolved_value and resolved_value.lower() != "unknown":
        return resolved_value.upper()

    # Mantem o valor original quando o mapeamento nao encontra alias.
    return raw_value.upper()


def _normalize_squad(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "UNKNOWN"

    resolved = resolve_squad(raw)
    normalized = _normalize_dimension_value(raw, resolved)

    # Se esta entre os squads canonicos, mantem formato esperado.
    if normalized in ALLOWED_SQUADS:
        return normalized

    return normalized


class MetricPayload(TypedDict):
    campaign_id: str
    offer_id: str | None
    metric_at: datetime
    squad: str
    checkout: str
    product: str
    cost: Decimal
    profit: Decimal
    revenue: Decimal
    roi: Decimal
    checkout_conversion: Decimal
    is_cumulative: bool


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

    squad_clause, squad_params = _build_squad_scope_clause(source, column_name="squad", param_name="source")

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

    if squad_clause:
        query += squad_clause
        params.update(squad_params)
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

    unique_payload: dict[tuple[str, datetime], MetricPayload] = {}
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

    previous_by_key: dict[tuple[str, datetime], HourlyMetric] = {}
    if previous_targets:
        previous_campaign_ids = list({campaign_id for campaign_id, _ in previous_targets})
        previous_metric_ats = list({metric_at for _, metric_at in previous_targets})
        previous_rows = db.query(HourlyMetric).filter(
            HourlyMetric.campaign_id.in_(previous_campaign_ids),  # type: ignore[attr-defined]
            HourlyMetric.metric_at.in_(previous_metric_ats),  # type: ignore[attr-defined]
        ).all()
        for row in previous_rows:
            if row.metric_at is None or not isinstance(row.metric_at, datetime):
                continue
            if not isinstance(row, HourlyMetric):
                continue
            metric_at_dt: datetime = row.metric_at  # type: ignore
            previous_by_key[(str(row.campaign_id), metric_at_dt)] = row

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

        current_cost = Decimal(str(item["cost"] or 0))
        previous_cost = Decimal(str(previous_row.cost or 0))
        item["cost"] = _q2(max(current_cost - previous_cost, Decimal("0")))

        current_profit = Decimal(str(item["profit"] or 0))
        previous_profit = Decimal(str(previous_row.profit or 0))
        item["profit"] = _q2(max(current_profit - previous_profit, Decimal("0")))

        current_revenue = Decimal(str(item["revenue"] or 0))
        previous_revenue = Decimal(str(previous_row.revenue or 0))
        item["revenue"] = _q2(max(current_revenue - previous_revenue, Decimal("0")))

        current_checkout = Decimal(str(item["checkout_conversion"] or 0))
        previous_checkout = Decimal(str(previous_row.checkout_conversion or 0))
        item["checkout_conversion"] = _q2(max(current_checkout - previous_checkout, Decimal("0")))

        item["roi"] = _q4((item["profit"] / item["cost"]) if item["cost"] > 0 else 0)

    campaign_ids = list({k[0] for k in unique_payload})
    metric_ats = list({k[1] for k in unique_payload})

    existing_rows = db.query(HourlyMetric).filter(
        HourlyMetric.campaign_id.in_(campaign_ids),  # type: ignore[attr-defined]
        HourlyMetric.metric_at.in_(metric_ats),  # type: ignore[attr-defined]
    ).all()
    existing_by_key: dict[tuple[str, datetime], HourlyMetric] = {}
    for row in existing_rows:
        if row.metric_at is None or not isinstance(row.metric_at, datetime):
            continue
        if not isinstance(row, HourlyMetric):
            continue
        metric_at_dt: datetime = row.metric_at  # type: ignore
        existing_by_key[(str(row.campaign_id), metric_at_dt)] = row

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
    squad_clause, squad_params = _build_squad_scope_clause(source)

    # Sem filtros de checkout/produto, usa o snapshot diário mais recente disponível.
    if not use_hourly_for_summary:
        latest_date_query = """
            SELECT MAX(metric_date) AS latest_date
            FROM tb_daily_metrics_summary
            WHERE 1=1
        """
        latest_params: dict[str, object] = {}
        if squad_clause:
            latest_date_query += squad_clause
            latest_params.update(squad_params)

        latest_row = db.execute(text(latest_date_query), latest_params).fetchone()
        latest_daily_date_raw = getattr(latest_row, "latest_date", None) if latest_row else None
        latest_daily_date = latest_daily_date_raw if isinstance(latest_daily_date_raw, date) else None
        reference_date: date = latest_daily_date or sp_today
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
                  {squad_clause}
                  AND (:checkout IS NULL OR UPPER(checkout_type) = UPPER(:checkout))
                  AND (
                    :product IS NULL
                    OR regexp_replace(UPPER(product), '[\\s_-]+', '', 'g')
                       = regexp_replace(UPPER(:product), '[\\s_-]+', '', 'g')
                  )
            """
            params: dict[str, object] = {
                "start_date": start_date,
                "end_date": end_date,
                "source": source,
                "checkout": checkout,
                "product": product,
            }
            params.update(squad_params)
            query = query.replace("{squad_clause}", squad_clause)
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

        params: dict[str, object] = {
            "start_date": start_date,
            "end_date": end_date,
        }

        if squad_clause:
            query += squad_clause
            params.update(squad_params)

        result = db.execute(text(query), params).fetchone()

        # Fallback: se não houver cost/profit/revenue e checkout_avg, busca média em tb_daily_checkout_summary
        if (not result or (getattr(result, "cost", None) is None and getattr(result, "profit", None) is None and getattr(result, "revenue", None) is None)):
            fallback_query = """
                SELECT
                    metric_date,
                    SUM(initiate_checkout) as initiate_checkout,
                    SUM(purchase) as purchase
                FROM tb_daily_checkout_summary
                WHERE metric_date BETWEEN :start_date AND :end_date
                GROUP BY metric_date
            """
            fallback_params = {
                "start_date": start_date,
                "end_date": end_date,
            }
            fallback_rows = db.execute(text(fallback_query), fallback_params).fetchall()
            # Calcula a média das conversões diárias em Python
            daily_conversions = []
            for row in fallback_rows:
                initiate = row.initiate_checkout or 0
                purchase = row.purchase or 0
                if initiate > 0:
                    daily_conversions.append((purchase / initiate) * 100)
            checkout_avg = round(sum(daily_conversions) / len(daily_conversions), 2) if daily_conversions else 0.0
            # Retorna um objeto compatível com o esperado
            from types import SimpleNamespace
            return SimpleNamespace(
                cost=None,
                profit=None,
                revenue=None,
                checkout_avg=checkout_avg,
                roi=None,
            )

        return result

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
            "roi": _roi_percent_from_cost_profit(getattr(current_data, "cost", 0) or 0, getattr(current_data, "profit", 0) or 0),
        },
        "yesterday": {
            "cost": _q2(getattr(previous_data, "cost", 0) or 0),
            "profit": _q2(getattr(previous_data, "profit", 0) or 0),
            "revenue": _q2(getattr(previous_data, "revenue", 0) or 0),
            "checkout": previous_checkout if previous_checkout is not None else _q2(getattr(previous_data, "checkout_avg", 0) or 0),
            "roi": _roi_percent_from_cost_profit(getattr(previous_data, "cost", 0) or 0, getattr(previous_data, "profit", 0) or 0),
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
    current_roi = float(result_obj["today"]["roi"] or 0)

    previous_cost = float(getattr(previous_data, "cost", 0) or 0)
    previous_profit = float(getattr(previous_data, "profit", 0) or 0)
    previous_revenue = float(getattr(previous_data, "revenue", 0) or 0)
    previous_checkout = float(result_obj["yesterday"]["checkout"] or 0)
    previous_roi = float(result_obj["yesterday"]["roi"] or 0)

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
    print(f"[DEBUG] get_metrics_by_hour params: source={source}")
    now_sp = datetime.now(SAO_PAULO_TZ)
    sp_today = now_sp.date()
    sp_yesterday = sp_today - timedelta(days=1)
    squad_clause, squad_params = _build_squad_scope_clause(source)

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
              {squad_clause}
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
    params.update(squad_params)

    query = query.replace("{squad_clause}", squad_clause)

    result = db.execute(text(query), params)
    rows = result.fetchall()

    print(f"[DEBUG] get_metrics_by_hour result: {rows}")

    return rows


def get_metrics_by_period(
    db: Session,
    start_date: date | None,
    end_date: date | None,
    squad: str = None,
    checkout: str = None,
    product: str = None,
    period: str = "daily",
    timezone: str = None,
    revenue: bool = False,
    offer_id: str = None,
    checkout_type: str = None,
):
    print(f"[DEBUG] get_metrics_by_period params: start_date={start_date}, end_date={end_date}, squad={squad}, checkout={checkout}, product={product}, period={period}, timezone={timezone}, revenue={revenue}, offer_id={offer_id}, checkout_type={checkout_type}")
    is_hourly = period in ("24h", "hourly", "daily")
    now_sp = datetime.now(SAO_PAULO_TZ)
    sp_today = now_sp.date()
    sp_yesterday = sp_today - timedelta(days=1)
    limit_hours: int | None = None
    squad_clause, squad_params = _build_squad_scope_clause(squad, column_name="squad", param_name="squad")

    # Determinar intervalo de datas conforme o período
    if start_date and end_date:
        date_start = min(start_date, end_date)
        date_end = max(start_date, end_date)
    elif period == "24h":
        date_start = sp_today - timedelta(days=1)
        date_end = sp_today
        limit_hours = 24
    elif period == "daily":
        date_start = sp_today
        date_end = sp_today
        limit_hours = 24
    elif period == "weekly":
        date_start = sp_today - timedelta(days=6)  # 7 dias incluindo hoje
        date_end = sp_today
        limit_hours = None  # Sem limite
    elif period == "monthly":
        date_start = sp_today - timedelta(days=29)  # 30 dias incluindo hoje
        date_end = sp_today
        limit_hours = None  # Sem limite
    else:
        date_start = sp_today - timedelta(days=1)
        date_end = sp_today
        limit_hours = 24

    # Construir query dinâmica
    limit_clause = f"LIMIT {limit_hours}" if limit_hours else ""
    if is_hourly:
        # Agrupamento por HORA
        query = f"""
            SELECT
                timezone('America/Sao_Paulo', metric_at)::date::text as metric_date,
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
                CASE WHEN :squad IS NULL THEN NULL::text ELSE :squad END as squad
            FROM tb_hourly_metrics
            WHERE timezone('America/Sao_Paulo', metric_at)::date BETWEEN :date_start AND :date_end
              {squad_clause}
              AND (:checkout IS NULL OR UPPER(checkout_type) = UPPER(:checkout))
              AND (
                :product IS NULL
                OR regexp_replace(UPPER(product), '[\\s_-]+', '', 'g')
                   = regexp_replace(UPPER(:product), '[\\s_-]+', '', 'g')
              )
            GROUP BY
                date_trunc('hour', timezone('America/Sao_Paulo', metric_at)),
                EXTRACT(HOUR FROM timezone('America/Sao_Paulo', metric_at)),
                timezone('America/Sao_Paulo', metric_at)::date
            ORDER BY slot DESC
            {limit_clause}
        """
    else:
        # Agrupamento por DIA
        query = f"""
            SELECT
                timezone('America/Sao_Paulo', metric_at)::date::text as metric_date,
                to_char(timezone('America/Sao_Paulo', metric_at)::date, 'YYYY-MM-DD"T"00:00:00') as slot,
                '0' as hour,
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
                CASE WHEN :squad IS NULL THEN NULL::text ELSE :squad END as squad
            FROM tb_hourly_metrics
            WHERE timezone('America/Sao_Paulo', metric_at)::date BETWEEN :date_start AND :date_end
              {squad_clause}
              AND (:checkout IS NULL OR UPPER(checkout_type) = UPPER(:checkout))
              AND (
                :product IS NULL
                OR regexp_replace(UPPER(product), '[\\s_-]+', '', 'g')
                   = regexp_replace(UPPER(:product), '[\\s_-]+', '', 'g')
              )
            GROUP BY
                timezone('America/Sao_Paulo', metric_at)::date
            ORDER BY slot DESC
        """

    params: dict[str, object] = {
        "sp_today": sp_today,
        "sp_yesterday": sp_yesterday,
        "date_start": date_start,
        "date_end": date_end,
        "squad": squad,
        "checkout": checkout,
        "product": product,
    }
    params.update(squad_params)

    import logging
    logger = logging.getLogger("metrics_service")
    logger.info(f"[get_metrics_by_period] SQL Query: {query}")
    logger.info(f"[get_metrics_by_period] Params: {params}")
    result = db.execute(text(query), params)
    rows = result.fetchall()

    print(f"[DEBUG] get_metrics_by_period result: {rows}")

    # Para weekly/monthly, garantir série contínua de dias
    if not is_hourly:
        num_days = (date_end - date_start).days + 1
        date_list = [(date_start + timedelta(days=i)).isoformat() for i in range(num_days)]
        row_by_date = {getattr(row, "metric_date", None): row for row in rows}
        filled = []
        for d in date_list:
            if d in row_by_date:
                filled.append(row_by_date[d])
            else:
                # Preenche com zeros
                filled.append(type("Row", (), {
                    "metric_date": d,
                    "slot": f"{d}T00:00:00",
                    "hour": "0",
                    "day": "past",
                    "checkout_conversion": 0.0,
                    "cost": 0.0,
                    "profit": 0.0,
                    "revenue": 0.0,
                    "roi": 0.0,
                    "squad": squad or ""
                })())
        # Ordem crescente
        return filled

    # Para daily, garantir série contínua de 24 horas
    if is_hourly and period == "daily":
        # rows: lista de resultados do banco agrupados por hora
        row_by_hour = {str(getattr(row, "hour", None)): row for row in rows}
        filled = []
        for h in range(24):
            hour_str = str(h)
            if hour_str in row_by_hour:
                filled.append(row_by_hour[hour_str])
            else:
                filled.append(type("Row", (), {
                    "metric_date": date_start.isoformat(),
                    "slot": f"{date_start.isoformat()}T{h:02d}:00:00",
                    "hour": hour_str,
                    "day": "today",
                    "checkout_conversion": 0.0,
                    "cost": 0.0,
                    "profit": 0.0,
                    "revenue": 0.0,
                    "roi": 0.0,
                    "squad": squad or ""
                })())
        return filled

    # Reverter ordem para crescente (mais antigo primeiro)
    return list(reversed(rows)) if rows else []


def get_checkout_summary(db: Session, squad: str = None, period: str = "24h"):
    print(f"[DEBUG] get_checkout_summary params: squad={squad}, period={period}")
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

    squad_clause, squad_params = _build_squad_scope_clause(squad)

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
    
    if squad_clause:
        query += squad_clause
        params.update(squad_params)
    else:
        query += " AND squad = 'ALL'"

    query += " GROUP BY checkout ORDER BY checkout_conversion DESC"
    
    result = db.execute(text(query), params)
    rows = result.fetchall()

    print(f"[DEBUG] get_checkout_summary result: {rows}")

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

    squad_clause, squad_params = _build_squad_scope_clause(squad)

    if squad:
        if not _table_exists(db, "tb_daily_conversion_entities"):
            return []

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
            FROM tb_daily_conversion_entities
            WHERE metric_date BETWEEN :date_start AND :date_end
        """

        params: dict[str, object] = {
            "date_start": date_start,
            "date_end": date_end,
        }

        if squad_clause:
            query += squad_clause
            params.update(squad_params)
        else:
            query += " AND squad = 'ALL'"

        query += " GROUP BY product ORDER BY checkout_conversion DESC"

        rows = db.execute(text(query), params).fetchall()
    else:
        if not _table_exists(db, "tb_daily_product_summary"):
            return []

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

        params = {
            "date_start": date_start,
            "date_end": date_end,
        }

        query += " AND squad = 'ALL'"
        query += " GROUP BY product ORDER BY checkout_conversion DESC"
        rows = db.execute(text(query), params).fetchall()

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
            "roi": float(row.roi or 0) * 100,
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
    date_start: date | None = None,
    date_end: date | None = None,
) -> list[dict[str, object]]:
    if not _table_exists(db, "tb_daily_conversion_entities"):
        logger.warning("⚠️ Tabela tb_daily_conversion_entities não existe")
        return []

    sp_today = datetime.now(SAO_PAULO_TZ).date()

    if date_start and date_end:
        range_start = min(date_start, date_end)
        range_end = max(date_start, date_end)
    elif period == "weekly":
        range_start = sp_today - timedelta(days=6)
        range_end = sp_today
    elif period == "monthly":
        range_start = sp_today - timedelta(days=29)
        range_end = sp_today
    else:  # 24h ou daily
        squad_clause, squad_params = _build_squad_scope_clause(squad)
        latest_query = """
            SELECT MAX(metric_date) AS latest_date
            FROM tb_daily_conversion_entities
            WHERE metric_date <= :today
        """
        if squad_clause:
            latest_query += squad_clause
        # Para admin sem filtro de squad, não adiciona filtro de squad (busca todos)
        latest_query += """
              AND (:checkout IS NULL OR UPPER(checkout) = UPPER(:checkout))
              AND (
                :product IS NULL
                OR regexp_replace(UPPER(product), '[\\s_-]+', '', 'g')
                   = regexp_replace(UPPER(:product), '[\\s_-]+', '', 'g')
              )
        """
        latest_row = db.execute(
            text(latest_query),
            {
                "today": sp_today,
                "checkout": checkout,
                "product": product,
                **squad_params,
            },
        ).fetchone()
        latest_date = getattr(latest_row, "latest_date", None) if latest_row else None

        reference_date = latest_date if isinstance(latest_date, date) else sp_today
        range_start = reference_date
        range_end = reference_date

    logger.info(f"🔍 Buscando conversion breakdown: period={period}, squad={squad}, checkout={checkout}, product={product}")
    logger.info(f"   Data range: {range_start} a {range_end}")

    squad_clause, squad_params = _build_squad_scope_clause(squad)
    query = f"""
        SELECT
            metric_date,
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
          {squad_clause}
          AND (:checkout IS NULL OR UPPER(checkout) = UPPER(:checkout))
          AND (
            :product IS NULL
            OR regexp_replace(UPPER(product), '[\\s_-]+', '', 'g')
               = regexp_replace(UPPER(:product), '[\\s_-]+', '', 'g')
          )
        GROUP BY metric_date, squad, checkout, product
        ORDER BY metric_date ASC, purchase DESC, initiate_checkout DESC
    """

    rows = db.execute(
        text(query),
        {
            "date_start": range_start,
            "date_end": range_end,
            "checkout": checkout,
            "product": product,
            **squad_params,
        },
    ).fetchall()

    metric_date_marker = str(range_start) if range_start == range_end else None

    logger.info(f"   Resultados da query: {len(rows)} linhas retornadas")

    # O frontend agrega esse endpoint por checkout/produto e não precisa de placeholders.
    # Preencher dias ausentes aqui introduz linhas artificiais com zero e ainda pode
    # sobrescrever combinações reais quando existem múltiplos squads na mesma data.
    fill_dates = False
    date_list = None

    # Normalização dos dados
    normalized: list[dict[str, object]] = []
    row_by_date_checkout_product = {}
    for row in rows:
        product_raw = str(row.product or "").strip()
        product_resolved = resolve_product(product_raw)
        product_value = product_resolved if product_resolved != "unknown" else (product_raw or "UNKNOWN")

        if product and _product_token(product_value) != _product_token(product):
            continue

        metric_date_value = getattr(row, "metric_date", None)
        metric_date_marker = metric_date_value.isoformat() if isinstance(metric_date_value, date) else (str(metric_date_value) if metric_date_value else (str(range_start) if range_start == range_end else None))
        key = (metric_date_marker, str(row.checkout or "unknown"), product_value)
        payload = {
            "metric_date": metric_date_marker,
            "squad": str(row.squad or "unknown"),
            "checkout": str(row.checkout or "unknown"),
            "product": product_value,
            "initiate_checkout": int(row.initiate_checkout or 0),
            "purchase": int(row.purchase or 0),
            "checkout_conversion": float(row.checkout_conversion or 0),
        }
        row_by_date_checkout_product[key] = payload
        normalized.append(payload)


    # Quando o filtro representa setor com multiplos squads (ex.: yt = yts + ytf),
    # consolida o retorno para evitar linhas duplicadas por squad no frontend.
    scoped_squads = resolve_user_squad_scope(squad)
    if scoped_squads and len(scoped_squads) > 1:
        grouped: dict[tuple[str | None, str, str], dict[str, object]] = {}
        scope_label = normalize_mapping_token(squad).upper() or "ALL"

        for item in normalized:
            key = (
                str(item.get("metric_date") or "") or None,
                str(item.get("checkout") or "unknown"),
                str(item.get("product") or "unknown"),
            )
            agg = grouped.setdefault(
                key,
                {
                    "metric_date": key[0],
                    "squad": scope_label,
                    "checkout": key[1],
                    "product": key[2],
                    "initiate_checkout": 0,
                    "purchase": 0,
                },
            )
            agg["initiate_checkout"] = _as_int(agg.get("initiate_checkout")) + _as_int(item.get("initiate_checkout"))
            agg["purchase"] = _as_int(agg.get("purchase")) + _as_int(item.get("purchase"))

        normalized = []
        for agg in grouped.values():
            initiate = _as_int(agg.get("initiate_checkout"))
            purchase = _as_int(agg.get("purchase"))
            conversion = round((purchase / initiate) * 100, 2) if initiate > 0 else 0.0
            normalized.append(
                {
                    "metric_date": agg["metric_date"],
                    "squad": agg["squad"],
                    "checkout": agg["checkout"],
                    "product": agg["product"],
                    "initiate_checkout": initiate,
                    "purchase": purchase,
                    "checkout_conversion": conversion,
                }
            )

        normalized.sort(
            key=lambda item: (int(item["purchase"]), int(item["initiate_checkout"])),
            reverse=True,
        )

    logger.info(f"   Resultados após normalização: {len(normalized)} registros")

    return normalized


