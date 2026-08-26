import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.agents.agent import Agent
from src.cli import build_parser, show_settings, update_settings


class SessionContext:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, *args):
        return False


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


def test_cli_parses_provider_neutral_settings_commands():
    parser = build_parser()
    assert parser.parse_args(["settings", "show", "--installation-id", "inst"]).settings_action == "show"
    args = parser.parse_args([
        "settings", "update", "--installation-id", "inst", "--llm-provider", "openai",
        "--api-key", "secret", "--auto-fill",
    ])
    assert args.settings_action == "update"
    assert args.api_key == "secret"
    assert args.auto_fill is True
    assert parser.parse_args([
        "settings", "update", "--installation-id", "inst", "--llm-provider", "lm_studio",
    ]).llm_provider == "lm_studio"
    assert parser.parse_args([
        "settings", "update", "--installation-id", "inst", "--llm-model", "preferred-model",
    ]).llm_model == "preferred-model"


def test_show_settings_masks_api_key(capsys):
    record = SimpleNamespace(
        installation_id="inst", llm_provider="openai", auto_fill=True,
        resume="resume", preferences="preferences", openai_key="sk-test-secret",
    )
    session = MagicMock()
    session.query.return_value.filter_by.return_value.one_or_none.return_value = record

    with patch("src.cli.SessionLocal", return_value=SessionContext(session)):
        assert show_settings("inst") == 0

    captured = capsys.readouterr().out
    output = json.loads(captured)
    assert output["has_api_key"] is True
    assert output["api_key"] == "sk-t...cret"
    assert "sk-test-secret" not in captured


def test_update_settings_changes_only_supplied_values(capsys):
    record = SimpleNamespace(
        installation_id="inst", llm_provider="ollama", auto_fill=False,
        resume="old resume", preferences="old preferences", openai_key=None,
    )
    session = MagicMock()
    session.query.return_value.filter_by.return_value.one_or_none.return_value = record

    with patch("src.cli.SessionLocal", return_value=SessionContext(session)):
        assert update_settings("inst", llm_provider="openai", api_key="new-key-value") == 0

    assert record.llm_provider == "openai"
    assert record.openai_key == "new-key-value"
    assert record.resume == "old resume"
    assert record.preferences == "old preferences"
    assert record.auto_fill is False
    session.commit.assert_called_once()
    assert json.loads(capsys.readouterr().out)["api_key"] == "new-...alue"


def test_update_settings_supports_file_values_and_explicit_clearing(tmp_path):
    resume_file = tmp_path / "resume.txt"
    resume_file.write_text("new resume", encoding="utf-8")
    record = SimpleNamespace(
        installation_id="inst", llm_provider="ollama", auto_fill=True,
        resume="old resume", preferences="old preferences", openai_key="old-key",
    )
    session = MagicMock()
    session.query.return_value.filter_by.return_value.one_or_none.return_value = record

    with patch("src.cli.SessionLocal", return_value=SessionContext(session)):
        update_settings(
            "inst", resume_file=str(resume_file), clear_preferences=True,
            clear_api_key=True, auto_fill=False,
        )

    assert record.resume == "new resume"
    assert record.preferences == ""
    assert record.openai_key is None
    assert record.auto_fill is False
