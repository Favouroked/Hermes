from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


class JobGoogleSearchQuery(BaseModel):
    """
    Represents a structured query for searching job listings via Google search.

    Contains parameters to build and track Google search queries targeting specific job boards,
    with filters and role specifications. Used to generate targeted search URLs for job scraping.

    Attributes:
        site: The job board platform to target (currently supports 'lever')
        role_focus: The job title or role description to search for
        filters: Dictionary of filter options to apply to the search
        query: The constructed Google search query string
        google_search_url: The complete, encoded URL for the Google search
    """

    site: Literal["lever"] = Field(..., description="Target job board/site")
    role_focus: str = Field(..., description="Role title/focus description")
    filters: dict = Field(..., description="Filter options")
    query: str = Field(..., description="Raw Google search query string")
    google_search_url: str = Field(..., description="Fully encoded Google search URL")


Unknown = Literal["unknown"]


class JobDetails(BaseModel):
    title: Union[str | Unknown] = Field(
        ...,
        description="Exact job title as written in the posting. Use 'unknown' only if the title truly cannot be determined.",
    )
    location: Optional[str | Unknown] = Field(
        default=None,
        description="City/region or remote/hybrid designation (e.g., 'San Francisco, CA', 'Remote'). Use 'unknown' if absent; use null only if location is irrelevant.",
    )
    company: Union[str | Unknown] = Field(
        default=None,
        description="Legal or brand name of the hiring company as shown on the page. Use 'unknown' if not provided.",
    )
    salary: Union[str | Unknown] = Field(
        default=None,
        description="Compensation string exactly as shown (e.g., '$150k–$180k base + equity', '£80,000-£95,000'). Use 'unknown' if no salary information is present.",
    )
    description: Union[str | Unknown] = Field(
        default=None,
        description="Cleaned full-text job description. Preserve essential content but remove obvious boilerplate if possible. Use 'unknown' if the description is missing.",
    )


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
