import logging
import asyncio
import sys

from pathlib import Path

class _PrettyFormatter(logging.Formatter):
    LEVEL_ICONS = {
        "DEBUG": "🔍",
        "INFO": "ℹ️ ",
        "WARNING": "⚠️ ",
        "ERROR": "❌",
        "CRITICAL": "🔥",
    }

    def format(self, record: logging.LogRecord) -> str:
        icon = self.LEVEL_ICONS.get(record.levelname, "•")
        record.level_icon = icon
        return super().format(record)


def _configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        _PrettyFormatter(
            fmt="%(asctime)s | %(level_icon)s %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


_configure_logging()
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

