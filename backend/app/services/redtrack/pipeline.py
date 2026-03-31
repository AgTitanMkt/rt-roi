from datetime import datetime, timedelta
import logging

import httpx

from ..redis_service import invalidate_metrics_cache
from ...schemas.redtrack_schema import RedtrackReportItem, RedtrackResponse
from .conversions import calculate_conversions, fetch_all_events
from .daily_summary import fetch_daily_summary_rows, log_cards_preview, persist_daily_summary_snapshot
from .http_client import make_request_with_retry
from .persistence import persist_metrics_report
from .settings import REDTRACK_API_KEY, REDTRACK_REPORT_URL, SAO_PAULO_TZ

logger = logging.getLogger(__name__)


async def redtrack_reports() -> RedtrackResponse:
    logger.info("=" * 80)
    logger.info("🚀 INICIANDO SINCRONIZAÇÃO DO REDTRACK")
    logger.info("=" * 80)

    now_sp = datetime.now(SAO_PAULO_TZ)
    last_closed_hour = now_sp.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    date_from = last_closed_hour.strftime("%Y-%m-%d")
    date_to = now_sp.strftime("%Y-%m-%d")

    logger.info("⏰ Horário atual (São Paulo): %s", now_sp.strftime('%Y-%m-%d %H:%M:%S %Z'))
    logger.info("⏰ Hora fechada anterior: %s", last_closed_hour.strftime('%Y-%m-%d %H:%M:%S %Z'))
    logger.info("📅 Período de busca: %s a %s", date_from, date_to)

    if not REDTRACK_API_KEY:
        raise RuntimeError("REDTRACK_API_KEY nao encontrada. Defina no .env antes de executar.")

    params_hourly = {
        "api_key": REDTRACK_API_KEY,
        "group": "campaign,date",
        "date_from": date_from,
        "date_to": date_to,
        "time_interval": "lasthour",
        "timezone": "America/Sao_Paulo",
        "per": 1000,
        "page": 1,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        logger.info("")
        logger.info("📌 ETAPA 1: Buscando dados principais de campanhas...")

        data: RedtrackResponse = []
        campaign_ids_seen: set[str] = set()
        cost_total = 0.0
        profit_total = 0.0
        page_count = 0

        while True:
            page_count += 1
            logger.info("📄 Processando página %s...", page_count)

            page_rows = await make_request_with_retry(client, REDTRACK_REPORT_URL, params_hourly)
            if not isinstance(page_rows, list):
                raise RuntimeError("Resposta inesperada da API Redtrack: esperado lista de registros.")

            logger.info("   ✓ %s registros recebidos", len(page_rows))

            for idx, row in enumerate(page_rows, 1):
                cost = float(row.get("cost", 0) or 0)
                profit = float(row.get("profit", 0) or 0)
                raw_date = row.get("date")
                if not raw_date:
                    continue

                campaign_name = str(row.get("campaign") or "").strip()
                campaign_id = str(row.get("campaign_id") or row.get("campaignId") or campaign_name).strip()
                if not campaign_id:
                    continue

                report_datetime = datetime.strptime(raw_date, "%Y-%m-%d").replace(
                    hour=last_closed_hour.hour,
                    minute=0,
                    second=0,
                    microsecond=0,
                    tzinfo=SAO_PAULO_TZ,
                )

                parts = [part.strip() for part in campaign_name.split("|") if part.strip()]
                responsible = parts[1] if len(parts) > 1 else (parts[0] if parts else "unknown")
                squad = responsible.split("-")[0]

                item = RedtrackReportItem(
                    campaign_id=campaign_id,
                    squad=squad,
                    date=report_datetime,
                    cost=cost,
                    revenue=float(row.get("revenue", 0) or 0),
                    profit=profit,
                    roi=float(row.get("roi", 0) or 0),
                    conversion=0.0,
                )

                data.append(item)
                campaign_ids_seen.add(campaign_id)
                profit_total += profit
                cost_total += cost

                logger.debug(
                    "   [%s/%s] %s | squad=%s | cost=%.2f | profit=%.2f | roi=%.2f | conversion=%.4f",
                    idx,
                    len(page_rows),
                    campaign_id,
                    squad,
                    cost,
                    profit,
                    row.get("roi", 0),
                    0.0,
                )

            if len(page_rows) < params_hourly["per"]:
                logger.info("✅ Fim da paginação atingido (página %s)", page_count)
                break

            params_hourly["page"] += 1

        logger.info("")
        logger.info("📌 ETAPA 2: Buscando conversões em requisição separada...")
        conversions: dict[str, float] = {}
        events_by_campaign: dict[str, dict[str, int]] = {}
        try:
            events_by_campaign = await fetch_all_events(client, date_from=date_from, date_to=date_to)
            conversions = calculate_conversions(events_by_campaign)
            logger.info("✅ %s campanhas com conversão calculada", len(conversions))
        except Exception as exc:
            logger.error(
                "❌ Falha ao buscar conversões no Redtrack: %s. "
                "Continuando ingestão de custo/receita/lucro sem bloquear persistência.",
                exc,
            )

        if conversions:
            data = [
                item.model_copy(update={"conversion": conversions.get(item.campaign_id, 0.0)})
                if item.campaign_id in campaign_ids_seen
                else item
                for item in data
            ]

        roi_total = (profit_total / cost_total) if cost_total > 0 else 0.0
        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 RESUMO DA SINCRONIZAÇÃO")
        logger.info("=" * 80)
        logger.info("📋 Total de campanhas: %s", len(data))
        logger.info("💰 Custo total: R$ %s", f"{cost_total:,.2f}")
        logger.info("💵 Lucro total: R$ %s", f"{profit_total:,.2f}")
        logger.info("📈 ROI total: %.4f", roi_total)
        avg_conversion = sum(conversions.values()) / len(conversions) if conversions else 0
        logger.info("🔄 Conversão média: %.4f", avg_conversion)
        logger.info("")

        persist_metrics_report(data)

        logger.info("")
        logger.info("📌 ETAPA 3: Buscando summary diário em requisição separada...")
        try:
            today_date = now_sp.date()
            yesterday_date = today_date - timedelta(days=1)

            for target_date in (today_date, yesterday_date):
                target_day = target_date.strftime("%Y-%m-%d")
                summary_rows = await fetch_daily_summary_rows(client, target_date=target_day)

                if target_date == today_date:
                    target_events = events_by_campaign
                else:
                    target_events = await fetch_all_events(
                        client,
                        date_from=target_day,
                        date_to=target_day,
                    )

                persist_daily_summary_snapshot(summary_rows, target_date, target_events)

            log_cards_preview()
        except Exception as exc:
            logger.error(
                "❌ Falha ao atualizar snapshot diário no Redtrack: %s. "
                "Mantendo persistência horária sem bloqueio.",
                exc,
            )

        try:
            cleared = invalidate_metrics_cache()
            logger.info("🧹 Cache Redis invalidado: %s chaves", cleared)
        except Exception as exc:
            logger.warning("⚠️ Falha ao invalidar cache Redis: %s", exc)

        logger.info("=" * 80)
        logger.info("✅ SINCRONIZAÇÃO CONCLUÍDA COM SUCESSO!")
        logger.info("=" * 80)
        logger.info("")

        return data

