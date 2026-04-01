#!/usr/bin/env python3
"""
Script para normalizar dados existentes na tabela tb_daily_conversion_entities
"""
import sys
from pathlib import Path

# Adicionar backend ao path
backend_root = str(Path(__file__).parent.parent / "backend")
sys.path.insert(0, backend_root)

from app.core.database import SessionLocal
from app.models.metrics import DailyConversionEntity
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s"
)

logger = logging.getLogger(__name__)

def normalize_conversion_entities():
    """Normaliza todos os valores em tb_daily_conversion_entities para UPPERCASE"""
    db = SessionLocal()
    try:
        logger.info("=" * 80)
        logger.info("🔧 NORMALIZANDO DADOS NA TABELA tb_daily_conversion_entities")
        logger.info("=" * 80)

        # Contar registros antes
        total_before = db.query(DailyConversionEntity).count()
        logger.info(f"\n📊 Total de registros: {total_before}")

        # Buscar registros com valores não normalizados
        records = db.query(DailyConversionEntity).all()

        updated_count = 0
        for record in records:
            updated = False

            # Normalizar squad
            if record.squad and record.squad != record.squad.upper():
                logger.info(f"  Atualizando squad: '{record.squad}' → '{record.squad.upper()}'")
                record.squad = record.squad.upper()
                updated = True

            # Normalizar checkout
            if record.checkout and record.checkout != record.checkout.upper():
                logger.info(f"  Atualizando checkout: '{record.checkout}' → '{record.checkout.upper()}'")
                record.checkout = record.checkout.upper()
                updated = True

            # Normalizar product
            if record.product and record.product != record.product.upper():
                logger.info(f"  Atualizando product: '{record.product}' → '{record.product.upper()}'")
                record.product = record.product.upper()
                updated = True

            if updated:
                updated_count += 1

        # Fazer commit
        if updated_count > 0:
            logger.info(f"\n💾 Salvando {updated_count} registros atualizados...")
            db.commit()
            logger.info("✅ Dados normalizados com sucesso!")
        else:
            logger.info("\n✅ Todos os dados já estão normalizados!")

        # Verificar resultado
        logger.info("\n🔍 Verificando dados após normalização:")
        logger.info("-" * 80)

        # Contar tipos de squad
        squads = db.query(DailyConversionEntity.squad).distinct().all()
        logger.info(f"Squads únicos: {[s[0] for s in squads]}")

        # Contar tipos de checkout
        checkouts = db.query(DailyConversionEntity.checkout).distinct().all()
        logger.info(f"Checkouts únicos: {[c[0] for c in checkouts]}")

        # Amostra de dados
        logger.info("\n📋 Amostra de dados após normalização:")
        samples = db.query(DailyConversionEntity).limit(5).all()
        for i, sample in enumerate(samples, 1):
            logger.info(f"  {i}. squad={sample.squad}, checkout={sample.checkout}, "
                       f"product={sample.product}")

        logger.info("\n" + "=" * 80)
        logger.info("✅ NORMALIZAÇÃO CONCLUÍDA")
        logger.info("=" * 80)

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erro durante normalização: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    normalize_conversion_entities()

