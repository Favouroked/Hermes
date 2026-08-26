import os
import unittest
from unittest.mock import patch

from src.agents.agent import Agent
from src.config.env import EnvConfig
from src.config.logger import get_logger
from src.llm.providers import LMStudioProvider, OllamaProvider, OpenAIProvider


class EnvConfigTests(unittest.TestCase):
    def test_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            config = EnvConfig()

        self.assertEqual(config.llm_provider, "ollama")
        self.assertEqual(config.ollama_model, "qwen3:14b")
        self.assertEqual(config.ollama_base_url, "http://localhost:11434")
        self.assertIsNone(config.openai_api_key)
        self.assertEqual(config.openai_model, "gpt-5-nano")
        self.assertEqual(config.lm_studio_model, "local-model")
        self.assertEqual(config.lm_studio_base_url, "http://localhost:1234/v1")
        self.assertIsNone(config.lm_studio_api_key)
        self.assertIsNone(config.logs_file)

    def test_reads_environment_when_created(self):
        values = {
            "LLM_PROVIDER": "openai",
            "OLLAMA_MODEL": "custom-ollama",
            "OLLAMA_BASE_URL": "http://ollama.example/",
            "OPENAI_API_KEY": "env-key",
            "OPENAI_MODEL": "custom-openai",
            "LM_STUDIO_MODEL": "custom-lm-studio",
            "LM_STUDIO_BASE_URL": "http://lm-studio.example/v1/",
            "LM_STUDIO_API_KEY": "lm-key",
            "LOGS_FILE": "/tmp/hermes.log",
        }
        with patch.dict(os.environ, values, clear=True):
            config = EnvConfig()

        self.assertEqual(config.llm_provider, "openai")
        self.assertEqual(config.ollama_model, "custom-ollama")
        self.assertEqual(config.ollama_base_url, "http://ollama.example/")
        self.assertEqual(config.openai_api_key, "env-key")
        self.assertEqual(config.openai_model, "custom-openai")
        self.assertEqual(config.lm_studio_model, "custom-lm-studio")
        self.assertEqual(config.lm_studio_base_url, "http://lm-studio.example/v1/")
        self.assertEqual(config.lm_studio_api_key, "lm-key")
        self.assertEqual(config.logs_file, "/tmp/hermes.log")


class ConfigConsumerTests(unittest.TestCase):
    def test_agent_selects_provider_from_injected_config(self):
        config = EnvConfig(llm_provider="openai", openai_api_key="configured-key")

        with patch("src.llm.providers.OpenAI"):
            agent = Agent(config=config)

        self.assertEqual(agent._provider_name, "openai")

    def test_ollama_provider_uses_injected_config(self):
        config = EnvConfig(ollama_model="test-model", ollama_base_url="http://example/")

        provider = OllamaProvider(config=config)

        self.assertEqual(provider.model, "test-model")
        self.assertEqual(provider.base_url, "http://example")

    def test_provider_arguments_override_injected_config(self):
        config = EnvConfig(ollama_model="configured-model", ollama_base_url="http://configured/")

        provider = OllamaProvider(
            model="explicit-model", base_url="http://explicit/", config=config
        )

        self.assertEqual(provider.model, "explicit-model")
        self.assertEqual(provider.base_url, "http://explicit")

    def test_agent_model_overrides_provider_config(self):
        config = EnvConfig(ollama_model="configured-model")
        agent = Agent(provider="ollama", model="preferred-model", config=config)

        self.assertEqual(agent._provider.model, "preferred-model")

    def test_openai_provider_uses_injected_config(self):
        config = EnvConfig(openai_api_key="configured-key", openai_model="configured-model")

        with patch("src.llm.providers.OpenAI") as openai:
            provider = OpenAIProvider(config=config)

        self.assertEqual(provider.api_key, "configured-key")
        self.assertEqual(provider.model, "configured-model")
        openai.assert_called_once_with(api_key="configured-key")

    def test_agent_selects_lm_studio_from_injected_config(self):
        config = EnvConfig(llm_provider="lm_studio", lm_studio_model="loaded-model")

        with patch("src.llm.providers.OpenAI"):
            agent = Agent(config=config)

        self.assertEqual(agent._provider_name, "lm_studio")
        self.assertEqual(agent._provider.model, "loaded-model")

    def test_lm_studio_provider_uses_injected_config(self):
        config = EnvConfig(
            lm_studio_model="loaded-model",
            lm_studio_base_url="http://localhost:1234/v1/",
            lm_studio_api_key="configured-key",
        )

        with patch("src.llm.providers.OpenAI") as openai:
            provider = LMStudioProvider(config=config)

        self.assertEqual(provider.model, "loaded-model")
        self.assertEqual(provider.base_url, "http://localhost:1234/v1")
        self.assertEqual(provider.api_key, "configured-key")
        openai.assert_called_once_with(
            api_key="configured-key", base_url="http://localhost:1234/v1"
        )

    def test_logger_uses_injected_config(self):
        config = EnvConfig(logs_file="/tmp/configured.log")

        with patch("src.config.logger.setup_logger") as setup_logger:
            get_logger("test", config=config)

        self.assertEqual(setup_logger.call_args.kwargs["file_path"], "/tmp/configured.log")
