import json
from typing import List, Literal, Optional

import requests

from src.config.prompts import (FILLER_AGENT_SYSTEM_PROMPT,
                                GOOGLE_SEARCH_PROMPT,
                                JOB_ANALYSIS_SYSTEM_PROMPT)
from src.models.agents import AgentAction, JobDetails, JobGoogleSearchQuery
from src.models.api import InstallRequest


class LeverAgent:
    def __init__(self):
        models = ["gpt-oss:20b", "gemma3:12b", "qwen3:14b"]
        self._model_name = models[2]

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
            "format": JobGoogleSearchQuery.model_json_schema(),  # instruct Ollama to return JSON matching schema
            "stream": False,
            "options": {
                "temperature": 0.0,
            },
        }

        resp = requests.post(
            "http://localhost:11434/api/generate", data=json.dumps(payload), timeout=120
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("response", "").strip()
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

        resp = requests.post(
            "http://localhost:11434/api/generate", data=json.dumps(payload), timeout=120
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("response", "").strip()
        return JobDetails.model_validate_json(raw)

    def generate_action(self, question_html: str, job_description: str) -> AgentAction:
        prompt = (
            "Question HTML:\n\n"
            f"{question_html}\n\n"
            "Job Description:\n\n"
            f"{job_description}\n\n"
        )

        payload = {
            "model": self._model_name,
            "prompt": prompt,
            "system": FILLER_AGENT_SYSTEM_PROMPT,
            "format": AgentAction.model_json_schema(),  # instruct Ollama to return JSON matching schema
            "stream": False,
            "options": {
                "temperature": 0.0,
            },
        }

        resp = requests.post(
            "http://localhost:11434/api/generate", data=json.dumps(payload), timeout=120
        )
        resp.raise_for_status()
        data = resp.json()

        # Ollama returns {"response": "<json-string>", ...}
        raw = data.get("response", "").strip()
        return AgentAction.model_validate_json(raw)
