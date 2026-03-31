import logging

import httpx

from .http_client import make_request_with_retry
from .settings import REDTRACK_API_KEY, REDTRACK_REPORT_URL

logger = logging.getLogger(__name__)


def _get_campaign_id(row: dict) -> str:
    return str(
        row.get("campaign_id")
        or row.get("campaignId")
        or row.get("campaign")
        or ""
    ).strip()


def _get_event_amount(row: dict) -> int:
    """Extract event volume from Redtrack row. Falls back to 1 per row when no volume field exists."""
    for key in (
        "count",
        "events",
        "conversions",
        "total",
        "value",
    ):
        raw = row.get(key)
        if raw is None:
            continue
        try:
            return max(int(float(raw)), 0)
        except (TypeError, ValueError):
            continue
    return 1


async def _fetch_event_rows(
    client: httpx.AsyncClient,
    *,
    event_type: str,
    date_from: str,
    date_to: str,
) -> list[dict]:
    params = {
        "api_key": REDTRACK_API_KEY,
        "date_from": date_from,
        "date_to": date_to,
        "type": event_type,
        "group": "campaign,date",
        "timezone": "America/Sao_Paulo",
        "per": 1000,
        "page": 1,
    }

    rows_acc: list[dict] = []
    page = 1
    while True:
        rows = await make_request_with_retry(client, REDTRACK_REPORT_URL, params, delay_after=0.3)
        if not isinstance(rows, list):
            raise RuntimeError("Resposta inesperada da API Redtrack: esperado lista de registros.")

        logger.debug("      Página %s: %s %s recebidos", page, len(rows), event_type)
        rows_acc.extend(rows)

        if len(rows) < params["per"]:
            break

        params["page"] += 1
        page += 1

    return rows_acc


async def fetch_all_events(
    client: httpx.AsyncClient,
    *,
    date_from: str,
    date_to: str,
) -> dict:
    logger.info(
        "📡 Buscando todos os eventos (InitiateCheckout + Purchase) do período %s a %s...",
        date_from,
        date_to,
    )

    events_by_campaign: dict[str, dict[str, int]] = {}

    logger.info("   🔵 Buscando eventos InitiateCheckout...")
    initiate_rows = await _fetch_event_rows(
        client,
        event_type="InitiateCheckout",
        date_from=date_from,
        date_to=date_to,
    )
    for row in initiate_rows:
        campaign_id = _get_campaign_id(row)
        if not campaign_id:
            continue
        amount = _get_event_amount(row)
        events_by_campaign.setdefault(campaign_id, {"InitiateCheckout": 0, "Purchase": 0})
        events_by_campaign[campaign_id]["InitiateCheckout"] += amount

    logger.info(
        "   ✅ Total de InitiateCheckout: %s",
        sum(v["InitiateCheckout"] for v in events_by_campaign.values()),
    )

    logger.info("   🔴 Buscando eventos Purchase...")
    purchase_rows = await _fetch_event_rows(
        client,
        event_type="Purchase",
        date_from=date_from,
        date_to=date_to,
    )
    for row in purchase_rows:
        campaign_id = _get_campaign_id(row)
        if not campaign_id:
            continue
        amount = _get_event_amount(row)
        events_by_campaign.setdefault(campaign_id, {"InitiateCheckout": 0, "Purchase": 0})
        events_by_campaign[campaign_id]["Purchase"] += amount

    logger.info(
        "   ✅ Total de Purchase: %s",
        sum(v["Purchase"] for v in events_by_campaign.values()),
    )

    logger.info("✅ Eventos agrupados por campaign: %s campanhas identificadas", len(events_by_campaign))
    return events_by_campaign


def calculate_conversions(events_by_campaign: dict) -> dict:
    logger.info("📊 Calculando taxas de conversão por campaign...")
    conversions: dict[str, float] = {}

    for campaign_id, events in events_by_campaign.items():
        initiate = events.get("InitiateCheckout", 0)
        purchase = events.get("Purchase", 0)

        if initiate == 0:
            conversion = 0.0
            logger.debug("   ⚠️  %s: sem InitiateCheckout, conversion=0.0", campaign_id)
        else:
            conversion = (purchase / initiate) * 100
            logger.debug("   ✅ %s: (%s/%s) * 100 = %.2f%%", campaign_id, purchase, initiate, conversion)

        conversions[campaign_id] = conversion

    return conversions

