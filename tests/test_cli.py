import json

from src.agents.agent import Agent
from src.cli import build_parser


class FakeProvider:
    def __init__(self):
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return json.dumps({"cover_letter": "Dear Hiring Team,\n\nI am excited to apply."})


def test_cover_letter_generation_uses_resume_and_page_text():
    agent = Agent(provider="ollama")
    provider = FakeProvider()
    agent._provider = provider

    assert agent.generate_cover_letter("Build APIs with Python", "Senior Python engineer")
    prompt = provider.calls[0]["user_prompt"]
    assert "Senior Python engineer" in prompt
    assert "Build APIs with Python" in prompt


def test_cli_parses_generation_status_stop_and_loop_commands():
    parser = build_parser()
    assert parser.parse_args(["cover-letter", "generate", "--installation-id", "inst"]).action == "generate"
    assert parser.parse_args(["cover-letter", "status", "--run-id", "run"]).run_id == "run"
    assert parser.parse_args(["cover-letter", "stop", "--run-id", "run"]).run_id == "run"
    assert parser.parse_args(["cover-letter", "apply-loop", "--installation-id", "inst"]).action == "apply-loop"
