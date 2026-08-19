import time
from typing import Any, Mapping, Protocol

import requests
from openai import OpenAI

from src.config.logger import get_logger
from src.config.env import EnvConfig


class LLMProvider(Protocol):
    def generate(
        self, *, system_prompt: str, user_prompt: str, schema: Mapping[str, Any], schema_name: str
    ) -> str: ...


class OllamaProvider:
    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        config: EnvConfig | None = None,
    ):
        config = config or EnvConfig()
        self.model = model or config.ollama_model
        self.base_url = (base_url or config.ollama_base_url).rstrip("/")
        self._logger = get_logger(__name__, config=config)

    def generate(self, *, system_prompt, user_prompt, schema, schema_name) -> str:
        start_time = time.time()
        payload = {
            "model": self.model,
            "prompt": user_prompt,
            "system": system_prompt,
            "format": schema,
            "stream": False,
            "options": {"temperature": 0.0},
        }
        self._logger.info("Starting Ollama API request")
        response = requests.post(
            f"{self.base_url}/api/generate", json=payload, timeout=120
        )
        response.raise_for_status()
        raw = response.json().get("response", "").strip()
        self._logger.info("Ollama API request completed in %.2fs", time.time() - start_time)
        self._logger.info("--------------- Ollama API response ---------------")
        self._logger.info(raw)
        self._logger.info("---------------------------------------------------")
        return raw


class OpenAIProvider:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        config: EnvConfig | None = None,
    ):
        config = config or EnvConfig()
        self.api_key = api_key or config.openai_api_key
        if not self.api_key:
            raise ValueError("OpenAI provider requires an installation key or OPENAI_API_KEY")
        self.model = model or config.openai_model
        self._client = OpenAI(api_key=self.api_key)
        self._logger = get_logger(__name__, config=config)

    def generate(self, *, system_prompt, user_prompt, schema, schema_name) -> str:
        start_time = time.time()
        self._logger.info("Starting OpenAI API request with model %s", self.model)
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": False,
                    "schema": schema,
                },
            },
        )
        raw = (response.choices[0].message.content or "").strip()
        self._logger.info("OpenAI API request completed in %.2fs", time.time() - start_time)
        self._logger.info("--------------- OpenAI API response ---------------")
        self._logger.info(raw)
        self._logger.info("---------------------------------------------------")
        return raw


class LMStudioProvider:
    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        config: EnvConfig | None = None,
    ):
        config = config or EnvConfig()
        self.model = model or config.lm_studio_model
        self.base_url = (base_url or config.lm_studio_base_url).rstrip("/")
        self.api_key = api_key or config.lm_studio_api_key or "lm-studio"
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self._logger = get_logger(__name__, config=config)

    def generate(self, *, system_prompt, user_prompt, schema, schema_name) -> str:
        start_time = time.time()
        self._logger.info("Starting LM Studio API request with model %s", self.model)
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": False,
                    "schema": schema,
                },
            },
        )
        raw = (response.choices[0].message.content or "").strip()
        self._logger.info("LM Studio API request completed in %.2fs", time.time() - start_time)
        self._logger.info("--------------- LM Studio API response ---------------")
        self._logger.info(raw)
        self._logger.info("---------------------------------------------------")
        return raw
