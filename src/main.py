import asyncio

from src.agents.lever import LeverAgent
from src.processors.lever import LeverAutoApply, LeverQuestionProcessor

agent = LeverAgent()


async def main():
    processor = LeverQuestionProcessor(agent)
    await processor.process()


async def main_():
    auto_apply = LeverAutoApply(show_browser=True)
    await auto_apply.process()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
