from typing import Any, Optional, Protocol
from urllib.parse import urlparse

from src.web.lever import LeverBrowser


class QuestionBrowser(Protocol):
    async def open_and_get_form_html(self) -> str:
        """Return the application form HTML for the configured link."""

    def get_questions_html(self, form_html: str) -> list[str]:
        """Extract question HTML from a form."""


class BrowserFactory:
    """Create the browser implementation appropriate for a job-board link."""

    @staticmethod
    def get_browser(
        link: str, *, headless: bool = True, browser: Any = None
    ) -> Optional[QuestionBrowser]:
        hostname = (urlparse(link).hostname or "").lower().rstrip(".")
        if hostname == "lever.co" or hostname.endswith(".lever.co"):
            if not link.endswith("/apply"):
                link = f"{link}/apply"
            return LeverBrowser(link, headless=headless, browser=browser)
        return None
