import asyncio
import logging

import httpx

from .settings import INITIAL_BACKOFF, MAX_BACKOFF, MAX_RETRIES, RATE_LIMIT_DELAY

logger = logging.getLogger(__name__)


async def make_request_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: dict,
    delay_after: float = RATE_LIMIT_DELAY,
) -> dict:
    backoff = INITIAL_BACKOFF
    last_error = None
    campaign_id = params.get("campaign_id", "N/A")
    page = params.get("page", 1)
    event_type = params.get("type", "N/A")

    for attempt in range(MAX_RETRIES):
        try:
            logger.debug(
                "📤 Requisição: campaign_id=%s, page=%s, type=%s, attempt=%s/%s",
                campaign_id,
                page,
                event_type,
                attempt + 1,
                MAX_RETRIES,
            )
            res = await client.get(url, params=params)

            if res.status_code == 429:
                wait_time = min(backoff, MAX_BACKOFF)
                logger.warning(
                    "⚠️  Rate limited (429)! campaign_id=%s, page=%s. Tentativa %s/%s. "
                    "Aguardando %ss antes de retry...",
                    campaign_id,
                    page,
                    attempt + 1,
                    MAX_RETRIES,
                    wait_time,
                )
                await asyncio.sleep(wait_time)
                backoff *= 2
                continue

            res.raise_for_status()
            payload = res.json()
            count = len(payload) if isinstance(payload, list) else 1
            logger.info(
                "✅ Requisição bem-sucedida: campaign_id=%s, page=%s, type=%s, linhas=%s",
                campaign_id,
                page,
                event_type,
                count,
            )

            if delay_after > 0:
                await asyncio.sleep(delay_after)

            return payload

        except httpx.HTTPStatusError as exc:
            last_error = exc
            if exc.response.status_code == 429:
                wait_time = min(backoff, MAX_BACKOFF)
                logger.warning(
                    "⚠️  Rate limited (429) em tentativa %s/%s. Aguardando %ss...",
                    attempt + 1,
                    MAX_RETRIES,
                    wait_time,
                )
                await asyncio.sleep(wait_time)
                backoff *= 2
            else:
                logger.error("❌ Erro HTTP %s: %s", exc.response.status_code, exc)
                raise
        except Exception as exc:
            last_error = exc
            logger.error("❌ Erro inesperado na requisição: %s: %s", type(exc).__name__, exc)
            raise

    msg = f"Falhou após {MAX_RETRIES} tentativas: {last_error}"
    logger.error("❌ %s", msg)
    raise RuntimeError(msg)

