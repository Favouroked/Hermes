from typing import AsyncIterator, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from src.agents.lever import AgentAction, LeverAgent
from src.config.logger import get_logger
from src.db.model import (
    ApplicationActions,
    JobAnalysis,
    SessionLocal,
    InstalledExtensions,
)
from src.models.processors import LeverQuestion
from src.processors.utils import clean_url
from src.web.lever import LeverBrowser


class ProcessingCancelled(Exception):
    """Raised when the external processing controller requests cancellation."""


class LeverProcessor:
    def __init__(self, installation_id: str):
        self._logger = get_logger(__name__)
        self._installation_id = installation_id
        self._headless_mode = True
        self._installation_data = self._get_installation_data()
        self._agent = LeverAgent(
            provider=self._installation_data["llm_provider"],
            openai_key=self._installation_data["openai_key"],
        )

    def _get_installation_data(self):
        with SessionLocal() as session:
            record = (
                session.query(InstalledExtensions)
                .filter(InstalledExtensions.installation_id == self._installation_id)
                .one_or_none()
            )
            if not record:
                raise ValueError(f"{self._installation_id} not found in database")
            return {
                "installation_id": record.installation_id,
                "resume": record.resume,
                "preferences": record.preferences,
                "openai_key": record.openai_key,
                "llm_provider": record.llm_provider or "ollama",
            }



    async def process_questions(
        self, link: str, page_text: str, stop_event=None
    ) -> AsyncIterator[LeverQuestion]:
        apply_link = clean_url(link)
        if not apply_link.endswith("/apply"):
            apply_link = f"{apply_link}/apply"
        extractor = LeverBrowser(apply_link, headless=self._headless_mode)
        form_html = await extractor.open_and_get_form_html()
        questions_html = extractor.get_questions_html(form_html)
        self._logger.info(f"Found {len(questions_html)} questions")
        for question_html in tqdm(questions_html):
            if stop_event is not None and stop_event.is_set():
                raise ProcessingCancelled()
            try:
                resume, preferences = (
                    self._installation_data["resume"],
                    self._installation_data["preferences"],
                )
                action = self._agent.generate_action(
                    question_html, page_text, resume, preferences
                )
                yield LeverQuestion(action=action, question_html=question_html)
            except Exception:
                self._logger.exception(
                    f"Error processing question:\n\n{question_html}.\n"
                )

    def _validate_lever_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            parts = parsed.path.strip("/").split("/")
            return (
                parsed.scheme == "https"
                and "lever.co" in parsed.netloc
                and len(parts) >= 2
            )
        except Exception:
            return False

    async def process_job(self, job_data: dict, stop_event=None):
        def check_cancelled():
            if stop_event is not None and stop_event.is_set():
                raise ProcessingCancelled()

        check_cancelled()
        link = job_data["link"]
        job_id = job_data["id"]
        if link.endswith("/apply"):
            link = link[:-6]

        if not self._validate_lever_url(link):
            raise ValueError(f"Invalid Lever job URL format: {link}")

        r = requests.get(link)

        r.raise_for_status()

        check_cancelled()
        soup = BeautifulSoup(r.text, "html.parser")
        page_text = soup.get_text()
        job_info = self._agent.generate_job_info(page_text)
        check_cancelled()
        is_unknown = job_info.title.lower() == "unknown"
        with SessionLocal() as session:
            updates = job_info.model_dump()
            if is_unknown:
                updates["is_processing"] = False
            session.query(JobAnalysis).filter(JobAnalysis.id == job_id).update(updates)
            session.commit()

        if is_unknown:
            return

        questions = [
            answer async for answer in self.process_questions(link, page_text, stop_event)
        ]

        check_cancelled()

        with SessionLocal() as session:
            db_actions = [
                ApplicationActions(
                    job_analysis_id=job_id,
                    question_html=question.question_html,
                    question_text=question.action.question_text,
                    answer_text=question.action.value,
                    action=question.action.action,
                    query_selector=question.action.query_selector,
                )
                for question in questions
            ]
            session.add_all(db_actions)
            session.commit()

            session.query(JobAnalysis).filter(JobAnalysis.id == job_id).update(
                {"is_processing": False}
            )
            session.commit()
