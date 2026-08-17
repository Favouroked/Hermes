import asyncio

from src.agents.agent import Agent
from snippets.lever_processor_v1 import LeverAutoApply, LeverQuestionProcessor

agent = Agent()


async def main():
    processor = LeverQuestionProcessor(agent)
    await processor.process()


async def main_():
    auto_apply = LeverAutoApply(show_browser=True)
    await auto_apply.process()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
