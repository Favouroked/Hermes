import atexit
import os
import signal
from concurrent.futures import Future, ProcessPoolExecutor
from typing import Dict
from uuid import uuid4

from flask import Flask, jsonify, request
from flask_cors import CORS

from src.agents.lever import LeverAgent
from src.config.logger import get_logger
from src.db.model import (
    ApplicationActions,
    JobAnalysis,
    JobGoogleSearchQuery,
    SessionLocal,
    InstalledExtensions,
)
from src.jobs.lever import execute as trigger_jobs_processing
from src.models.api import (
    Action,
    ExtensionRequest,
    InstallRequest,
    ListingsRequest,
    StatusRequest,
    UrlsRequest,
)
from src.processors.utils import clean_url
from dotenv import load_dotenv

load_dotenv('.env')

logger = get_logger(__name__)

EXECUTOR = ProcessPoolExecutor(max_workers=2)
JOBS: Dict[str, Future] = {}

app = Flask(__name__)
CORS(app)


@app.route("/", methods=["GET"])
def index():
    return jsonify(
        {
            "online": True,
        }
    )


@app.route("/api/install", methods=["POST"])
def install():
    """
    Receives installation_id, resume, and preferences from the extension.
    Returns a list of Google search URLs to scrape for job listings.
    """
    installation_data = InstallRequest.model_validate(request.get_json())
    logger.info(f"Install request from: {installation_data.installation_id}")

    with SessionLocal() as session:
        record = (
            session.query(InstalledExtensions)
            .filter(
                InstalledExtensions.installation_id == installation_data.installation_id
            )
            .one_or_none()
        )
        if record is None:
            new_extension = InstalledExtensions(
                installation_id=installation_data.installation_id,
                resume=installation_data.resume,
                preferences=installation_data.preferences,
                openai_key=installation_data.openai_key,
            )
            session.add(new_extension)
            session.commit()

    agent = LeverAgent()

    search_data = agent.generate_google_searches(installation_data)

    with SessionLocal() as session:
        records = [
            JobGoogleSearchQuery(
                installation_id=installation_data.installation_id,
                site=data.site,
                role_focus=data.role_focus,
                filters=data.filters,
                query=data.query,
                google_search_url=data.google_search_url,
            )
            for data in search_data
        ]
        session.add_all(records)
        session.commit()

        return jsonify({"urls": [record.google_search_url for record in records]})


@app.route("/api/listings", methods=["POST"])
def listings():
    """
    Receives installation_id and links extracted from a Google search page.
    Stores the links for processing.
    """
    data = ListingsRequest.model_validate(request.get_json())
    logger.info(
        f"Received {len(data.links)} links from installation: {data.installation_id}"
    )
    _extracted_links = [clean_url(link) for link in data.links]
    extracted_links = []
    for link in _extracted_links:
        if "lever.co" not in link:
            continue
        if link.endswith("/apply"):
            link = link[:-6]
        extracted_links.append(link)
    logger.info(extracted_links)

    with SessionLocal() as session:
        existing_links = [
            record.link
            for record in session.query(JobAnalysis)
            .filter(
                JobAnalysis.installation_id == data.installation_id,
                JobAnalysis.link.in_(extracted_links),
            )
            .all()
        ]
        records = [
            JobAnalysis(
                link=link,
                title="processing...",
                expired=False,
                installation_id=data.installation_id,
                is_processing=True,
            )
            for link in extracted_links
            if link not in existing_links
        ]
        logger.info(f"Found {len(records)} new lever analysis")
        session.add_all(records)
        session.commit()

    job_id = str(uuid4())
    future = EXECUTOR.submit(trigger_jobs_processing, data.installation_id)
    JOBS[job_id] = future  # not really necessary

    return jsonify({"status": "success", "links_received": len(data.links)})


@app.route("/api/status", methods=["POST"])
def status():
    """
    Checks if jobs are ready for the given installation_id.
    Returns 200 if jobs are ready, 202 if still processing.
    """
    data = StatusRequest.model_validate(request.get_json())
    logger.info(f"Status check from installation: {data.installation_id}")

    with SessionLocal() as session:
        processing_jobs = (
            session.query(JobAnalysis)
            .filter(
                JobAnalysis.installation_id == data.installation_id,
                JobAnalysis.is_processing == True,
            )
            .all()
        )
        if len(processing_jobs) == 0:
            job_count = (
                session.query(JobAnalysis)
                .filter(
                    JobAnalysis.installation_id == data.installation_id,
                    JobAnalysis.is_processed == False,
                    JobAnalysis.has_error == False,
                )
                .count()
            )
            if job_count == 0:
                # check google searches
                google_data_records = (
                    session.query(JobGoogleSearchQuery)
                    .filter(
                        JobGoogleSearchQuery.installation_id == data.installation_id
                    )
                    .all()
                )
                if len(google_data_records) == 0:
                    return jsonify({"status": "none"}), 200
                return jsonify(
                    {
                        "status": "google",
                        "urls": [
                            record.google_search_url for record in google_data_records
                        ],
                    }
                )
            logger.info(f"Jobs are ready for installation: {data.installation_id}")
            return jsonify({"status": "ready", "job_count": job_count}), 200
        else:
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

    with SessionLocal() as session:
        records = (
            session.query(JobAnalysis)
            .filter(
                JobAnalysis.installation_id == data.installation_id,
                JobAnalysis.is_processed == False,
                JobAnalysis.has_error == False,
            )
            .all()
        )
        job_urls = [record.link for record in records]
        formatted_urls = []
        for url in job_urls:
            if not url.endswith("/apply"):
                url = url + "/apply"
            formatted_urls.append(url)

        logger.info(
            f"Returning {len(job_urls)} URLs for installation: {data.installation_id}"
        )
        return jsonify({"urls": formatted_urls})


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


def shutdown_pool_immediately():
    # Try to cancel futures that haven't started, and stop accepting new tasks
    # wait=False => return immediately; running tasks will be terminated by process exit
    try:
        EXECUTOR.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass


def handle_sigterm(signum, frame):
    shutdown_pool_immediately()
    # Exit process quickly after signaling shutdown
    os._exit(0)


signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)

# Fallback at-exit hook (e.g., when interpreter exits normally)
atexit.register(shutdown_pool_immediately)

if __name__ == "__main__":
    app.run(port=8080)
