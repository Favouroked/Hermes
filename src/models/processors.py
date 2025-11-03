from pydantic import BaseModel

from src.models.agents import AgentAction


class LeverQuestion(BaseModel):
    action: AgentAction
    question_html: str
