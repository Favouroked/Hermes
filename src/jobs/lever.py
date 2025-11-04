import asyncio

from src.config.logger import get_logger
from src.processors.lever import LeverProcessor

logger = get_logger(__name__)


async def _execute(installation_id: str):
    processor = LeverProcessor(installation_id)
    await processor.process()


def execute(installation_id: str):
    try:
        return asyncio.run(_execute(installation_id))
    except Exception as e:
        logger.exception(e)
