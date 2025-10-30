from typing import Literal, Optional

from flask import Flask, jsonify, request
from flask_cors import CORS
from pydantic import BaseModel

from src.config.logger import get_logger
from src.db.model import SessionLocal, JobAnalysis, ApplicationActions
from src.processors.utils import clean_url

logger = get_logger(__name__)


class ExtensionRequest(BaseModel):
    url: str
    html: str
    timestamp: str


class Action(BaseModel):
    action: Literal["type", "click", "select", "alert"]
    query_selector: Optional[str]
    value: Optional[str]


class InstallRequest(BaseModel):
    installation_id: str
    resume: str
    preferences: str


class ListingsRequest(BaseModel):
    installation_id: str
    links: list[str]


app = Flask(__name__)
CORS(app)


@app.route("/", methods=["GET"])
def index():
    return jsonify(
        {
            "online": True,
        }
    )


@app.route("/api/filler", methods=["POST"])
def analyze_page():
    data = ExtensionRequest.model_validate(request.get_json())
    logger.info(f"Extension data: {data.model_dump(exclude={'html'})}")
    link = clean_url(data.url)
    if link.endswith("/apply"):
        link = link[:-6]  # remove '/apply'

    with SessionLocal() as session:
        matched_job_postings = (
            session.query(JobAnalysis)
            .filter(
                JobAnalysis.link.like(f"%{link}%"),
            )
            .all()
        )
        logger.info(f"Found {len(matched_job_postings)} postings")
        job_posting = matched_job_postings[0]
        db_actions = (
            session.query(ApplicationActions)
            .filter(ApplicationActions.job_analysis_id == job_posting.id)
            .all()
        )
        logger.info(f"Found {len(db_actions)} actions")
        actions = [
            Action.model_validate(
                {
                    "action": action.action,
                    "query_selector": action.query_selector,
                    "value": action.answer_text,
                }
            )
            for action in db_actions
        ]

    return jsonify([action.model_dump(mode="json") for action in actions])


@app.route("/api/install", methods=["POST"])
def install():
    """
    Receives installation_id, resume, and preferences from the extension.
    Returns a list of Google search URLs to scrape for job listings.
    """
    data = InstallRequest.model_validate(request.get_json())
    logger.info(f"Install request from: {data.installation_id}")
    
    # TODO: Generate Google search queries based on resume and preferences
    # For now, return some example Google job search URLs
    # In a real implementation, this would use an LLM to generate relevant queries
    
    # Example URLs based on common job search patterns
    search_urls = [
        "https://www.google.com/search?q=software+engineer+jobs+remote",
        "https://www.google.com/search?q=python+developer+jobs",
        "https://www.google.com/search?q=full+stack+engineer+openings"
    ]
    
    return jsonify({"urls": search_urls})


@app.route("/api/listings", methods=["POST"])
def listings():
    """
    Receives installation_id and links extracted from a Google search page.
    Stores the links for processing.
    """
    data = ListingsRequest.model_validate(request.get_json())
    logger.info(f"Received {len(data.links)} links from installation: {data.installation_id}")
    
    # TODO: Store links in database for processing
    # For now, just log them
    for link in data.links:
        logger.info(f"  - {link}")
    
    return jsonify({"status": "success", "links_received": len(data.links)})


if __name__ == "__main__":
    app.run(port=8080)
