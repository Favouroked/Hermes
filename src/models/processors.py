from pydantic import BaseModel

from src.models.agents import AgentAction


class Question(BaseModel):
    action: AgentAction
    question_html: str
