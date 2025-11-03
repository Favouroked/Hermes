from pydantic import BaseModel
from typing import Optional, Literal


class ExtensionRequest(BaseModel):
    url: str
    html: str
    timestamp: str
    installation_id: str


class Action(BaseModel):
    action: Literal["type", "click", "select", "alert"]
    query_selector: Optional[str]
    value: Optional[str]


class InstallRequest(BaseModel):
    installation_id: str
    resume: str
    preferences: str
    openai_key: Optional[str] = None


class ListingsRequest(BaseModel):
    installation_id: str
    links: list[str]


class StatusRequest(BaseModel):
    installation_id: str


class UrlsRequest(BaseModel):
    installation_id: str
