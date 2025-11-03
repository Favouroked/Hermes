import asyncio

from src.processors.lever import LeverProcessor


async def _execute(installation_id: str):
    processor = LeverProcessor(installation_id)
    await processor.process()


def execute(installation_id: str):
    try:
        return asyncio.run(_execute(installation_id))
    except Exception as e:
        raise e
