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
        processor._browser = Mock()
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
            "https://jobs.lever.co/company/role/apply",
            headless=True,
            browser=processor._browser,
        )
        browser.open_and_get_form_html.assert_awaited_once_with()
        browser.get_questions_html.assert_called_once_with("<form></form>")


class RenderedPageTests(unittest.TestCase):
    @patch("src.processors.processor.launch")
    def test_get_rendered_page_text_uses_body_inner_text_and_keeps_browser_open(self, launch_browser):
        browser = Mock()
        page = Mock()
        browser.newPage = AsyncMock(return_value=page)
        page.evaluate = AsyncMock(return_value="Rendered job description")
        page.setUserAgent = AsyncMock()
        page.setViewport = AsyncMock()
        page.goto = AsyncMock()
        page.close = AsyncMock()
        browser.close = AsyncMock()
        launch_browser.return_value = browser

        processor = Processor.__new__(Processor)
        processor._headless_mode = True

        async def load_text():
            return await processor._get_rendered_page_text(
                "https://boards.greenhouse.io/company/jobs/123"
            )

        self.assertEqual(asyncio.run(load_text()), "Rendered job description")
        page.goto.assert_awaited_once_with(
            "https://boards.greenhouse.io/company/jobs/123",
            waitUntil="networkidle2",
            timeout=120_000,
        )
        page.evaluate.assert_awaited_once_with(
            "() => document.body ? document.body.innerText : ''"
        )
        page.close.assert_awaited_once_with()
        browser.close.assert_not_awaited()

    @patch("src.processors.processor.launch")
    def test_reuses_browser_until_explicitly_closed(self, launch_browser):
        browser = Mock()
        first_page = Mock()
        second_page = Mock()
        browser.newPage = AsyncMock(side_effect=[first_page, second_page])
        browser.close = AsyncMock()
        for page in (first_page, second_page):
            page.evaluate = AsyncMock(return_value="Rendered job description")
            page.setUserAgent = AsyncMock()
            page.setViewport = AsyncMock()
            page.goto = AsyncMock()
            page.close = AsyncMock()
        launch_browser.return_value = browser

        processor = Processor.__new__(Processor)
        processor._headless_mode = True
        processor._browser = None

        async def load_twice_and_close():
            await processor._get_rendered_page_text("https://example.com/jobs/one")
            await processor._get_rendered_page_text("https://example.com/jobs/two")
            await processor.close_browser()

        asyncio.run(load_twice_and_close())
        launch_browser.assert_awaited_once()
        first_page.close.assert_awaited_once_with()
        second_page.close.assert_awaited_once_with()
        browser.close.assert_awaited_once_with()
