from datetime import datetime
import os
import asyncio
import sys

from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import json

from dotenv import load_dotenv, find_dotenv

try:
    from ..core.database import SessionLocal
    from .metrics_service import insert_metrics
    from ..schemas.redtrack_schema import RedtrackReportItem, RedtrackResponse
except ImportError:
    # Allow direct execution: python backend/app/services/redtrack_service.py
    current = Path(__file__).resolve()
    backend_root = str(current.parents[2])
    project_root = str(current.parents[3])
    for path in (backend_root, project_root):
        if path not in sys.path:
            sys.path.insert(0, path)

    from app.core.database import SessionLocal
    from app.services.metrics_service import insert_metrics
    from app.schemas.redtrack_schema import RedtrackReportItem, RedtrackResponse

# Resolve .env starting from current working directory.
# Keeps compatibility when running from project root, backend folder or IDE run configs.
load_dotenv(find_dotenv(usecwd=True))

REDTRACK_KEY = os.getenv("REDTRACK_KEY")
REDTRACK_URL = "https://api.redtrack.io/report"
SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")


def persist_metrics_report(data: RedtrackResponse) -> None:
    payload = [
        {
            "metric_at": item.date.replace(tzinfo=None),
            "source_alias": item.source_alias,
            "cost": item.cost,
            "profit": item.profit,
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
    today = now_sp.strftime("%Y-%m-%d")
    hour = now_sp.hour

    params = {
        "api_key": REDTRACK_KEY,
        "group": "source,date",
        "date_from": today,
        "date_to": today,
        "time_interval": "lasthour",
        "timezone": "America/Sao_Paulo",
        "per": 1000,
        "page": 1,
    }

    if not REDTRACK_KEY:
        raise RuntimeError("REDTRACK_KEY nao encontrada. Defina no .env antes de executar.")

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

            for x in page_rows:
                cost = float(x.get("cost", 0) or 0)
                profit = float(x.get("profit", 0) or 0)

                raw_date = x.get("date")
                if not raw_date:
                    continue

                report_datetime = datetime.strptime(raw_date, "%Y-%m-%d").replace(
                    hour=hour,
                    minute=0,
                    second=0,
                    microsecond=0,
                    tzinfo=SAO_PAULO_TZ,
                )

                if cost > 0 and profit != 0:
                    res_data = RedtrackReportItem(
                        source_alias=x.get("source_alias", "unknown"),
                        date=report_datetime,
                        cost=cost,
                        profit=profit,
                        roi=float(x.get("roi", 0) or 0)
                    )

                    data.append(res_data)
                    profit_total += profit
                    cost_total += cost


            print(params["page"])
            params["page"] += 1
            print(len(data))

            if len(page_rows) < params["per"]:
                break


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

