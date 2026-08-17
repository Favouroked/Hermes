import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from src.processors.processor import Processor
from src.web.factory import BrowserFactory
from src.web.lever import LeverBrowser


class BrowserFactoryTests(unittest.TestCase):
    def test_creates_lever_browser_for_lever_links(self):
        browser = BrowserFactory.get_browser(
            "https://jobs.lever.co/company/role/apply", headless=False
        )

        self.assertIsInstance(browser, LeverBrowser)
        self.assertFalse(browser._headless_mode)

    def test_creates_lever_browser_for_lever_subdomains(self):
        browser = BrowserFactory.get_browser("https://sub.jobs.lever.co/company/role")

        self.assertIsInstance(browser, LeverBrowser)

    def test_returns_none_for_unsupported_or_lookalike_links(self):
        links = [
            "https://boards.greenhouse.io/company/jobs/123",
            "https://jobs.lever.co.evil.example/company/role",
            "not a url",
        ]

        for link in links:
            with self.subTest(link=link):
                self.assertIsNone(BrowserFactory.get_browser(link))


class ProcessQuestionsTests(unittest.TestCase):
    def test_unsupported_link_yields_no_questions(self):
        processor = Processor.__new__(Processor)
        processor._headless_mode = True
        processor._logger = Mock()

        async def collect_questions():
            return [
                question
                async for question in processor.process_questions(
                    "https://boards.greenhouse.io/company/jobs/123", "page text"
                )
            ]

        self.assertEqual(asyncio.run(collect_questions()), [])

    @patch("src.processors.processor.BrowserFactory.get_browser")
    def test_uses_browser_selected_by_factory(self, get_browser):
        processor = Processor.__new__(Processor)
        processor._headless_mode = True
        processor._logger = Mock()
        browser = Mock()
        browser.open_and_get_form_html = AsyncMock(return_value="<form></form>")
        browser.get_questions_html.return_value = []
        get_browser.return_value = browser

        async def collect_questions():
            return [
                question
                async for question in processor.process_questions(
                    "https://jobs.lever.co/company/role", "page text"
                )
            ]

        self.assertEqual(asyncio.run(collect_questions()), [])
        get_browser.assert_called_once_with(
            "https://jobs.lever.co/company/role/apply", headless=True
        )
        browser.open_and_get_form_html.assert_awaited_once_with()
        browser.get_questions_html.assert_called_once_with("<form></form>")
