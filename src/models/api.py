from typing import Literal, Optional

from pydantic import BaseModel


class ExtensionRequest(BaseModel):
    url: str
    html: str
    timestamp: str
    installation_id: str


class GoogleSearchRequest(BaseModel):
    installation_id: str
    cutoff_date: str
    force_generate: bool = False


class GoogleResultsRequest(BaseModel):
    installation_id: str
    search_run_id: str
    links: list[str]


class LinksRequest(BaseModel):
    installation_id: str
    max_links: int = 20
    with_actions: bool = False


class LinkNotesRequest(BaseModel):
    installation_id: str
    notes: str = ""


class ManualFillRequest(BaseModel):
    installation_id: str
    url: str


class SettingsRequest(BaseModel):
    installation_id: str
    llm_provider: Literal["ollama", "openai"]
    openai_key: Optional[str] = None
    auto_fill: bool = False
    resume: str = ""
    preferences: str = ""


class Action(BaseModel):
    action: Literal["type", "click", "select", "alert"]
    query_selector: Optional[str]
    value: Optional[str]


class InstallRequest(BaseModel):
    installation_id: str
    resume: str
    preferences: str
    openai_key: Optional[str] = None
    llm_provider: Literal["ollama", "openai"] = "ollama"
    cutoff_date: Optional[str] = None


class ListingsRequest(BaseModel):
    installation_id: str
    links: list[str]


class StatusRequest(BaseModel):
    installation_id: str


class UrlsRequest(BaseModel):
    installation_id: str
