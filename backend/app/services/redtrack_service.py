import asyncio
import sys
import logging

from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

try:
    from .redtrack.pipeline import redtrack_reports
except ImportError:
    current = Path(__file__).resolve()
    backend_root = str(current.parents[2])
    project_root = str(current.parents[3])
    for path in (backend_root, project_root):
        if path not in sys.path:
            sys.path.insert(0, path)

    from app.services.redtrack.pipeline import redtrack_reports


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

