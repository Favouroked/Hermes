import json
from typing import Literal, Optional

import requests
from pydantic import BaseModel, Field

from src.config.prompts import FILLER_AGENT_SYSTEM_PROMPT


class AgentAction(BaseModel):
    """Action that can be performed on the page to answer the question."""

    action: Literal["type", "click", "select"] = Field(
        description="The type of action to perform on the browser to answer the question."
    )
    question_text: str = Field(description="The question the Agent answered")
    query_selector: str = Field(
        description="The query selector to select the answer field."
    )
    value: Optional[str] = Field(
        default=None,
        description="The answer value. This is not required for 'click' actions.",
    )


class LeverAgent:
    def __init__(self):
        models = ["gpt-oss:20b", "gemma3:12b", "qwen3:14b"]
        self._model_name = models[2]

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
