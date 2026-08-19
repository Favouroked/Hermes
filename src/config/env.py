import os
from dataclasses import dataclass, field


def _env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


@dataclass(frozen=True)
class EnvConfig:
    """Environment-backed application configuration.

    Values are read when an instance is created so callers can inject an
    explicit configuration in tests or when embedding the application.
    """

    llm_provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "ollama") or "ollama")
    ollama_model: str = field(
        default_factory=lambda: _env("OLLAMA_MODEL", "qwen3:14b") or "qwen3:14b"
    )
    ollama_base_url: str = field(
        default_factory=lambda: _env("OLLAMA_BASE_URL", "http://localhost:11434")
        or "http://localhost:11434"
    )
    openai_api_key: str | None = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    openai_model: str = field(
        default_factory=lambda: _env("OPENAI_MODEL", "gpt-5-nano") or "gpt-5-nano"
    )
    logs_file: str | None = field(default_factory=lambda: _env("LOGS_FILE"))
