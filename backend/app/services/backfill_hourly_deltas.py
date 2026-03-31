import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..models.metrics import DailySummary, HourlyMetric
from .redis_service import invalidate_metrics_cache

SAO_PAULO_TZINFO = ZoneInfo("America/Sao_Paulo")


def _q2(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q4(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _iter_campaigns(db: Session, campaign_id: str | None) -> Iterable[str]:
    query = db.query(HourlyMetric.campaign_id).distinct().order_by(HourlyMetric.campaign_id)
    if campaign_id:
        query = query.filter(HourlyMetric.campaign_id == campaign_id)
    for row in query.all():
        yield str(row[0])


def _rebuild_daily_summary(db: Session, affected_keys: set[tuple[date, str]]) -> None:
    if not affected_keys:
        return

    grouped_dates: dict[str, set[date]] = defaultdict(set)
    for metric_date, squad in affected_keys:
        grouped_dates[squad].add(metric_date)

    for squad, dates in grouped_dates.items():
        for metric_date in dates:
            day_start = datetime.combine(metric_date, datetime.min.time(), tzinfo=SAO_PAULO_TZINFO)
            day_end = day_start + timedelta(days=1)
            agg = db.query(
                HourlyMetric.cost,
                HourlyMetric.profit,
                HourlyMetric.revenue,
                HourlyMetric.checkout_conversion,
            ).filter(
                HourlyMetric.squad == squad,
                HourlyMetric.metric_at >= day_start,
                HourlyMetric.metric_at < day_end,
            ).all()

            total_cost = _q2(sum((Decimal(str(row.cost or 0)) for row in agg), Decimal("0")))
            total_profit = _q2(sum((Decimal(str(row.profit or 0)) for row in agg), Decimal("0")))
            total_revenue = _q2(sum((Decimal(str(row.revenue or 0)) for row in agg), Decimal("0")))
            total_checkout = _q2(sum((Decimal(str(row.checkout_conversion or 0)) for row in agg), Decimal("0")))
            roi = _q4((total_profit / total_cost) if total_cost > 0 else 0)

            summary_row = db.query(DailySummary).filter(
                DailySummary.metric_date == metric_date,
                DailySummary.squad == squad,
            ).one_or_none()

            if summary_row:
                summary_row.cost = total_cost
                summary_row.profit = total_profit
                summary_row.revenue = total_revenue
                summary_row.checkout_conversion = total_checkout
                summary_row.roi = roi
            else:
                db.add(
                    DailySummary(
                        metric_date=metric_date,
                        squad=squad,
                        cost=total_cost,
                        profit=total_profit,
                        revenue=total_revenue,
                        checkout_conversion=total_checkout,
                        roi=roi,
                    )
                )


def _apply_backfill(
    db: Session,
    *,
    campaign_id: str | None,
    from_date: date | None,
    to_date: date | None,
    apply_changes: bool,
) -> dict[str, int]:
    stats = {
        "campaigns": 0,
        "rows_scanned": 0,
        "rows_updated": 0,
        "rows_skipped_missing_prev": 0,
        "rows_midnight": 0,
    }

    affected_keys: set[tuple[date, str]] = set()

    for cid in _iter_campaigns(db, campaign_id):
        stats["campaigns"] += 1

        query = db.query(HourlyMetric).filter(HourlyMetric.campaign_id == cid).order_by(HourlyMetric.metric_at)
        rows = query.all()

        previous_by_dt: dict[datetime, Any] = {row.metric_at: row for row in rows}

        for row in rows:
            stats["rows_scanned"] += 1
            row_date = row.metric_at.date()
            if from_date and row_date < from_date:
                continue
            if to_date and row_date > to_date:
                continue

            if row.metric_at.astimezone(SAO_PAULO_TZINFO).hour == 0:
                stats["rows_midnight"] += 1
                affected_keys.add((row.metric_at.date(), str(row.squad or "unknown")))
                continue

            prev = previous_by_dt.get(row.metric_at - timedelta(hours=1))
            if prev is None:
                stats["rows_skipped_missing_prev"] += 1
                continue

            curr_cost = Decimal(str(row.cost or 0))
            curr_profit = Decimal(str(row.profit or 0))
            curr_revenue = Decimal(str(row.revenue or 0))
            curr_checkout = Decimal(str(row.checkout_conversion or 0))

            prev_cost = Decimal(str(prev.cost or 0))
            prev_profit = Decimal(str(prev.profit or 0))
            prev_revenue = Decimal(str(prev.revenue or 0))
            prev_checkout = Decimal(str(prev.checkout_conversion or 0))

            new_cost = _q2(max(curr_cost - prev_cost, Decimal("0")))
            new_profit = _q2(max(curr_profit - prev_profit, Decimal("0")))
            new_revenue = _q2(max(curr_revenue - prev_revenue, Decimal("0")))
            new_checkout = _q2(max(curr_checkout - prev_checkout, Decimal("0")))
            new_roi = _q4((new_profit / new_cost) if new_cost > 0 else 0)

            changed = (
                row.cost != new_cost
                or row.profit != new_profit
                or row.revenue != new_revenue
                or row.checkout_conversion != new_checkout
                or row.roi != new_roi
            )

            if changed:
                stats["rows_updated"] += 1
                if apply_changes:
                    row.cost = new_cost
                    row.profit = new_profit
                    row.revenue = new_revenue
                    row.checkout_conversion = new_checkout
                    row.roi = new_roi
                affected_keys.add((row.metric_at.date(), str(row.squad or "unknown")))

    if apply_changes:
        _rebuild_daily_summary(db, affected_keys)

    return stats


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill hourly delta metrics by campaign")
    parser.add_argument("--apply", action="store_true", help="Persist changes. Without this flag runs in dry-run mode")
    parser.add_argument("--campaign-id", default=None, help="Optional campaign_id scope")
    parser.add_argument("--from-date", default=None, help="Optional start date (YYYY-MM-DD)")
    parser.add_argument("--to-date", default=None, help="Optional end date (YYYY-MM-DD)")
    args = parser.parse_args()

    from_date = _parse_date(args.from_date)
    to_date = _parse_date(args.to_date)

    db = SessionLocal()
    try:
        stats = _apply_backfill(
            db,
            campaign_id=args.campaign_id,
            from_date=from_date,
            to_date=to_date,
            apply_changes=args.apply,
        )

        if args.apply:
            db.commit()
            try:
                invalidate_metrics_cache()
            except Exception:
                pass
            print("[apply] backfill concluido")
        else:
            db.rollback()
            print("[dry-run] backfill simulado (nenhuma alteracao persistida)")

        print(stats)
    finally:
        db.close()


if __name__ == "__main__":
    main()





