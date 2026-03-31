import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx

from .http_client import make_request_with_retry
from .settings import REDTRACK_API_KEY, REDTRACK_CONVERSIONS_URL, REDTRACK_REPORT_URL

logger = logging.getLogger(__name__)

# Tipos de conversão que queremos filtrar
VALID_CONVERSION_TYPES = {"purchase", "initiatecheckout"}


@dataclass
class CampaignInfo:
    """Informações extraídas da nomenclatura da campanha."""
    campaign_id: str
    campaign_name: str
    squad: str = "unknown"
    checkout: str = "unknown"  # Cartpanda, Clickbank, etc.
    product: str = "unknown"   # ErosLift, etc.
    niche: str = "unknown"     # ED, etc.
    platform: str = "unknown"  # FB, etc.


@dataclass 
class ConversionMetrics:
    """Métricas de conversão agregadas."""
    initiate_checkout: int = 0
    purchase: int = 0
    
    @property
    def conversion_rate(self) -> float:
        if self.initiate_checkout == 0:
            return 0.0
        return (self.purchase / self.initiate_checkout) * 100


@dataclass
class AggregatedConversions:
    """Conversões agregadas por diferentes dimensões."""
    by_campaign: dict[str, ConversionMetrics] = field(default_factory=dict)
    by_squad: dict[str, ConversionMetrics] = field(default_factory=dict)
    by_checkout: dict[str, ConversionMetrics] = field(default_factory=dict)
    by_product: dict[str, ConversionMetrics] = field(default_factory=dict)
    total: ConversionMetrics = field(default_factory=ConversionMetrics)


def extract_campaign_info(campaign_name: str, campaign_id: str = "") -> CampaignInfo:
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
        campaign_name=campaign_name,
    )
    
    if len(parts) > 0:
        info.platform = parts[0].upper()
    
    if len(parts) > 1:
        responsible = parts[1]
        info.squad = (responsible.split("-")[0] or "unknown").strip().upper()
    
    if len(parts) > 2:
        checkout = parts[2].strip().lower()
        # Normalizar nomes de checkout
        if "cartpanda" in checkout:
            info.checkout = "Cartpanda"
        elif "clickbank" in checkout:
            info.checkout = "Clickbank"
        else:
            info.checkout = parts[2].strip()
    
    if len(parts) > 3:
        info.niche = parts[3].strip().upper()
    
    if len(parts) > 4:
        info.product = parts[4].strip()
    
    return info


def _get_campaign_id(row: dict) -> str:
    """Extrai o ID da campanha de uma linha de dados."""
    campaign = row.get("campaign")
    if isinstance(campaign, dict):
        nested_id = str(campaign.get("id") or campaign.get("campaign_id") or "").strip()
        if nested_id:
            return nested_id

    return str(
        row.get("campaign_id")
        or row.get("campaignId")
        or row.get("cid")
        or row.get("id")
        or row.get("campaign")
        or ""
    ).strip()


def _get_campaign_name(row: dict) -> str:
    """Extrai o nome da campanha de uma linha de dados."""
    campaign = row.get("campaign")
    if isinstance(campaign, dict):
        nested_name = str(campaign.get("name") or campaign.get("campaign_name") or "").strip()
        if nested_name:
            return nested_name

    return str(row.get("campaign") or row.get("campaign_name") or "").strip()


def _get_conversion_type(row: dict) -> Optional[str]:
    """
    Extrai e normaliza o tipo de conversão.
    Retorna None se não for um tipo válido (Purchase ou InitiateCheckout).
    """
    raw_type = str(
        row.get("type")
        or row.get("event_type")
        or row.get("conversion_type")
        or row.get("conversionType")
        or row.get("goal")
        or row.get("event")
        or ""
    ).strip().lower()

    if raw_type in VALID_CONVERSION_TYPES:
        return raw_type
    
    # Tentar normalizar variações comuns
    if "purchase" in raw_type:
        return "purchase"
    if "initiate" in raw_type and "checkout" in raw_type:
        return "initiatecheckout"
    
    return None


def _get_event_count(row: dict) -> int:
    """Extrai a quantidade de eventos de uma linha."""
    for key in (
        "count",
        "event_count",
        "events",
        "conversions",
        "total",
        "value",
        "qty",
        "amount",
    ):
        raw = row.get(key)
        if raw is None:
            continue
        try:
            return max(int(float(raw)), 0)
        except (TypeError, ValueError):
            continue
    return 1


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
    per_page: int = 1000,
) -> list[dict]:
    """Busca uma página de conversões da API."""
    params = {
        "api_key": REDTRACK_API_KEY,
        "date_from": date_from,
        "date_to": date_to,
        "time_interval": "lasthour",
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
        "date_from": date_from,
        "date_to": date_to,
        "type": event_type,
        "timezone": "America/Sao_Paulo",
        "per": 1000,
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
            campaign_id = _get_campaign_id(row)
            if not campaign_id:
                continue

            campaign_name = _get_campaign_name(row)
            count = _get_event_count(row)

            if campaign_id not in campaign_info_cache:
                campaign_info_cache[campaign_id] = extract_campaign_info(campaign_name, campaign_id)

            info = campaign_info_cache[campaign_id]
            result.by_campaign.setdefault(campaign_id, ConversionMetrics())
            result.by_squad.setdefault(info.squad, ConversionMetrics())
            result.by_checkout.setdefault(info.checkout, ConversionMetrics())
            result.by_product.setdefault(info.product, ConversionMetrics())

            if is_purchase:
                result.by_campaign[campaign_id].purchase += count
                result.by_squad[info.squad].purchase += count
                result.by_checkout[info.checkout].purchase += count
                result.by_product[info.product].purchase += count
                result.total.purchase += count
            else:
                result.by_campaign[campaign_id].initiate_checkout += count
                result.by_squad[info.squad].initiate_checkout += count
                result.by_checkout[info.checkout].initiate_checkout += count
                result.by_product[info.product].initiate_checkout += count
                result.total.initiate_checkout += count

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
    
    page = 1
    total_rows = 0
    filtered_rows = 0
    
    while True:
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
            # Validar tipo de conversão
            conv_type = _get_conversion_type(row)
            if conv_type is None:
                # Ignorar tipos que não são Purchase ou InitiateCheckout
                logger.debug("Ignorando tipo de conversão: %s", row.get("type"))
                continue
            
            filtered_rows += 1
            
            campaign_id = _get_campaign_id(row)
            if not campaign_id:
                continue
            
            campaign_name = _get_campaign_name(row)
            count = _get_event_count(row)
            
            # Extrair informações da campanha (usar cache para performance)
            if campaign_id not in campaign_info_cache:
                campaign_info_cache[campaign_id] = extract_campaign_info(
                    campaign_name, 
                    campaign_id
                )
            
            info = campaign_info_cache[campaign_id]
            
            # Agregar por campanha
            if campaign_id not in result.by_campaign:
                result.by_campaign[campaign_id] = ConversionMetrics()
            
            # Agregar por squad
            if info.squad not in result.by_squad:
                result.by_squad[info.squad] = ConversionMetrics()
            
            # Agregar por checkout
            if info.checkout not in result.by_checkout:
                result.by_checkout[info.checkout] = ConversionMetrics()
            
            # Agregar por produto
            if info.product not in result.by_product:
                result.by_product[info.product] = ConversionMetrics()
            
            # Atualizar contadores
            if conv_type == "initiatecheckout":
                result.by_campaign[campaign_id].initiate_checkout += count
                result.by_squad[info.squad].initiate_checkout += count
                result.by_checkout[info.checkout].initiate_checkout += count
                result.by_product[info.product].initiate_checkout += count
                result.total.initiate_checkout += count
            elif conv_type == "purchase":
                result.by_campaign[campaign_id].purchase += count
                result.by_squad[info.squad].purchase += count
                result.by_checkout[info.checkout].purchase += count
                result.by_product[info.product].purchase += count
                result.total.purchase += count
        
        logger.debug("Página %s: %s linhas, %s filtradas", page, len(rows), filtered_rows)
        
        if len(rows) < 1000:
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
