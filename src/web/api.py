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
    installation_id: str


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


class StatusRequest(BaseModel):
    installation_id: str


class UrlsRequest(BaseModel):
    installation_id: str


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


@app.route("/api/status", methods=["POST"])
def status():
    """
    Checks if jobs are ready for the given installation_id.
    Returns 200 if jobs are ready, 202 if still processing.
    """
    data = StatusRequest.model_validate(request.get_json())
    logger.info(f"Status check from installation: {data.installation_id}")
    
    # TODO: Check database for processed jobs for this installation_id
    # For now, simulate that jobs are ready after some time
    # In a real implementation, this would query the database to check
    # if job analysis and application actions are ready
    
    with SessionLocal() as session:
        # Check if there are any job postings with application actions
        job_count = session.query(JobAnalysis).count()
        
        if job_count > 0:
            # Jobs are ready
            logger.info(f"Jobs are ready for installation: {data.installation_id}")
            return jsonify({"status": "ready", "job_count": job_count}), 200
        else:
            # Still processing
            logger.info(f"Jobs not ready yet for installation: {data.installation_id}")
            return jsonify({"status": "processing"}), 202


@app.route("/api/urls", methods=["POST"])
def urls():
    """
    Returns a list of job application URLs for the given installation_id.
    These are the URLs that the user should visit to apply for jobs.
    """
    data = UrlsRequest.model_validate(request.get_json())
    logger.info(f"URLs request from installation: {data.installation_id}")
    
    # TODO: Retrieve job URLs from database for this installation_id
    # For now, return example URLs
    # In a real implementation, this would query JobAnalysis table
    # and return the application URLs for jobs matching the user's preferences
    
    with SessionLocal() as session:
        jobs = session.query(JobAnalysis).limit(10).all()
        job_urls = [job.link for job in jobs if job.link]
        
        logger.info(f"Returning {len(job_urls)} URLs for installation: {data.installation_id}")
        return jsonify({"urls": job_urls})


if __name__ == "__main__":
    app.run(port=8080)
