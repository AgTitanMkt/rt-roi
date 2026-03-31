from datetime import datetime, timedelta
import os
import asyncio
import sys
import logging

from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from dotenv import load_dotenv, find_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

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
    campaign_id = params.get("campaign_id", "N/A")
    page = params.get("page", 1)
    event_type = params.get("type", "N/A")
    
    for attempt in range(MAX_RETRIES):
        try:
            logger.debug(f"📤 Requisição: campaign_id={campaign_id}, page={page}, type={event_type}, attempt={attempt + 1}/{MAX_RETRIES}")
            res = await client.get(url, params=params)
            
            # If we got rate limited, wait and retry
            if res.status_code == 429:
                wait_time = min(backoff, MAX_BACKOFF)
                logger.warning(f"⚠️  Rate limited (429)! campaign_id={campaign_id}, page={page}. Tentativa {attempt + 1}/{MAX_RETRIES}. Aguardando {wait_time}s antes de retry...")
                await asyncio.sleep(wait_time)
                backoff *= 2  # Exponential backoff
                continue
            
            res.raise_for_status()
            response_data = res.json()
            response_count = len(response_data) if isinstance(response_data, list) else 1
            logger.info(f"✅ Requisição bem-sucedida: campaign_id={campaign_id}, page={page}, type={event_type}, linhas={response_count}")
            
            # Add delay after successful request to avoid rate limiting
            if delay_after > 0:
                await asyncio.sleep(delay_after)
            
            return response_data
        
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code == 429:
                # Rate limit: retry with backoff
                wait_time = min(backoff, MAX_BACKOFF)
                logger.warning(f"⚠️  Rate limited (429) em tentativa {attempt + 1}/{MAX_RETRIES}. Aguardando {wait_time}s...")
                await asyncio.sleep(wait_time)
                backoff *= 2
            else:
                # Non-429 errors: fail immediately
                logger.error(f"❌ Erro HTTP {e.response.status_code}: {e}")
                raise
        
        except Exception as e:
            last_error = e
            logger.error(f"❌ Erro inesperado na requisição: {type(e).__name__}: {e}")
            raise
    
    # All retries exhausted
    error_msg = f"Falhou após {MAX_RETRIES} tentativas: {last_error}"
    logger.error(f"❌ {error_msg}")
    if last_error:
        raise RuntimeError(error_msg)
    raise RuntimeError(f"Falhou após {MAX_RETRIES} tentativas")



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
        logger.info("💾 Nenhum dado para persistir (payload vazio)")
        return

    logger.info(f"💾 Iniciando persistência de {len(payload)} registros no banco de dados...")
    db = SessionLocal()
    try:
        result = insert_metrics(db, payload)
        logger.info(
            f"✅ Persistencia finalizada: "
            f"inseridos={result['inserted']}, "
            f"atualizados={result['updated']}, "
            f"ignorados={result['ignored']}"
        )
    except Exception as e:
        logger.error(f"❌ Erro ao persistir métricas: {type(e).__name__}: {e}")
        raise
    finally:
        db.close()


async def _fetch_all_events(
    client: httpx.AsyncClient,
    *,
    date_from: str,
    date_to: str,
) -> dict:
    """
    Fetch all events (InitiateCheckout and Purchase) in a single request.
    Returns a dict organized by campaign_id with event counts.
    
    Returns:
        {
            "campaign_id_1": {"InitiateCheckout": 10, "Purchase": 5},
            "campaign_id_2": {"InitiateCheckout": 3, "Purchase": 2},
            ...
        }
    """
    logger.info(f"📡 Buscando todos os eventos (InitiateCheckout + Purchase) do período {date_from} a {date_to}...")
    
    events_by_campaign = {}
    
    # Fetch InitiateCheckout events
    logger.info("   🔵 Buscando eventos InitiateCheckout...")
    params_initiate = {
        "api_key": REDTRACK_API_KEY,
        "date_from": date_from,
        "date_to": date_to,
        "type": "InitiateCheckout",
        "country_code": "US",
        "per": 1000,
        "page": 1,
    }
    
    page = 1
    while True:
        rows = await _make_request_with_retry(client, REDTRACK_REPORT_URL, params_initiate, delay_after=0.3)
        
        if not isinstance(rows, list):
            logger.error(f"❌ Resposta inesperada para InitiateCheckout: type={type(rows)}")
            raise RuntimeError("Resposta inesperada da API Redtrack: esperado lista de registros.")
        
        logger.debug(f"      Página {page}: {len(rows)} InitiateCheckout recebidos")
        
        for row in rows:
            campaign_id = str(
                row.get("campaign_id")
                or row.get("campaignId")
                or row.get("campaign")
                or ""
            ).strip()
            if campaign_id:
                if campaign_id not in events_by_campaign:
                    events_by_campaign[campaign_id] = {"InitiateCheckout": 0, "Purchase": 0}
                events_by_campaign[campaign_id]["InitiateCheckout"] += 1
        
        if len(rows) < params_initiate["per"]:
            logger.info(f"   ✅ Total de InitiateCheckout: {sum(c['InitiateCheckout'] for c in events_by_campaign.values())}")
            break
        
        params_initiate["page"] += 1
        page += 1
    
    # Fetch Purchase events
    logger.info("   🔴 Buscando eventos Purchase...")
    params_purchase = {
        "api_key": REDTRACK_API_KEY,
        "date_from": date_from,
        "date_to": date_to,
        "type": "Purchase",
        "country_code": "US",
        "per": 1000,
        "page": 1,
    }
    
    page = 1
    while True:
        rows = await _make_request_with_retry(client, REDTRACK_REPORT_URL, params_purchase, delay_after=0.3)
        
        if not isinstance(rows, list):
            logger.error(f"❌ Resposta inesperada para Purchase: type={type(rows)}")
            raise RuntimeError("Resposta inesperada da API Redtrack: esperado lista de registros.")
        
        logger.debug(f"      Página {page}: {len(rows)} Purchase recebidos")
        
        for row in rows:
            campaign_id = str(
                row.get("campaign_id")
                or row.get("campaignId")
                or row.get("campaign")
                or ""
            ).strip()
            if campaign_id:
                if campaign_id not in events_by_campaign:
                    events_by_campaign[campaign_id] = {"InitiateCheckout": 0, "Purchase": 0}
                events_by_campaign[campaign_id]["Purchase"] += 1
        
        if len(rows) < params_purchase["per"]:
            logger.info(f"   ✅ Total de Purchase: {sum(c['Purchase'] for c in events_by_campaign.values())}")
            break
        
        params_purchase["page"] += 1
        page += 1
    
    logger.info(f"✅ Eventos agrupados por campaign: {len(events_by_campaign)} campanhas identificadas")
    return events_by_campaign


async def _calculate_conversions(
    events_by_campaign: dict,
) -> dict:
    """
    Calculate conversion rates from pre-fetched events.
    
    Returns:
        {
            "campaign_id_1": 0.5,  # conversion rate
            "campaign_id_2": 0.666,
            ...
        }
    """
    logger.info("📊 Calculando taxas de conversão por campaign...")
    conversions = {}
    
    for campaign_id, events in events_by_campaign.items():
        initiate = events.get("InitiateCheckout", 0)
        purchase = events.get("Purchase", 0)
        
        if initiate == 0:
            conversion = 0.0
            logger.debug(f"   ⚠️  {campaign_id}: sem InitiateCheckout, conversion=0.0")
        else:
            conversion = (purchase / initiate) * 100
            logger.debug(f"   ✅ {campaign_id}: ({purchase}/{initiate}) * 100 = {conversion:.2f}%")
        
        conversions[campaign_id] = conversion
    
    return conversions


async def redtrack_reports() -> RedtrackResponse:
    logger.info("=" * 80)
    logger.info("🚀 INICIANDO SINCRONIZAÇÃO DO REDTRACK")
    logger.info("=" * 80)
    
    now_sp = datetime.now(SAO_PAULO_TZ)
    last_closed_hour = now_sp.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    date_from = last_closed_hour.strftime("%Y-%m-%d")
    date_to = now_sp.strftime("%Y-%m-%d")

    logger.info(f"⏰ Horário atual (São Paulo): {now_sp.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info(f"⏰ Hora fechada anterior: {last_closed_hour.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info(f"📅 Período de busca: {date_from} a {date_to}")

    params = {
        "api_key": REDTRACK_API_KEY,
        "group": "campaign,date",
        "date_from": date_from,
        "date_to": date_to,
        "timezone": "America/Sao_Paulo",
        "per": 1000,
        "page": 1,
    }

    if not REDTRACK_API_KEY:
        logger.error("❌ REDTRACK_API_KEY não definida no .env")
        raise RuntimeError("REDTRACK_API_KEY nao encontrada. Defina no .env antes de executar.")

    params = dict(params)
    params["page"] = 1

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Fetch conversion events (InitiateCheckout + Purchase) once
        logger.info("")
        logger.info("📌 ETAPA 1: Buscando eventos de conversão...")
        events_by_campaign = await _fetch_all_events(
            client,
            date_from=date_from,
            date_to=date_to,
        )
        
        # Step 2: Calculate conversions from fetched events
        logger.info("")
        logger.info("📌 ETAPA 2: Calculando conversões...")
        conversions = await _calculate_conversions(events_by_campaign)
        logger.info(f"✅ {len(conversions)} campanhas com conversão calculada")
        
        # Step 3: Fetch main report data
        logger.info("")
        logger.info("📌 ETAPA 3: Buscando dados de campanhas...")
        data: RedtrackResponse = []
        cost_total = 0.0
        profit_total = 0.0
        page_count = 0

        while True:
            page_count += 1
            logger.info(f"📄 Processando página {page_count}...")
            
            page_rows = await _make_request_with_retry(
                client,
                REDTRACK_REPORT_URL,
                params,
            )

            if not isinstance(page_rows, list):
                logger.error(f"❌ Resposta inesperada: esperado lista, recebido {type(page_rows)}")
                raise RuntimeError("Resposta inesperada da API Redtrack: esperado lista de registros.")

            logger.info(f"   ✓ {len(page_rows)} registros recebidos")

            for idx, x in enumerate(page_rows, 1):
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

                # Use pre-calculated conversion
                conversion = conversions.get(campaign_id, 0.0)
                    
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
                
                logger.debug(f"   [{idx}/{len(page_rows)}] {campaign_id} | squad={squad} | cost={cost:.2f} | profit={profit:.2f} | roi={x.get('roi', 0):.2f} | conversion={conversion:.4f}")

            if len(page_rows) < params["per"]:
                logger.info(f"✅ Fim da paginação atingido (página {page_count})")
                break

            params["page"] += 1

        roi_total = (profit_total / cost_total) if cost_total > 0 else 0.0

        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 RESUMO DA SINCRONIZAÇÃO")
        logger.info("=" * 80)
        logger.info(f"📋 Total de campanhas: {len(data)}")
        logger.info(f"💰 Custo total: R$ {cost_total:,.2f}")
        logger.info(f"💵 Lucro total: R$ {profit_total:,.2f}")
        logger.info(f"📈 ROI total: {roi_total:.4f}")
        avg_conversion = sum(conversions.values()) / len(conversions) if conversions else 0
        logger.info(f"🔄 Conversão média: {avg_conversion:.4f}")
        logger.info("")

        persist_metrics_report(data)
        
        logger.info("=" * 80)
        logger.info("✅ SINCRONIZAÇÃO CONCLUÍDA COM SUCESSO!")
        logger.info("=" * 80)
        logger.info("")
        
        return data


if __name__ == "__main__":
    try:
        logger.info("\n" + "=" * 80)
        logger.info("🔧 EXECUÇÃO MANUAL DO REDTRACK_SERVICE")
        logger.info("=" * 80 + "\n")
        
        data = asyncio.run(redtrack_reports())
        
        logger.info("\n" + "=" * 80)
        logger.info(f"✅ SUCESSO: {len(data)} registros obtidos e processados do Redtrack")
        logger.info("=" * 80 + "\n")
        
    except Exception as exc:
        logger.error("\n" + "=" * 80)
        logger.error(f"❌ ERRO DURANTE A EXECUÇÃO: {type(exc).__name__}")
        logger.error(f"   Mensagem: {str(exc)}")
        logger.error("=" * 80 + "\n")
        raise

