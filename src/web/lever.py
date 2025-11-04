import traceback
from typing import List, Optional

from bs4 import BeautifulSoup
from pyppeteer import launch

from src.config.logger import get_logger


def _get_wrapper(snippet: str):
    return f"""
async def __snippet__(page):
    {snippet}
"""


class LeverAutoBrowser:
    def __init__(self, show_browser: bool = True, debug: bool = False):
        self._headless_mode = not show_browser
        self._debug = debug
        self._executable_path = (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        )
        self._launch_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ]
        self._browser = None
        self._logger = get_logger(__name__)
        self._form_container = {"id": "application-form"}

    async def create_browser(self):
        browser = await launch(
            headless=self._headless_mode,
            args=self._launch_args,
            executablePath=self._executable_path,
        )
        self._browser = browser

    async def close_browser(self):
        if self._browser is not None:
            await self._browser.close()
            self._browser = None

    async def new_page(self, link: str):
        if self._browser is None:
            raise ValueError("Browser is not created")
        page = await self._browser.newPage()
        await self._page_setup(page)
        await page.goto(link, waitUntil="networkidle2", timeout=120_000)
        return page

    async def auto_apply(self, link: str, questions: List[dict]):
        try:
            page = await self.new_page(link)
            form_selector = self._build_selector_from_identifier(self._form_container)
            await page.waitForSelector(form_selector, {"timeout": 60_000})
            self._logger.info(f"Filling form: [{link}]")
            for question in questions:
                question_text = question["question_text"]
                answer_text = question["answer_text"]
                code = question["answer_execution_code"]
                try:
                    await self._run_action_snippet(page, code)
                except Exception as e:
                    self._logger.info(
                        f"Error filling form. Question: {question_text}\nAnswer: {answer_text}\n"
                    )
                    if self._debug:
                        self._logger.exception(e)
            resume_input = await page.querySelector("#resume-upload-input")
            await resume_input.uploadFile("data/resume.pdf")
            self._logger.info(f"Done filling form: [{link}]")
        except Exception as e:
            self._logger.exception(e)

    @staticmethod
    async def _page_setup(page):
        await page.setUserAgent(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/127.0.0.0 Safari/537.36"
        )
        await page.setViewport(
            {
                "width": 1366,
                "height": 768,
                "deviceScaleFactor": 1,
                "hasTouch": False,
                "isMobile": False,
            }
        )

        # Preload evasions before any page scripts run
        await page.evaluateOnNewDocument(
            """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
                Object.defineProperty(navigator, 'platform', {get: () => 'MacIntel'});
                Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4]});
                const origQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (p) => (
                  p && p.name === 'notifications'
                    ? Promise.resolve({ state: 'default' })
                    : origQuery(p)
                );
            """
        )

        await page.setExtraHTTPHeaders(
            {
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    @staticmethod
    async def _run_action_snippet(page, snippet):
        wrapper = _get_wrapper(snippet)
        ns = {}
        exec(wrapper, ns, ns)
        return await ns["__snippet__"](page)

    def _build_selector_from_identifier(self, identifier: dict) -> Optional[str]:
        """
        Build a CSS selector string from the question identifier config.
        Accepts keys: 'selector' (raw), 'id', 'class', or 'tag'.
        """
        if not identifier:
            return None  # very loose fallback
        if identifier.get("selector"):
            return identifier["selector"]
        selector_parts = []
        if identifier.get("tag"):
            selector_parts.append(identifier["tag"])
        if identifier.get("id"):
            selector_parts.append(f'#{identifier["id"]}')
        if identifier.get("class"):
            cls = identifier["class"].strip()
            class_selector = cls if cls.startswith(".") else "." + ".".join(cls.split())
            selector_parts.append(class_selector)

        return "".join(selector_parts) if selector_parts else None


class LeverBrowser(LeverAutoBrowser):
    def __init__(self, link: str, headless: bool = True, debug: bool = False):
        super().__init__(not headless, debug)
        self._logger = get_logger(__name__)
        self._link = link
        self._headless_mode = headless
        self._apply_btn_class = {"class": ".postings-btn template-btn-submit hex-color"}
        self._form_submit_btn = {
            "id": "btn-submit",
            "class": ".postings-btn template-btn-submit hex-color",
        }
        self._form_question_identifier = {"class": "application-question", "tag": "li"}
        self._form_additional_information_identifier = {
            "class": "application-additional"
        }

    async def open_and_get_form_html(self) -> str:
        """
        Open the posting link with pyppeteer and return the innerHTML of the form container.
        """
        browser_created = False
        if self._browser is None:
            await self.create_browser()
            browser_created = True
        try:
            page = await self._browser.newPage()
            await self._page_setup(page)
            await page.goto(self._link, waitUntil="networkidle2", timeout=120_000)

            selector = self._build_selector_from_identifier(self._form_container)
            self._logger.info(f"Waiting for form {selector}")
            await page.waitForSelector(selector, {"timeout": 60_000})
            element = await page.querySelector(selector)
            if not element:
                raise RuntimeError(
                    f"Form container not found with selector: {selector}"
                )

            inner_html: str = await page.evaluate("(el) => el.innerHTML", element)
            return inner_html
        finally:
            if browser_created:
                await self.close_browser()

    def get_questions_html(self, form_html: str) -> List[str]:
        """Extract question HTML elements using BeautifulSoup."""
        question_selector = self._build_selector_from_identifier(
            self._form_question_identifier
        )
        soup = BeautifulSoup(form_html, "html.parser")

        questions = []
        if question_selector:
            elements = soup.select(question_selector)
            questions = [
                str(element)
                for element in elements
                if "resume" not in element.get("class")
            ]

        additional_info_selector = self._build_selector_from_identifier(
            self._form_additional_information_identifier
        )
        additional_elements = soup.select(additional_info_selector)
        additional_questions = [str(elem) for elem in additional_elements]
        questions.extend(additional_questions)

        return questions
