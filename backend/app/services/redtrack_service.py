from datetime import datetime, timedelta
import os
import asyncio
import sys

from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from dotenv import load_dotenv, find_dotenv

# Retry configuration
MAX_RETRIES = 5
INITIAL_BACKOFF = 1  # seconds
MAX_BACKOFF = 60  # seconds
RATE_LIMIT_DELAY = 0.5  # 500ms between requests

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
REDTRACK_REPORT_URL = "https://api.redtrack.io/report"
SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")


async def _make_request_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: dict,
    delay_after: float = RATE_LIMIT_DELAY,
) -> dict:
    """
    Make HTTP request with exponential backoff retry for 429 errors.
    
    Args:
        client: AsyncClient instance
        url: Request URL
        params: Query parameters
        delay_after: Delay in seconds after successful request
    
    Returns:
        Response JSON
    
    Raises:
        HTTPStatusError: If all retries exhausted or non-recoverable error
    """
    backoff = INITIAL_BACKOFF
    last_error = None
    
    for attempt in range(MAX_RETRIES):
        try:
            res = await client.get(url, params=params)
            
            # If we got rate limited, wait and retry
            if res.status_code == 429:
                wait_time = min(backoff, MAX_BACKOFF)
                print(f"⚠️  Rate limited (429). Attempt {attempt + 1}/{MAX_RETRIES}. Waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
                backoff *= 2  # Exponential backoff
                continue
            
            res.raise_for_status()
            
            # Add delay after successful request to avoid rate limiting
            if delay_after > 0:
                await asyncio.sleep(delay_after)
            
            return res.json()
        
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code == 429:
                # Rate limit: retry with backoff
                wait_time = min(backoff, MAX_BACKOFF)
                print(f"⚠️  Rate limited (429). Attempt {attempt + 1}/{MAX_RETRIES}. Waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
                backoff *= 2
            else:
                # Non-429 errors: fail immediately
                raise
        
        except Exception as e:
            last_error = e
            raise
    
    # All retries exhausted
    if last_error:
        raise RuntimeError(f"Failed after {MAX_RETRIES} retries: {last_error}")
    raise RuntimeError(f"Failed after {MAX_RETRIES} retries")



def persist_metrics_report(data: RedtrackResponse) -> None:
    payload = [
        {
            "id": item.campaign_id,
            "squad": item.squad,
            "metric_at": item.date,
            "cost": item.cost,
            "profit": item.profit,
            "revenue": item.revenue,
            "roi": item.roi,
            "checkout_conversion": item.conversion,
        }
        for item in data
    ]

    if not payload:
        return

    db = SessionLocal()
    try:
        result = insert_metrics(db, payload)
        print(
            "Persistencia finalizada: "
            f"inseridos={result['inserted']} "
            f"atualizados={result['updated']} "
            f"ignorados={result['ignored']}"
        )
    finally:
        db.close()


async def _count_campaign_events(
    client: httpx.AsyncClient,
    *,
    campaign_id: str,
    event_type: str,
    date_from: str,
    date_to: str,
) -> int:
    params = {
        "api_key": REDTRACK_API_KEY,
        "date_from": date_from,
        "date_to": date_to,
        "type": event_type,
        "country_code": "US",
        "per": 1000,
        "campaign_id": campaign_id,
        "page": 1,
    }

    total = 0
    while True:
        page_rows = await _make_request_with_retry(client, REDTRACK_REPORT_URL, params)

        if not isinstance(page_rows, list):
            raise RuntimeError("Resposta inesperada da API Redtrack: esperado lista de registros.")

        total += len(page_rows)

        if len(page_rows) < params["per"]:
            break

        params["page"] += 1

    return total


async def redtrack_conversion(
    campaign_id: str,
    client: httpx.AsyncClient,
    *,
    date_from: str,
    date_to: str,
) -> float:
    if not REDTRACK_API_KEY:
        raise RuntimeError("REDTRACK_API_KEY nao encontrada. Defina no .env antes de executar.")

    initiate_total = await _count_campaign_events(
        client,
        campaign_id=campaign_id,
        event_type="InitiateCheckout",
        date_from=date_from,
        date_to=date_to,
    )
    purchase_total = await _count_campaign_events(
        client,
        campaign_id=campaign_id,
        event_type="Purchase",
        date_from=date_from,
        date_to=date_to,
    )

    if purchase_total == 0:
        return 0.0

    return initiate_total / purchase_total


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
        conversion_cache: dict[str, float] = {}

        cost_total = 0.0
        profit_total = 0.0

        while True:
            page_rows = await _make_request_with_retry(
                client,
                REDTRACK_REPORT_URL,
                params,
            )

            if not isinstance(page_rows, list):
                raise RuntimeError("Resposta inesperada da API Redtrack: esperado lista de registros.")

            for x in page_rows:
                cost = float(x.get("cost", 0) or 0)
                profit = float(x.get("profit", 0) or 0)

                raw_date = x.get("date")
                if not raw_date:
                    continue

                campaign_name = str(x.get("campaign") or "").strip()
                campaign_id = str(
                    x.get("campaign_id")
                    or x.get("campaignId")
                    or campaign_name
                ).strip()
                if not campaign_id:
                    continue

                report_datetime = datetime.strptime(raw_date, "%Y-%m-%d").replace(
                    hour=last_closed_hour.hour,
                    minute=0,
                    second=0,
                    microsecond=0,
                    tzinfo=SAO_PAULO_TZ,
                )

                campaign_parts = [part.strip() for part in campaign_name.split("|") if part.strip()]

                if campaign_id not in conversion_cache:
                    conversion_cache[campaign_id] = await redtrack_conversion(
                        campaign_id,
                        client,
                        date_from=date_from,
                        date_to=date_to,
                    )
                conversion = conversion_cache[campaign_id]

                responsible = campaign_parts[1] if len(campaign_parts) > 1 else (campaign_parts[0] if campaign_parts else "unknown")
                squad = responsible.split("-")[0]

                res_data = RedtrackReportItem(
                    campaign_id=campaign_id,
                    squad=squad,
                    date=report_datetime,
                    cost=cost,
                    revenue=float(x.get("revenue", 0) or 0),
                    profit=profit,
                    roi=float(x.get("roi", 0) or 0),
                    conversion=conversion,
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

