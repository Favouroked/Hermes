import os
from typing import AsyncIterator, List, Optional, get_args
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from pyppeteer import launch
from tqdm import tqdm

from src.agents.agent import Agent
from src.config.logger import get_logger
from src.db.model import (
    ApplicationActions,
    JobAnalysis,
    SessionLocal,
    InstalledExtensions,
)
from src.models.processors import Question
from src.models.agents import AgentAction, JobGoogleSearchQuery
from src.processors.utils import clean_url
from src.web.factory import BrowserFactory


class ProcessingCancelled(Exception):
    """Raised when the external processing controller requests cancellation."""


PLATFORM_DOMAINS = {
    "lever": ("lever.co",),
    "greenhouse": ("greenhouse.io",),
    "ashbyhq": ("ashbyhq.com",),
    "myworkdayjobs": ("myworkdayjobs.com",),
    "smartrecruiters": ("smartrecruiters.com",),
    "jobvite": ("jobvite.com",),
}
SUPPORTED_PLATFORMS = set(get_args(JobGoogleSearchQuery.__annotations__["site"]))


class Processor:
    def __init__(self, installation_id: str):
        self._logger = get_logger(__name__)
        self._installation_id = installation_id
        self._headless_mode = True
        self._browser = None
        self._installation_data = self._get_installation_data()
        self._agent = Agent(
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

    async def _get_browser(self):
        launch_options = {
            "headless": self._headless_mode,
            "args": ["--no-sandbox", "--disable-dev-shm-usage"],
            "executablePath": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        }

        if getattr(self, "_browser", None) is None:
            self._browser = await launch(**launch_options)
        return self._browser

    async def close_browser(self):
        """Close the browser owned by this processor, if it was created."""
        if getattr(self, "_browser", None) is not None:
            await self._browser.close()
            self._browser = None

    async def _get_rendered_page_text(self, link: str) -> str:
        """Load a job page and return text after its scripts run."""
        browser = await self._get_browser()
        page = None
        try:
            page = await browser.newPage()
            await page.setUserAgent(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/127.0.0.0 Safari/537.36"
            )
            await page.setViewport({"width": 1366, "height": 768})
            await page.goto(link, waitUntil="networkidle2", timeout=120_000)

            try:
                await page.waitForFunction(
                    """
                    () => {
                        const text = document.body?.innerText || "";
                        return text.trim().length > 0 &&
                               !text.includes("Jump to selected job details\\nLoading");
                    }
                    """,
                    {"timeout": 30_000},
                )
            except Exception:
                self._logger.warning(
                    "Timed out waiting for job details: %s", link
                )

            return await page.evaluate(
                "() => document.body ? document.body.innerText : ''"
            )
        finally:
            if page is not None:
                await page.close()



    async def process_questions(
        self, link: str, page_text: str, stop_event=None
    ) -> AsyncIterator[Question]:
        cleaned_link = clean_url(link)
        browser = await self._get_browser()
        extractor = BrowserFactory.get_browser(
            cleaned_link, headless=self._headless_mode, browser=browser
        )
        if extractor is None:
            self._logger.info(f"No browser available for link: {link}")
            return
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
                yield Question(action=action, question_html=question_html)
            except Exception:
                self._logger.exception(
                    f"Error processing question:\n\n{question_html}.\n"
                )

    @staticmethod
    def _validate_url(url: str) -> bool:
        try:
            parsed = urlparse(url)
            hostname = (parsed.hostname or "").lower().rstrip(".")
            if parsed.scheme != "https" or not parsed.path.strip("/"):
                return False
            return any(
                platform in SUPPORTED_PLATFORMS
                and any(hostname == domain or hostname.endswith(f".{domain}") for domain in domains)
                for platform, domains in PLATFORM_DOMAINS.items()
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

        if not self._validate_url(link):
            raise ValueError(f"Invalid supported job URL format: {link}")

        check_cancelled()
        page_text = await self._get_rendered_page_text(link)
        self._logger.info(f"Page Text: {page_text.strip()}")
        check_cancelled()
        job_info = self._agent.generate_job_info(page_text)
        check_cancelled()
        is_unknown = job_info.title.lower() == "unknown"
        with SessionLocal() as session:
            updates = job_info.model_dump()
            updates["page_text"] = page_text
            if is_unknown:
                updates["is_processing"] = False
                session.query(ApplicationActions).filter(
                    ApplicationActions.job_analysis_id == job_id
                ).delete(synchronize_session=False)
            session.query(JobAnalysis).filter(JobAnalysis.id == job_id).update(updates)
            session.commit()

        if is_unknown:
            return

        questions = [
            answer async for answer in self.process_questions(link, page_text, stop_event)
        ]

        check_cancelled()

        with SessionLocal() as session:
            if len(questions) > 0:
                session.query(ApplicationActions).filter(
                    ApplicationActions.job_analysis_id == job_id
                ).delete(synchronize_session=False)
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
