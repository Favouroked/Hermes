import os
import time
from typing import Any, Mapping, Protocol

import requests
from openai import OpenAI

from src.config.logger import get_logger


class LLMProvider(Protocol):
    def generate(
        self, *, system_prompt: str, user_prompt: str, schema: Mapping[str, Any], schema_name: str
    ) -> str: ...


class OllamaProvider:
    def __init__(self, model: str | None = None, base_url: str | None = None):
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen3:14b")
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self._logger = get_logger(__name__)

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
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI provider requires an installation key or OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._client = OpenAI(api_key=self.api_key)
        self._logger = get_logger(__name__)

    def generate(self, *, system_prompt, user_prompt, schema, schema_name) -> str:
        start_time = time.time()
        self._logger.info("Starting OpenAI API request with model %s", self.model)
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
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
