from src.processors.lever import LeverProcessor
import asyncio


async def _execute(installation_id: str):
    processor = LeverProcessor(installation_id)
    await processor.process()


def execute(installation_id: str):
    raise SystemExit(asyncio.run(_execute(installation_id)))
