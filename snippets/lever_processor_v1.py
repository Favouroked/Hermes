from typing import List, Optional

import pyperclip
from sqlalchemy import and_

from src.agents.lever import LeverAgent
from src.config.logger import get_logger
from src.db.model import (ApplicationActions, ApplicationQuestions,
                          JobAnalysis, SessionLocal)
from src.models.processors import LeverQuestion
from src.processors.utils import clean_url
from src.web.lever import LeverAutoBrowser


class LeverQuestionProcessor:
    def __init__(
        self, agent: LeverAgent, limit: Optional[int] = None, show_browser: bool = False
    ):
        self.agent = agent
        self._logger = get_logger(__name__)
        self._limit = limit
        self._headless_mode = not show_browser

    def get_postings(self) -> List[dict]:
        with SessionLocal() as session:
            query = session.query(JobAnalysis).filter(
                and_(
                    JobAnalysis.title.notin_(["unprocessed", "unknown"]),
                    JobAnalysis.is_processed == False,
                    JobAnalysis.link.like(f"%lever%"),
                    JobAnalysis.is_agent_processed == False,
                )
            )
            if self._limit:
                query = query.limit(self._limit)
            records = query.all()
            data_list = [
                {
                    "id": record.id,
                    "link": record.link,
                    "title": record.title,
                    "page_text": record.page_text,
                }
                for record in records
            ]
            return data_list

    @staticmethod
    def save_action(posting_id: int, answer: LeverQuestion):
        action = answer.action
        with SessionLocal() as session:
            record = ApplicationActions(
                job_analysis_id=posting_id,
                question_html=answer.question_html,
                question_text=action.question_text,
                answer_text=action.value,
                action=action.action,
                query_selector=action.query_selector,
            )
            session.add(record)
            session.commit()

    @staticmethod
    def update_posting(posting_id: int):
        with SessionLocal() as session:
            session.query(JobAnalysis).filter(JobAnalysis.id == posting_id).update(
                {"is_agent_processed": True}
            )
            session.commit()

    async def process(self):
        postings = self.get_postings()
        self._logger.info(f"Processing {len(postings)} lever job postings")
        for posting in postings:
            link, page_text = posting["link"], posting["page_text"]
            self._logger.info(f"Title: {posting['title']} | Link: {link}")
            try:
                async for answer in self.process_questions(link, page_text):
                    try:
                        self.save_action(posting["id"], answer)
                    except Exception:
                        self._logger.exception(f"Failed to save question {answer}")
                self.update_posting(posting["id"])
            except Exception as e:
                self._logger.exception(f"Failed to process posting [{link}]")


class LeverAutoApply:
    def __init__(self, limit: Optional[int] = None, show_browser: bool = False):
        self._logger = get_logger(__name__)
        self._limit = limit
        self._headless_mode = not show_browser
        self._show_browser = show_browser

    def _retrieve_job_postings(self) -> List[dict]:
        with SessionLocal() as session:
            subquery = (
                session.query(ApplicationQuestions)
                .filter(ApplicationQuestions.job_analysis_id == JobAnalysis.id)
                .exists()
            )
            query = session.query(JobAnalysis).filter(
                and_(
                    subquery,
                    JobAnalysis.is_processed == False,
                    JobAnalysis.expired == False,
                    JobAnalysis.is_agent_processed == True,
                )
            )
            if self._limit:
                query = query.limit(self._limit)
            records = query.all()
            return [
                {
                    "id": record.id,
                    "link": record.link,
                    "title": record.title,
                    "cover_letter": record.cover_letter,
                }
                for record in records
            ]

    @staticmethod
    def _retrieve_job_questions(job_id: int) -> List[dict]:
        with SessionLocal() as session:
            query = session.query(ApplicationQuestions).filter(
                ApplicationQuestions.job_analysis_id == job_id
            )
            records = query.all()
            return [
                {
                    "id": record.id,
                    "job_analysis_id": record.job_analysis_id,
                    "question_html": record.question_html,
                    "question_text": record.question_text,
                    "answer_text": record.answer_text,
                    "answer_execution_code": record.answer_execution_code,
                    "created_at": record.created_at,
                }
                for record in records
            ]

    @staticmethod
    def _update_job_posting(job_id: int, updates: dict):
        with SessionLocal() as session:
            session.query(JobAnalysis).filter(JobAnalysis.id == job_id).update(updates)
            session.commit()

    async def process(self):
        job_postings = self._retrieve_job_postings()
        self._logger.info(f"Found {len(job_postings)} lever job postings")
        browser = LeverAutoBrowser(show_browser=self._show_browser)
        await browser.create_browser()
        for job_posting in job_postings:
            try:
                questions = self._retrieve_job_questions(job_posting["id"])
                self._logger.info(
                    f"Found {len(questions)} questions for job [{job_posting['id']}]: [{job_posting['title']}]"
                )
                link = job_posting["link"]

                apply_link = clean_url(link)
                if not apply_link.endswith("/apply"):
                    await browser.new_page(apply_link)
                    apply_link = f"{apply_link}/apply"
                pyperclip.copy(job_posting["cover_letter"])
                await browser.auto_apply(apply_link, questions)
                print(
                    "\n-----------------------------------------------------------------------------\n"
                )
                updates: dict = {"is_processed": True}
                cmd = input("Enter command: ")
                if "n" in cmd:
                    notes = input("Enter notes: ")
                    updates["notes"] = notes
                if "r" in cmd:
                    updates["is_processed"] = False
                self._update_job_posting(job_posting["id"], updates)
                print(
                    "\n-----------------------------------------------------------------------------\n"
                )
                if "e" in cmd:
                    break
            except Exception as e:
                self._logger.exception(
                    f"Failed to process posting [{job_posting}]: {e}"
                )
        await browser.close_browser()
