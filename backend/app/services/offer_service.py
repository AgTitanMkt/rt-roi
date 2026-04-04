"""
Offer Service: Busca e cacheia dados de ofertas do Redtrack.

Responsabilidade: Fazer requisições para a API de ofertas do Redtrack
e retornar os dados da oferta em um formato estruturado.
"""
import logging
import asyncio
from typing import Optional

import httpx

from .redtrack.http_client import make_request_with_retry
from .redtrack.settings import REDTRACK_API_KEY, REDTRACK_OFFER_URL

logger = logging.getLogger(__name__)


async def fetch_offer_data(offer_id: str) -> Optional[dict]:
    """
    Busca dados de uma oferta específica do Redtrack.

    Args:
        offer_id: ID da oferta a ser buscada

    Returns:
        Dict com os dados da oferta ou None se não encontrar
    """
    if not offer_id or not REDTRACK_API_KEY:
        logger.warning("❌ offer_id ou REDTRACK_API_KEY não fornecidos")
        return None

    logger.info(f"🔍 Buscando dados da oferta: {offer_id}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Tenta diferentes formatos de parametrização
        for params in (
            {"api_key": REDTRACK_API_KEY, "id": offer_id},
            {"api_key": REDTRACK_API_KEY, "offer_id": offer_id},
            {"api_key": REDTRACK_API_KEY, "offerId": offer_id},
        ):
            try:
                logger.debug(f"   Tentando com params: {sorted(params.keys())}")
                result = await make_request_with_retry(
                    client,
                    REDTRACK_OFFER_URL,
                    params,
                    delay_after=0.0
                )

                if result:
                    logger.info(f"✅ Oferta {offer_id} encontrada com sucesso")
                    return result if isinstance(result, dict) else {"data": result}

            except Exception as e:
                logger.debug(f"   Falha com params {sorted(params.keys())}: {str(e)}")
                continue

    logger.warning(f"⚠️  Não foi possível buscar a oferta {offer_id}")
    return None


def sync_fetch_offer_data(offer_id: str) -> Optional[dict]:
    """
    Versão síncrona de fetch_offer_data para uso em endpoints FastAPI.

    Args:
        offer_id: ID da oferta a ser buscada

    Returns:
        Dict com os dados da oferta ou None se não encontrar
    """
    try:
        return asyncio.run(fetch_offer_data(offer_id))
    except Exception as e:
        logger.error(f"❌ Erro ao buscar oferta {offer_id}: {str(e)}")
        return None

