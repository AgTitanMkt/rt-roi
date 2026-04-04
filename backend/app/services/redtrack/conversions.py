import logging
from datetime import datetime
from typing import Callable

import httpx

from .http_client import make_request_with_retry
from .extractors import (
    get_campaign_id,
    get_campaign_name,
    get_offer_id,
    get_offer_name,
    get_conversion_type,
    get_event_count,
    build_mapping_source_text,
)
from .mappings import resolve_squad, resolve_checkout, resolve_product
from .aggregators import aggregate_by_dimension
from .models import CampaignInfo, AggregatedConversions
from .settings import (
    REDTRACK_API_KEY,
    REDTRACK_CONVERSIONS_URL,
    REDTRACK_REPORT_URL,
    REDTRACK_OFFER_URL,
    REDTRACK_CONVERSIONS_PER_PAGE,
    REDTRACK_CONVERSIONS_MAX_PAGES,
    SAO_PAULO_TZ,
)

logger = logging.getLogger(__name__)

# Tipos de conversão suportados pelo dashboard.
VALID_CONVERSION_TYPES = {"purchase", "initiatecheckout"}


def _pick_raw_or_resolved(raw_value: str | None, resolved_value: str | None) -> str:
    raw = str(raw_value or "").strip()
    resolved = str(resolved_value or "").strip()

    if resolved and resolved.lower() != "unknown":
        return resolved

    return raw or "unknown"


def _is_cartpanda_checkout(checkout: str | None) -> bool:
    return str(checkout or "").strip().lower() == "cartpanda"


def _best_kit_product(*kits: str) -> str:
    for kit in kits:
        clean = str(kit or "").strip()
        if clean and clean.lower() != "unknown":
            return clean
    return "unknown"


def extract_campaign_info(campaign_name: str, campaign_id: str = "", offer_id: str | None = None) -> CampaignInfo:
    """
    Extrai e normaliza dados úteis da nomenclatura da campanha.

    O texto completo é usado para resolver aliases e, quando não houver match,
    o valor bruto da campanha é preservado.
    """
    parts = [part.strip() for part in str(campaign_name or "").split("|") if part.strip()]

    info = CampaignInfo(
        campaign_id=campaign_id or campaign_name,
        offer_id=(str(offer_id).strip() if offer_id else None),
        campaign_name=campaign_name,
    )

    if len(parts) > 0:
        info.platform = parts[0].upper()

    raw_squad = parts[1] if len(parts) > 1 else ""
    raw_checkout = parts[2] if len(parts) > 2 else ""
    raw_product = parts[4] if len(parts) > 4 else ""

    info.squad = _pick_raw_or_resolved(raw_squad, resolve_squad(campaign_name))
    info.checkout = _pick_raw_or_resolved(raw_checkout, resolve_checkout(campaign_name))

    if len(parts) > 3:
        info.niche = parts[3].strip().upper()

    info.product = _pick_raw_or_resolved(raw_product, resolve_product(campaign_name))

    return info


def _extract_rows(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]

    if isinstance(payload, dict):
        for key in ("rows", "data", "result", "items", "records"):
            nested = payload.get(key)
            if isinstance(nested, list):
                return [row for row in nested if isinstance(row, dict)]

    return []


def _parse_row_datetime(row: dict) -> datetime | None:
    for key in (
        "datetime",
        "event_time",
        "conversion_time",
        "created_at",
        "time",
        "timestamp",
        "date_time",
    ):
        raw = row.get(key)
        if raw is None:
            continue

        if isinstance(raw, (int, float)):
            try:
                ts = float(raw)
                if ts > 1e12:
                    ts = ts / 1000.0
                return datetime.fromtimestamp(ts, tz=SAO_PAULO_TZ)
            except Exception:
                continue

        text = str(raw).strip()
        if not text:
            continue

        normalized = text.replace("Z", "+00:00")
        for candidate in (normalized, text):
            try:
                return datetime.fromisoformat(candidate)
            except ValueError:
                continue

        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S%z",
        ):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue

    return None


def _filter_rows_by_hour_window(
    rows: list[dict],
    *,
    hour_start: datetime | None,
    hour_end: datetime | None,
) -> list[dict]:
    if hour_start is None or hour_end is None:
        return rows

    filtered: list[dict] = []
    parsed_count = 0
    unknown_count = 0
    outside_count = 0

    for row in rows:
        row_dt = _parse_row_datetime(row)
        if row_dt is None:
            unknown_count += 1
            continue

        parsed_count += 1
        if row_dt.tzinfo is None:
            row_dt = row_dt.replace(tzinfo=SAO_PAULO_TZ)
        else:
            row_dt = row_dt.astimezone(SAO_PAULO_TZ)

        if hour_start <= row_dt < hour_end:
            filtered.append(row)
        else:
            outside_count += 1

    if parsed_count == 0:
        logger.warning(
            "⚠️ Não foi possível identificar timestamp nas linhas de conversão. "
            "Mantendo janela diária para evitar perda de dados.",
        )
        return rows

    logger.info(
        "🕐 Conversões filtradas por hora: inicio=%s fim=%s | total=%s parseadas=%s fora_janela=%s desconhecidas=%s selecionadas=%s",
        hour_start.isoformat(),
        hour_end.isoformat(),
        len(rows),
        parsed_count,
        outside_count,
        unknown_count,
        len(filtered),
    )
    return filtered


async def _fetch_paginated_rows(
    client: httpx.AsyncClient,
    *,
    url: str,
    base_params: dict[str, object],
    per_page: int,
    max_pages: int | None = None,
    delay_after: float = 0.3,
) -> list[dict]:
    """Busca páginas consecutivas até acabar o payload ou atingir o limite."""
    params = dict(base_params)
    params.update({"per": per_page, "page": 1})
    endpoint = str(url).rstrip("/").split("/")[-1] or "unknown"

    rows_acc: list[dict] = []
    page = 1

    while max_pages is None or page <= max_pages:
        logger.info("📄 [%s] Buscando página %s", endpoint, page)
        try:
            payload = await make_request_with_retry(client, url, params, delay_after=delay_after)
        except Exception as exc:
            logger.error("❌ [%s] Falha na página %s: %s", endpoint, page, exc)
            raise

        rows = _extract_rows(payload)
        if not rows:
            logger.info("✅ [%s] Fim da paginação na página %s (sem linhas)", endpoint, page)
            break

        rows_acc.extend(rows)
        logger.info("✅ [%s] Página %s concluída (%s linhas)", endpoint, page, len(rows))
        if len(rows) < per_page:
            logger.info("✅ [%s] Última página identificada: %s", endpoint, page)
            break

        page += 1
        params["page"] = page

    return rows_acc


async def fetch_conversion_rows(
    client: httpx.AsyncClient,
    *,
    date_from: str,
    date_to: str,
) -> list[dict]:
    """Busca linhas brutas de /conversions para possível reuso entre etapas."""
    return await _fetch_paginated_rows(
        client,
        url=REDTRACK_CONVERSIONS_URL,
        base_params={
            "api_key": REDTRACK_API_KEY,
            "date_from": date_from,
            "date_to": date_to,
            "timezone": "America/Sao_Paulo",
        },
        per_page=REDTRACK_CONVERSIONS_PER_PAGE,
        max_pages=REDTRACK_CONVERSIONS_MAX_PAGES,
        delay_after=0.3,
    )


async def _fetch_offer_payload(
    client: httpx.AsyncClient,
    *,
    offer_id: str,
) -> object:
    for params in (
        {"api_key": REDTRACK_API_KEY, "id": offer_id},
        {"api_key": REDTRACK_API_KEY, "offer_id": offer_id},
        {"api_key": REDTRACK_API_KEY, "offerId": offer_id},
    ):
        try:
            return await make_request_with_retry(client, REDTRACK_OFFER_URL, params, delay_after=0.0)
        except Exception:
            logger.debug("Falha ao buscar offer com params %s", sorted(params.keys()))

    return {}


async def _fetch_report_event_rows(
    client: httpx.AsyncClient,
    *,
    event_type: str,
    date_from: str,
    date_to: str,
) -> list[dict]:
    return await _fetch_paginated_rows(
        client,
        url=REDTRACK_REPORT_URL,
        base_params={
            "api_key": REDTRACK_API_KEY,
            "group": "campaign",
            "date_from": date_from,
            "date_to": date_to,
            "type": event_type,
            "timezone": "America/Sao_Paulo",
        },
        per_page=500,
        delay_after=0.3,
    )


def _build_campaign_info_cache_entry(
    row: dict,
    campaign_id: str,
    campaign_info_cache: dict[str, CampaignInfo],
) -> CampaignInfo:
    info = campaign_info_cache.get(campaign_id)
    if info is not None:
        return info

    campaign_name = get_campaign_name(row)
    offer_name = get_offer_name(row)
    mapping_source = build_mapping_source_text(campaign_name, offer_name)
    offer_id = get_offer_id(row)

    info = extract_campaign_info(mapping_source or campaign_name, campaign_id, offer_id)
    campaign_info_cache[campaign_id] = info
    return info


def _aggregate_conversion_rows(
    result: AggregatedConversions,
    campaign_info_cache: dict[str, CampaignInfo],
    rows: list[dict],
    *,
    count_getter: Callable[[dict], int],
) -> int:
    processed = 0

    for row in rows:
        conv_type = get_conversion_type(row)
        if conv_type not in VALID_CONVERSION_TYPES:
            continue

        campaign_id = get_campaign_id(row)
        if not campaign_id:
            continue

        info = _build_campaign_info_cache_entry(row, campaign_id, campaign_info_cache)
        count = count_getter(row)
        is_purchase = conv_type == "purchase"

        result.campaign_info[campaign_id] = info
        aggregate_by_dimension(result, result.by_campaign, campaign_id, is_purchase, count)
        aggregate_by_dimension(result, result.by_squad, info.squad, is_purchase, count)
        aggregate_by_dimension(result, result.by_checkout, info.checkout, is_purchase, count)
        aggregate_by_dimension(result, result.by_product, info.product, is_purchase, count)
        processed += 1

    return processed


def _aggregate_report_rows(
    result: AggregatedConversions,
    campaign_info_cache: dict[str, CampaignInfo],
    rows: list[dict],
    *,
    is_purchase: bool,
) -> int:
    processed = 0

    for row in rows:
        campaign_id = get_campaign_id(row)
        if not campaign_id:
            continue

        info = _build_campaign_info_cache_entry(row, campaign_id, campaign_info_cache)
        count = get_event_count(row)

        result.campaign_info[campaign_id] = info
        aggregate_by_dimension(result, result.by_campaign, campaign_id, is_purchase, count)
        aggregate_by_dimension(result, result.by_squad, info.squad, is_purchase, count)
        aggregate_by_dimension(result, result.by_checkout, info.checkout, is_purchase, count)
        aggregate_by_dimension(result, result.by_product, info.product, is_purchase, count)
        processed += 1

    return processed


async def _fallback_fetch_all_conversions_via_report(
    client: httpx.AsyncClient,
    *,
    date_from: str,
    date_to: str,
) -> AggregatedConversions:
    logger.info("↩️  Fallback: buscando conversões via /report por tipo de evento")

    result = AggregatedConversions()
    campaign_info_cache: dict[str, CampaignInfo] = {}
    for event_type, is_purchase in (("InitiateCheckout", False), ("Purchase", True)):
        rows = await _fetch_report_event_rows(client, event_type=event_type, date_from=date_from, date_to=date_to)
        _aggregate_report_rows(result, campaign_info_cache, rows, is_purchase=is_purchase)

    return result


async def fetch_all_conversions(
    client: httpx.AsyncClient,
    *,
    date_from: str,
    date_to: str,
    hour_start: datetime | None = None,
    hour_end: datetime | None = None,
    prefetched_rows: list[dict] | None = None,
) -> AggregatedConversions:
    """Busca conversões do período e agrega por campanha, squad, checkout e produto.

    Quando `hour_start/hour_end` são informados, aplica filtro de janela horária
    em memória para suportar ingestão incremental por hora.
    """
    logger.info(
        "📡 Buscando conversões (InitiateCheckout + Purchase) de %s a %s...",
        date_from,
        date_to,
    )

    result = AggregatedConversions()
    campaign_info_cache: dict[str, CampaignInfo] = {}
    rows = prefetched_rows if prefetched_rows is not None else await fetch_conversion_rows(
        client,
        date_from=date_from,
        date_to=date_to,
    )

    rows = _filter_rows_by_hour_window(
        rows,
        hour_start=hour_start,
        hour_end=hour_end,
    )

    if rows:
        logger.debug("Campos recebidos em conversões (amostra): %s", sorted(rows[0].keys()))

    total_rows = len(rows)
    filtered_rows = _aggregate_conversion_rows(
        result,
        campaign_info_cache,
        rows,
        count_getter=get_event_count,
    )

    logger.info(
        "✅ Conversões processadas: %s total, %s filtradas (Purchase/InitiateCheckout)",
        total_rows,
        filtered_rows,
    )

    if filtered_rows == 0 and total_rows > 0:
        logger.warning(
            "⚠️  Nenhuma linha mapeada para Purchase/InitiateCheckout via /conversions."
            " Tentando fallback via /report."
        )
        result = await _fallback_fetch_all_conversions_via_report(
            client,
            date_from=date_from,
            date_to=date_to,
        )
    logger.info(
        "📊 Totais: InitiateCheckout=%s, Purchase=%s, Taxa=%.2f%%",
        result.total.initiate_checkout,
        result.total.purchase,
        result.total.conversion_rate,
    )
    logger.info(
        "📊 Dimensões processadas: campanhas=%s | squads=%s | checkouts=%s | produtos=%s",
        len(result.by_campaign),
        len(result.by_squad),
        len(result.by_checkout),
        len(result.by_product),
    )

    return result


def get_conversion_rates_by_campaign(conversions: AggregatedConversions) -> dict[str, float]:
    """Retorna taxas de conversão por campanha (formato legado para compatibilidade)."""
    return {
        campaign_id: metrics.conversion_rate
        for campaign_id, metrics in conversions.by_campaign.items()
    }


def get_conversion_rates_by_squad(conversions: AggregatedConversions) -> dict[str, float]:
    """Retorna taxas de conversão por squad."""
    return {
        squad: metrics.conversion_rate
        for squad, metrics in conversions.by_squad.items()
    }


def get_conversion_rates_by_checkout(conversions: AggregatedConversions) -> dict[str, float]:
    """Retorna taxas de conversão por checkout (Cartpanda, Clickbank)."""
    return {
        checkout: metrics.conversion_rate
        for checkout, metrics in conversions.by_checkout.items()
    }


def get_conversion_rates_by_product(conversions: AggregatedConversions) -> dict[str, float]:
    """Retorna taxas de conversão por produto."""
    return {
        product: metrics.conversion_rate
        for product, metrics in conversions.by_product.items()
    }


# Funções legadas para compatibilidade
async def fetch_all_events(
    client: httpx.AsyncClient,
    *,
    date_from: str,
    date_to: str,
) -> dict:
    """
    Função legada para compatibilidade.
    Retorna eventos no formato antigo (dict[campaign_id, {InitiateCheckout, Purchase}]).
    """
    conversions = await fetch_all_conversions(client, date_from=date_from, date_to=date_to)

    return {
        campaign_id: {
            "InitiateCheckout": metrics.initiate_checkout,
            "Purchase": metrics.purchase,
        }
        for campaign_id, metrics in conversions.by_campaign.items()
    }


def calculate_conversions(events_by_campaign: dict) -> dict:
    """Função legada para compatibilidade."""
    logger.info("📊 Calculando taxas de conversão por campaign...")
    conversions: dict[str, float] = {}

    for campaign_id, events in events_by_campaign.items():
        checkout = events.get("InitiateCheckout", 0)
        purchase = events.get("Purchase", 0)

        if checkout == 0:
            conversion = 0.0
        else:
            conversion = (purchase / checkout) * 100

        conversions[campaign_id] = conversion

    return conversions
