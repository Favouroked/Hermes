import json
from typing import List

from src.config.env import EnvConfig
from src.config.logger import get_logger
from src.config.prompts import (
    FILLER_AGENT_SYSTEM_PROMPT,
    GOOGLE_SEARCH_PROMPT,
    JOB_ANALYSIS_SYSTEM_PROMPT,
    COVER_LETTER_SYSTEM_PROMPT,
)
from src.llm.providers import LLMProvider, OpenAIProvider, OllamaProvider
from src.models.agents import AgentAction, AgentActions, JobDetails, JobGoogleSearchQuery
from src.models.api import InstallRequest
from pydantic import BaseModel, Field


class SearchQueries(BaseModel):
    items: List[JobGoogleSearchQuery] = Field(..., description="Generated job searches")


class CoverLetter(BaseModel):
    cover_letter: str = Field(..., description="The finished cover letter")


class Agent:
    def __init__(
        self,
        provider: str | None = None,
        openai_key: str | None = None,
        config: EnvConfig | None = None,
    ):
        config = config or EnvConfig()
        provider = (provider or config.llm_provider).lower()
        if provider == "ollama":
            self._provider: LLMProvider = OllamaProvider(config=config)
        elif provider == "openai":
            self._provider = OpenAIProvider(api_key=openai_key, config=config)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
        self._provider_name = provider
        self._logger = get_logger(__name__, config=config)

    def _generate(self, system_prompt: str, user_prompt: str, model: type[BaseModel]) -> str:
        return self._provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=model.model_json_schema(mode="serialization"),
            schema_name=model.__name__.lower(),
        )

    def generate_google_searches(self, payload: InstallRequest) -> List[JobGoogleSearchQuery]:
        prompt = (
            "Resume text:\n\n"
            f"{payload.resume}\n\n"
            "Preferences:\n\n"
            f"{payload.preferences}\n\n"
        )
        model = SearchQueries if self._provider_name == "openai" else JobGoogleSearchQuery
        raw = self._generate(GOOGLE_SEARCH_PROMPT, prompt, model)
        parsed = json.loads(raw)
        if self._provider_name == "openai":
            return SearchQueries.model_validate(parsed).items
        return [JobGoogleSearchQuery.model_validate(item) for item in parsed]

    def generate_job_info(self, page_text: str) -> JobDetails:
        raw = self._generate(
            JOB_ANALYSIS_SYSTEM_PROMPT,
            f"Analyze the page below:\n{page_text}",
            JobDetails,
        )
        return JobDetails.model_validate_json(raw)

    def generate_cover_letter(self, page_text: str, resume: str) -> str:
        raw = self._generate(
            COVER_LETTER_SYSTEM_PROMPT,
            f"Candidate resume:\n\n{resume}\n\nJob page text:\n\n{page_text}",
            CoverLetter,
        )
        return CoverLetter.model_validate_json(raw).cover_letter.strip()

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
        raw = self._generate(system_prompt, prompt, AgentAction)
        return AgentAction.model_validate_json(raw)

    def generate_actions(self, page_html: str, context: str = "") -> List[AgentAction]:
        prompt = (
            "Page HTML:\n\n" + page_html + "\n\n"
            "Additional user context:\n\n" + context
        )
        system = (
            "Return the form-filling actions needed for this page as JSON. "
            "Return an object with an items array. Each item must contain action "
            "(type, click, or select), query_selector, question_text, and value when needed. "
            "Return an empty items array when no actions are appropriate."
        )
        raw = self._generate(system, prompt, AgentActions)
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [AgentAction.model_validate(item) for item in parsed]
        return AgentActions.model_validate(parsed).items
