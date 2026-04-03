import logging

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
    REDTRACK_CONVERSIONS_PER_PAGE,
    REDTRACK_CONVERSIONS_MAX_PAGES,
)

logger = logging.getLogger(__name__)

# Tipos de conversão que queremos filtrar
VALID_CONVERSION_TYPES = {"purchase", "initiatecheckout"}



def extract_campaign_info(campaign_name: str, campaign_id: str = "", offer_id: str | None = None) -> CampaignInfo:
    """
    Extrai informações da nomenclatura da campanha.
    
    Formato esperado:
    FB | FBR-Renato | Cartpanda | ED | ErosLift | Conta 6 BM: MS | elevateandwell.com | 24/12
     0       1           2        3      4              5                  6              7
    
    - Índice 0: Plataforma (FB)
    - Índice 1: Squad-Responsável (FBR-Renato)
    - Índice 2: Checkout (Cartpanda, Clickbank)
    - Índice 3: Nicho (ED)
    - Índice 4: Produto (ErosLift)
    """
    parts = [part.strip() for part in str(campaign_name or "").split("|") if part.strip()]
    
    info = CampaignInfo(
        campaign_id=campaign_id or campaign_name,
        offer_id=(str(offer_id).strip() if offer_id else None),
        campaign_name=campaign_name,
    )
    
    if len(parts) > 0:
        info.platform = parts[0].upper()
    
    # Squad/checkout são resolvidos no texto completo para não depender da ordem dos campos.
    # Se não houver match no mapping, preservamos o valor bruto da nomenclatura.
    squad_resolved = resolve_squad(campaign_name)
    checkout_resolved = resolve_checkout(campaign_name)

    raw_squad = parts[1].strip() if len(parts) > 1 else ""
    raw_checkout = parts[2].strip() if len(parts) > 2 else ""

    info.squad = squad_resolved if squad_resolved != "unknown" else (raw_squad or "unknown")
    info.checkout = checkout_resolved if checkout_resolved != "unknown" else (raw_checkout or "unknown")

    if len(parts) > 3:
        info.niche = parts[3].strip().upper()
    
    # Produto também é resolvido no texto completo para padronizar aliases.
    # Sem match, usamos o valor bruto da parte esperada da campanha.
    product_resolved = resolve_product(campaign_name)
    raw_product = parts[4].strip() if len(parts) > 4 else ""
    info.product = product_resolved if product_resolved != "unknown" else (raw_product or "unknown")

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


async def _fetch_conversions_page(
    client: httpx.AsyncClient,
    *,
    date_from: str,
    date_to: str,
    page: int = 1,
    per_page: int = REDTRACK_CONVERSIONS_PER_PAGE,
) -> list[dict]:
    """Busca uma página de conversões da API."""
    params = {
        "api_key": REDTRACK_API_KEY,
        "date_from": date_from,
        "date_to": date_to,
        "timezone": "America/Sao_Paulo",
        "per": per_page,
        "page": page,
    }

    rows = await make_request_with_retry(
        client, 
        REDTRACK_CONVERSIONS_URL, 
        params, 
        delay_after=0.3
    )
    
    parsed = _extract_rows(rows)
    if parsed:
        return parsed

    if isinstance(rows, dict):
        logger.warning(
            "Resposta de conversões sem lista de linhas. Chaves recebidas: %s",
            sorted(rows.keys()),
        )
    else:
        logger.warning("Resposta inesperada da API: esperado lista/dict, recebido %s", type(rows))
    return []


async def _fetch_report_event_rows(
    client: httpx.AsyncClient,
    *,
    event_type: str,
    date_from: str,
    date_to: str,
) -> list[dict]:
    params = {
        "api_key": REDTRACK_API_KEY,
        "group": "campaign",
        "date_from": date_from,
        "date_to": date_to,
        "type": event_type,
        "timezone": "America/Sao_Paulo",
        "per": 500,
        "page": 1,
    }

    rows_acc: list[dict] = []
    while True:
        payload = await make_request_with_retry(client, REDTRACK_REPORT_URL, params, delay_after=0.3)
        rows = _extract_rows(payload)
        if not rows:
            break

        rows_acc.extend(rows)
        if len(rows) < params["per"]:
            break
        params["page"] += 1

    return rows_acc


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
        rows = await _fetch_report_event_rows(
            client,
            event_type=event_type,
            date_from=date_from,
            date_to=date_to,
        )

        for row in rows:
            campaign_id = get_campaign_id(row)
            if not campaign_id:
                continue

            campaign_name = get_campaign_name(row)
            offer_name = get_offer_name(row)
            mapping_source = build_mapping_source_text(campaign_name, offer_name)
            offer_id = get_offer_id(row)
            count = get_event_count(row)

            if campaign_id not in campaign_info_cache:
                campaign_info_cache[campaign_id] = extract_campaign_info(
                    mapping_source or campaign_name, campaign_id, offer_id,
                )

            info = campaign_info_cache[campaign_id]
            result.campaign_info[campaign_id] = info

            aggregate_by_dimension(result, result.by_campaign, campaign_id, is_purchase, count)
            aggregate_by_dimension(result, result.by_squad, info.squad, is_purchase, count)
            aggregate_by_dimension(result, result.by_checkout, info.checkout, is_purchase, count)
            aggregate_by_dimension(result, result.by_product, info.product, is_purchase, count)

    return result


async def fetch_all_conversions(
    client: httpx.AsyncClient,
    *,
    date_from: str,
    date_to: str,
) -> AggregatedConversions:
    """
    Busca todas as conversões do período e agrega por campanha, squad, checkout e produto.
    Filtra apenas eventos Purchase e InitiateCheckout.
    """
    logger.info(
        "📡 Buscando conversões (InitiateCheckout + Purchase) de %s a %s...",
        date_from,
        date_to,
    )
    
    result = AggregatedConversions()
    campaign_info_cache: dict[str, CampaignInfo] = {}
    total_rows = 0
    filtered_rows = 0

    page = 1
    while page <= REDTRACK_CONVERSIONS_MAX_PAGES:
        rows = await _fetch_conversions_page(
            client,
            date_from=date_from,
            date_to=date_to,
            page=page,
        )

        if not rows:
            break

        if page == 1:
            logger.info("🔎 Campos recebidos em conversões (amostra): %s", sorted(rows[0].keys()))

        total_rows += len(rows)

        for row in rows:
            conv_type = get_conversion_type(row)
            if conv_type is None:
                # Ignora qualquer tipo que nao seja Purchase/InitiateCheckout.
                continue

            filtered_rows += 1
            campaign_id = get_campaign_id(row)
            if not campaign_id:
                continue

            campaign_name = get_campaign_name(row)
            offer_name = get_offer_name(row)
            mapping_source = build_mapping_source_text(campaign_name, offer_name)
            offer_id = get_offer_id(row)
            # /conversions retorna eventos brutos; cada linha equivale a 1 evento.
            count = 1

            if campaign_id not in campaign_info_cache:
                campaign_info_cache[campaign_id] = extract_campaign_info(
                    mapping_source or campaign_name, campaign_id, offer_id,
                )

            info = campaign_info_cache[campaign_id]
            result.campaign_info[campaign_id] = info

            is_purchase = conv_type == "purchase"
            aggregate_by_dimension(result, result.by_campaign, campaign_id, is_purchase, count)
            aggregate_by_dimension(result, result.by_squad, info.squad, is_purchase, count)
            aggregate_by_dimension(result, result.by_checkout, info.checkout, is_purchase, count)
            aggregate_by_dimension(result, result.by_product, info.product, is_purchase, count)

        logger.debug("Página %s: %s linhas, %s filtradas", page, len(rows), filtered_rows)
        if len(rows) < REDTRACK_CONVERSIONS_PER_PAGE:
            break
        page += 1


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
