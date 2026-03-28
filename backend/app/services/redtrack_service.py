from datetime import datetime, timedelta
import os
import asyncio
import sys

from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from dotenv import load_dotenv, find_dotenv

try:
    from ..core.database import SessionLocal
    from .metrics_service import insert_metrics
    from ..schemas.redtrack_schema import RedtrackReportItem, RedtrackResponse
except ImportError:
    current = Path(__file__).resolve()
    backend_root = str(current.parents[2])
    project_root = str(current.parents[3])
    for path in (backend_root, project_root):
        if path not in sys.path:
            sys.path.insert(0, path)

    from app.core.database import SessionLocal
    from app.services.metrics_service import insert_metrics
    from app.schemas.redtrack_schema import RedtrackReportItem, RedtrackResponse

load_dotenv(find_dotenv(usecwd=True))

REDTRACK_API_KEY = os.getenv("REDTRACK_API_KEY")
REDTRACK_URL = "https://api.redtrack.io/report"
SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")


def persist_metrics_report(data: RedtrackResponse) -> None:
    payload = [
        {
            "squad": item.squad,
            "metric_at": item.date,
            "cost": item.cost,
            "profit": item.profit,
            "revenue": item.revenue,
            "roi": item.roi,
        }
        for item in data
    ]

    if not payload:
        return

    db = SessionLocal()
    try:
        result = insert_metrics(db, payload)
        print(
            f"Persistencia finalizada: inseridos={result['inserted']} ignorados={result['ignored']}"
        )
    finally:
        db.close()

async def redtrack_reports() -> RedtrackResponse:
    now_sp = datetime.now(SAO_PAULO_TZ)
    last_closed_hour = now_sp.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    date_from = last_closed_hour.strftime("%Y-%m-%d")
    date_to = now_sp.strftime("%Y-%m-%d")

    params = {
        "api_key": REDTRACK_API_KEY,
        "group": "campaign,date",
        "date_from": date_from,
        "date_to": date_to,
        "time_interval": "lasthour",
        "timezone": "America/Sao_Paulo",
        "per": 1000,
        "page": 1,
    }

    if not REDTRACK_API_KEY:
        raise RuntimeError("REDTRACK_API_KEY nao encontrada. Defina no .env antes de executar.")

    params = dict(params)
    params["page"] = 1

    async with httpx.AsyncClient(timeout=30.0) as client:
        data: RedtrackResponse = []

        cost_total = 0.0
        profit_total = 0.0

        while True:
            res = await client.get(
                REDTRACK_URL,
                params=params,
            )
            res.raise_for_status()
            page_rows = res.json()

            if not isinstance(page_rows, list):
                raise RuntimeError("Resposta inesperada da API Redtrack: esperado lista de registros.")

            for x in page_rows:
                cost = float(x.get("cost", 0) or 0)
                profit = float(x.get("profit", 0) or 0)

                raw_date = x.get("date")
                if not raw_date:
                    continue

                report_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
                if report_date == last_closed_hour.date():
                    metric_hour = last_closed_hour.hour
                elif report_date == now_sp.date():
                    metric_hour = now_sp.hour
                else:
                    metric_hour = 0

                report_datetime = datetime.strptime(raw_date, "%Y-%m-%d").replace(
                    hour=metric_hour,
                    minute=0,
                    second=0,
                    microsecond=0,
                    tzinfo=SAO_PAULO_TZ,
                )

                if cost > 0 and profit != 0:
                    campaign = str(x.get("campaign") or "").strip()
                    campaign_parts = [part.strip() for part in campaign.split("|") if part.strip()]

                    responsible = campaign_parts[1] if len(campaign_parts) > 1 else (campaign_parts[0] if campaign_parts else "unknown")
                    squad = responsible.split("-")[0]

                    res_data = RedtrackReportItem(
                        squad=squad,
                        date=report_datetime,
                        cost=cost,
                        revenue=float(x.get("revenue", 0) or 0),
                        profit=profit,
                        roi=float(x.get("roi", 0) or 0),
                    )

                    data.append(res_data)
                    profit_total += profit
                    cost_total += cost

            if len(page_rows) < params["per"]:
                break

            params["page"] += 1

        roi_total = (profit_total / cost_total) if cost_total > 0 else 0.0

        print(f"Profit: {profit_total:.2f} \nRoi: {roi_total:.2f} \nCost: {cost_total:.2f}")

        persist_metrics_report(data)
        return data


if __name__ == "__main__":
    try:
        data = asyncio.run(redtrack_reports())
        print(f"OK: {len(data)} registros obtidos do Redtrack")
    except Exception as exc:
        print(f"ERRO: {exc}")
        raise

