#!/usr/bin/env python3
"""
Script para testar a nova formatação de valores desconhecidos
"""
import sys
from pathlib import Path

# Adicionar backend ao path
backend_root = str(Path(__file__).parent.parent / "backend")
sys.path.insert(0, backend_root)

from app.services.redtrack.daily_summary import _normalize_and_format
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s"
)

logger = logging.getLogger(__name__)

def test_normalize_and_format():
    """Testa a função de normalização com valores conhecidos e desconhecidos"""

    logger.info("=" * 80)
    logger.info("🧪 TESTANDO NOVA FORMATAÇÃO DE VALORES DESCONHECIDOS")
    logger.info("=" * 80)

    # Testes
    test_cases = [
        # (raw_value, normalized_value, expected_result)
        ("FBR", "FBR", "FBR"),
        ("NTE", "NTE", "NTE"),
        ("unknown", "unknown", "UNKNOWN"),
        ("xyz", "unknown", "UNKNOWN (XYZ)"),
        ("test_squad", "unknown", "UNKNOWN (TEST_SQUAD)"),
        ("", "unknown", "UNKNOWN"),
        (None, "unknown", "UNKNOWN"),
        ("CARTPANDA", "CARTPANDA", "CARTPANDA"),
        ("clickbank", "CLICKBANK", "CLICKBANK"),
        ("random_checkout", "unknown", "UNKNOWN (RANDOM_CHECKOUT)"),
        ("mind_boost", "MIND_BOOST", "MIND_BOOST"),
        ("strange_product", "unknown", "UNKNOWN (STRANGE_PRODUCT)"),
    ]

    logger.info("\n📋 Executando testes:")
    logger.info("-" * 80)

    all_passed = True
    for i, (raw, normalized, expected) in enumerate(test_cases, 1):
        result = _normalize_and_format(raw, normalized)
        passed = result == expected
        status = "✅ PASS" if passed else "❌ FAIL"

        logger.info(f"{status} Test {i}:")
        logger.info(f"   Raw: {repr(raw)}, Normalized: {repr(normalized)}")
        logger.info(f"   Expected: {repr(expected)}")
        logger.info(f"   Got:      {repr(result)}")

        if not passed:
            all_passed = False

    logger.info("\n" + "=" * 80)
    if all_passed:
        logger.info("✅ TODOS OS TESTES PASSARAM!")
    else:
        logger.info("❌ ALGUNS TESTES FALHARAM!")
    logger.info("=" * 80)

    return all_passed

if __name__ == "__main__":
    success = test_normalize_and_format()
    sys.exit(0 if success else 1)

