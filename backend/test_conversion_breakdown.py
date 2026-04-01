#!/usr/bin/env python3
"""
Script para testar a API de conversion breakdown
"""
import sys
import asyncio
from pathlib import Path

# Adicionar backend ao path
backend_root = str(Path(__file__).parent.parent / "backend")
sys.path.insert(0, backend_root)

from app.core.database import SessionLocal
from app.services.metrics_service import get_conversion_breakdown
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)

def test_conversion_breakdown():
    db = SessionLocal()
    try:
        logger.info("=" * 80)
        logger.info("🧪 TESTANDO CONVERSION BREAKDOWN")
        logger.info("=" * 80)

        # Teste 1: Sem filtros (todos os dados)
        logger.info("\n1️⃣  Teste: Sem filtros (todos os dados)")
        logger.info("-" * 80)
        result = get_conversion_breakdown(db, period="24h")
        logger.info(f"Resultado: {len(result)} registros")
        if result:
            logger.info("Primeiros 5 registros:")
            for i, item in enumerate(result[:5], 1):
                logger.info(f"  {i}. squad={item['squad']}, checkout={item['checkout']}, "
                           f"product={item['product']}, "
                           f"initiate={item['initiate_checkout']}, purchase={item['purchase']}")
        else:
            logger.warning("⚠️  NENHUM DADO RETORNADO!")

        # Teste 2: Com squad específico
        logger.info("\n2️⃣  Teste: Com squad='FBR'")
        logger.info("-" * 80)
        result_fbr = get_conversion_breakdown(db, period="24h", squad="FBR")
        logger.info(f"Resultado: {len(result_fbr)} registros")
        if result_fbr:
            logger.info("Primeiros 3 registros:")
            for i, item in enumerate(result_fbr[:3], 1):
                logger.info(f"  {i}. squad={item['squad']}, checkout={item['checkout']}, "
                           f"product={item['product']}")

        # Teste 3: Com checkout específico
        logger.info("\n3️⃣  Teste: Com checkout='CARTPANDA'")
        logger.info("-" * 80)
        result_cart = get_conversion_breakdown(db, period="24h", checkout="CARTPANDA")
        logger.info(f"Resultado: {len(result_cart)} registros")
        if result_cart:
            logger.info("Primeiros 3 registros:")
            for i, item in enumerate(result_cart[:3], 1):
                logger.info(f"  {i}. checkout={item['checkout']}, "
                           f"initiate={item['initiate_checkout']}, purchase={item['purchase']}")

        # Teste 4: Período weekly
        logger.info("\n4️⃣  Teste: Período semanal")
        logger.info("-" * 80)
        result_weekly = get_conversion_breakdown(db, period="weekly")
        logger.info(f"Resultado: {len(result_weekly)} registros")

        # Teste 5: Período mensal
        logger.info("\n5️⃣  Teste: Período mensal")
        logger.info("-" * 80)
        result_monthly = get_conversion_breakdown(db, period="monthly")
        logger.info(f"Resultado: {len(result_monthly)} registros")

        logger.info("\n" + "=" * 80)
        logger.info("✅ TESTES CONCLUÍDOS")
        logger.info("=" * 80)

    finally:
        db.close()

if __name__ == "__main__":
    test_conversion_breakdown()

