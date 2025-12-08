import json
import time
from typing import List, Literal, Optional

import requests

from src.config.logger import get_logger
from src.config.prompts import (
    FILLER_AGENT_SYSTEM_PROMPT,
    GOOGLE_SEARCH_PROMPT,
    JOB_ANALYSIS_SYSTEM_PROMPT,
)
from src.models.agents import AgentAction, JobDetails, JobGoogleSearchQuery
from src.models.api import InstallRequest
from pathlib import Path
import os

def use_cached_google_searches(
    env_var: str = "USE_CACHED_GOOGLE_SEARCHES",
    cache_path: Path | None = None,
):
    """
    Decorator for LeverAgent.generate_google_searches that, when the given
    environment variable is set, returns cached results from data/searches_1.json
    instead of calling Ollama.

    The JSON file is expected to contain an array of objects compatible with
    JobGoogleSearchQuery.
    """
    if cache_path is None:
        # src/processors/lever.py -> project root is parents[2]
        default_cache_path = Path(__file__).resolve().parents[2] / "data" / "searches_1.json"
    else:
        default_cache_path = cache_path

    def decorator(func):
        def wrapper(self, *args, **kwargs):
            if os.getenv(env_var):
                # Optional logging if logger is present on self
                logger = getattr(self, "_logger", None)
                if logger:
                    logger.info(
                        "Using cached google searches from %s due to %s being set",
                        default_cache_path,
                        env_var,
                    )

                with default_cache_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)

                return [JobGoogleSearchQuery.model_validate(item) for item in data]

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


class LeverAgent:
    def __init__(self):
        models = ["gpt-oss:20b", "gemma3:12b", "qwen3:14b"]
        self._model_name = models[2]
        self._logger = get_logger(__name__)
        self._log_response = True

    def _call_ollama(self, payload) -> str:
        start_time = time.time()
        self._logger.info("Starting Ollama API request")
        resp = requests.post(
            "http://localhost:11434/api/generate", data=json.dumps(payload), timeout=120
        )
        resp.raise_for_status()
        data = resp.json()
        self._logger.info(
            f"Ollama API request completed in {time.time() - start_time:.2f}s"
        )
        raw = data.get("response", "").strip()
        if self._log_response:
            self._logger.info("--------------- Ollama API response ---------------")
            self._logger.info(raw)
            self._logger.info("---------------------------------------------------")
        return raw

    @use_cached_google_searches()
    def generate_google_searches(
        self, payload: InstallRequest
    ) -> List[JobGoogleSearchQuery]:
        prompt = (
            "Resume text:\n\n"
            f"{payload.resume}\n\n"
            "Preferences:\n\n"
            f"{payload.preferences}\n\n"
        )

        payload = {
            "model": self._model_name,
            "prompt": prompt,
            "system": GOOGLE_SEARCH_PROMPT,
            "format": {
                "type": "array",
                "items": JobGoogleSearchQuery.model_json_schema(mode="serialization"),
            },
            # instruct Ollama to return JSON matching schema
            "stream": False,
            "options": {
                "temperature": 0.0,
            },
        }
        raw = self._call_ollama(payload)
        json_raw = json.loads(raw)
        return [JobGoogleSearchQuery.model_validate(r) for r in json_raw]

    def generate_job_info(self, page_text: str) -> JobDetails:
        prompt = f"Analyze the page below:\n{page_text}"

        payload = {
            "model": self._model_name,
            "prompt": prompt,
            "system": JOB_ANALYSIS_SYSTEM_PROMPT,
            "format": JobDetails.model_json_schema(),  # instruct Ollama to return JSON matching schema
            "stream": False,
            "options": {
                "temperature": 0.0,
            },
        }

        raw = self._call_ollama(payload)
        return JobDetails.model_validate_json(raw)

    def generate_action(
        self, question_html: str, job_description: str, resume: str, preferences: str
    ) -> AgentAction:
        prompt = (
            "Question HTML:\n\n"
            f"{question_html}\n\n"
            "Job Description:\n\n"
            f"{job_description}\n\n"
        )

        system_prompt = FILLER_AGENT_SYSTEM_PROMPT.format(
            resume=resume, preferences=preferences
        )

        payload = {
            "model": self._model_name,
            "prompt": prompt,
            "system": system_prompt,
            "format": AgentAction.model_json_schema(),  # instruct Ollama to return JSON matching schema
            "stream": False,
            "options": {
                "temperature": 0.0,
            },
        }

        raw = self._call_ollama(payload)
        return AgentAction.model_validate_json(raw)
