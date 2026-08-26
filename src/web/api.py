import atexit
import os
import re
import signal
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from uuid import uuid4
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from src.agents.agent import Agent
from src.config.logger import get_logger
from src.db.model import (
    ApplicationActions,
    JobAnalysis,
    JobGoogleSearchQuery,
    SearchRun,
    ProcessingRun,
    SessionLocal,
    InstalledExtensions,
)
from src.jobs.job import execute as trigger_jobs_processing
from src.models.api import (
    Action, ExtensionRequest, GoogleResultsRequest, GoogleSearchRequest,
    InstallRequest, LinkNotesRequest, LinksRequest, ManualFillRequest,
    SettingsRequest,
)
from src.processors.utils import clean_url

load_dotenv(".env")
logger = get_logger(__name__)
EXECUTOR = ThreadPoolExecutor(max_workers=2)
PROCESSING_RUNS = {}
PROCESSING_RUNS_LOCK = threading.Lock()
app = Flask(__name__)
CORS(app)


def _installation(installation_id: str):
    with SessionLocal() as session:
        return session.query(InstalledExtensions).filter_by(installation_id=installation_id).one_or_none()


def _cutoff_url(url: str, cutoff_date: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    raw = query.get("q", "")
    raw = re.sub(r"(?<!\S)after:\d{4}-\d{2}-\d{2}\b", "", raw, flags=re.IGNORECASE)

    # Convert "- intern" to "-intern", "- internship" to "-internship", etc.
    raw = re.sub(
        r"(?<!\S)-\s+(?=\S)",
        "-",
        raw,
    )

    raw = re.sub(r"\s+", " ", raw).strip()
    raw = f"{raw} after:{cutoff_date}".strip()
    query["q"] = raw
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _start_processing(installation_id: str):
    with PROCESSING_RUNS_LOCK:
        current = PROCESSING_RUNS.get(installation_id)
        if current is not None and not current["future"].done():
            return current["run_id"]

        run_id = uuid4().hex
        stop_event = threading.Event()
        with SessionLocal() as session:
            run = ProcessingRun(id=run_id, installation_id=installation_id, status="queued")
            session.add(run)
            session.flush()
            session.query(JobAnalysis).filter(
                JobAnalysis.installation_id == installation_id,
                JobAnalysis.is_processing.is_(True),
                JobAnalysis.processing_run_id.is_(None),
            ).update({"processing_run_id": run_id, "processing_status": "pending"}, synchronize_session=False)
            session.commit()

        future = EXECUTOR.submit(trigger_jobs_processing, installation_id, run_id, stop_event)
        PROCESSING_RUNS[installation_id] = {
            "run_id": run_id, "future": future, "stop_event": stop_event,
        }
        return run_id


def _processing_run_json(run, jobs):
    counts = {}
    for job in jobs:
        counts[job.processing_status] = counts.get(job.processing_status, 0) + 1
    return {
        "run_id": run.id if run else None,
        "installation_id": run.installation_id if run else (jobs[0].installation_id if jobs else None),
        "status": run.status if run else "idle",
        "cancel_requested": bool(run.cancel_requested) if run else False,
        "job_counts": counts,
        "jobs": [{
            "id": job.id, "url": job.link, "title": job.title,
            "status": job.processing_status,
            "is_processing": bool(job.is_processing),
            "has_error": bool(job.has_error),
        } for job in jobs],
    }


@app.get("/")
def index():
    return jsonify({"online": True})


@app.post("/api/automaton/google-search")
def google_search():
    data = GoogleSearchRequest.model_validate(request.get_json() or {})
    try:
        cutoff = date.fromisoformat(data.cutoff_date).isoformat()
    except ValueError as exc:
        return jsonify({"error": "cutoff_date must be YYYY-MM-DD"}), 400

    record = _installation(data.installation_id)
    if record is None:
        with SessionLocal() as session:
            record = InstalledExtensions(installation_id=data.installation_id, resume="", preferences="")
            session.add(record)
            session.commit()
    run_id = uuid4().hex
    with SessionLocal() as session:
        existing = []
        if not data.force_generate:
            existing = (
                session.query(JobGoogleSearchQuery)
                .filter(JobGoogleSearchQuery.installation_id == data.installation_id)
                .order_by(JobGoogleSearchQuery.created_at.desc())
                .all()
            )
        if existing:
            session.add(SearchRun(id=run_id, installation_id=data.installation_id, cutoff_date=cutoff, status="running"))
            for record in existing:
                record.google_search_url = _cutoff_url(record.google_search_url, cutoff)
                record.search_run_id = run_id
            session.commit()
            return jsonify({"search_run_id": run_id, "urls": [record.google_search_url for record in existing]})

    payload = InstallRequest(
        installation_id=record.installation_id,
        resume=record.resume,
        preferences=record.preferences,
        llm_provider=record.llm_provider or "ollama",
        llm_model=getattr(record, "llm_model", None),
        openai_key=record.openai_key,
        cutoff_date=cutoff,
    )
    searches = Agent(provider=payload.llm_provider, model=payload.llm_model, openai_key=payload.openai_key).generate_google_searches(payload)
    with SessionLocal() as session:
        session.add(SearchRun(id=run_id, installation_id=data.installation_id, cutoff_date=cutoff, status="running"))
        records = [
            JobGoogleSearchQuery(
                installation_id=data.installation_id, site=item.site, role_focus=item.role_focus,
                filters=item.filters, query=item.query, google_search_url=_cutoff_url(item.google_search_url, cutoff),
                search_run_id=run_id,
            )
            for item in searches
        ]
        session.add_all(records)
        session.commit()
    return jsonify({"search_run_id": run_id, "urls": [r.google_search_url for r in records]})


@app.post("/api/automaton/google-results")
def google_results():
    data = GoogleResultsRequest.model_validate(request.get_json() or {})
    links = list(dict.fromkeys(clean_url(link) for link in data.links if link))
    links = [link[:-6] if link.endswith("/apply") else link for link in links]
    with SessionLocal() as session:
        run = session.query(SearchRun).filter_by(id=data.search_run_id, installation_id=data.installation_id).one_or_none()
        if run is None:
            return jsonify({"error": "search run not found"}), 404
        existing = {r.link for r in session.query(JobAnalysis).filter(JobAnalysis.installation_id == data.installation_id, JobAnalysis.link.in_(links)).all()}
        session.add_all(JobAnalysis(link=link, title="processing...", installation_id=data.installation_id, is_processing=True) for link in links if link not in existing)
        run.status = "submitted"
        session.commit()
    processing_run_id = _start_processing(data.installation_id) if links else None
    return jsonify({
        "status": "success",
        "links_received": len(links),
        "processing_run_id": processing_run_id,
    })


@app.get("/api/automaton/processing")
def processing_status():
    installation_id = request.args.get("installation_id", "")
    if not installation_id:
        return jsonify({"error": "installation_id is required"}), 400
    with SessionLocal() as session:
        run = (
            session.query(ProcessingRun)
            .filter_by(installation_id=installation_id)
            .order_by(ProcessingRun.created_at.desc())
            .first()
        )
        query = session.query(JobAnalysis).filter(JobAnalysis.installation_id == installation_id)
        if run is not None:
            query = query.filter(JobAnalysis.processing_run_id == run.id)
        else:
            query = query.filter(JobAnalysis.is_processing.is_(True))
        jobs = query.order_by(JobAnalysis.created_at.asc(), JobAnalysis.id.asc()).all()
        return jsonify(_processing_run_json(run, jobs))


@app.post("/api/automaton/processing/stop")
def stop_processing():
    installation_id = (request.get_json() or {}).get("installation_id", "")
    if not installation_id:
        return jsonify({"error": "installation_id is required"}), 400

    with PROCESSING_RUNS_LOCK:
        current = PROCESSING_RUNS.get(installation_id)
        if current is not None and not current["future"].done():
            current["stop_event"].set()
            run_id = current["run_id"]
        else:
            run_id = None

    with SessionLocal() as session:
        run = (
            session.query(ProcessingRun)
            .filter_by(installation_id=installation_id)
            .order_by(ProcessingRun.created_at.desc())
            .first()
        )
        if run is None or run.status in {"completed", "cancelled", "failed"}:
            return jsonify({"error": "no active processing run"}), 404
        if run_id is None:
            run_id = run.id
        run.cancel_requested = True
        run.status = "cancelling"
        session.commit()
        return jsonify({"run_id": run_id, "status": run.status})


@app.post("/api/automaton/links")
def automaton_links():
    data = LinksRequest.model_validate(request.get_json() or {})
    limit = max(1, min(data.max_links, 100))
    with SessionLocal() as session:
        query = session.query(JobAnalysis).filter(
            JobAnalysis.installation_id == data.installation_id,
            JobAnalysis.is_processed.is_(False), JobAnalysis.has_error.is_(False),
        )
        if data.with_actions:
            query = query.filter(JobAnalysis.is_agent_processed.is_(True))
        rows = query.order_by(JobAnalysis.created_at.asc()).limit(limit).all()
        result = [{"id": row.id, "url": row.link, "notes": row.notes or "", "has_actions": row.is_agent_processed} for row in rows]
    return jsonify({"links": result})


@app.put("/api/automaton/links/<int:link_id>/notes")
def save_link_notes(link_id: int):
    data = LinkNotesRequest.model_validate(request.get_json() or {})
    with SessionLocal() as session:
        row = session.query(JobAnalysis).filter_by(id=link_id, installation_id=data.installation_id).one_or_none()
        if row is None:
            return jsonify({"error": "link not found"}), 404
        row.notes = data.notes
        session.commit()
    return jsonify({"status": "ok"})


@app.put("/api/automaton/links/<int:link_id>/processed")
def mark_link_processed(link_id: int):
    data = LinkNotesRequest.model_validate(request.get_json() or {})
    with SessionLocal() as session:
        row = session.query(JobAnalysis).filter_by(id=link_id, installation_id=data.installation_id).one_or_none()
        if row is None:
            return jsonify({"error": "link not found"}), 404
        row.is_processed = True
        if data.notes:
            row.notes = data.notes
        session.commit()
    return jsonify({"status": "ok"})


@app.post("/api/manual-fill")
def manual_fill():
    try:
        data = ManualFillRequest.model_validate({"installation_id": request.form.get("installation_id"), "url": request.form.get("url")})
    except Exception:
        return jsonify({"error": "installation_id and url are required"}), 400
    record = _installation(data.installation_id)
    if record is None:
        return jsonify({"error": "installation is not configured"}), 404
    html = request.form.get("html", "")
    context_file = request.files.get("context")
    context = context_file.read().decode("utf-8", errors="replace") if context_file else ""
    link = clean_url(data.url).removesuffix("/apply")
    with SessionLocal() as session:
        job = session.query(JobAnalysis).filter(JobAnalysis.link.like(f"%{link}%")).first()
        actions = [] if job is None else session.query(ApplicationActions).filter_by(job_analysis_id=job.id).all()
        response_actions = [Action(action=a.action, query_selector=a.query_selector, value=a.answer_text) for a in actions]
    if not response_actions:
        agent = Agent(provider=record.llm_provider or "ollama", model=getattr(record, "llm_model", None), openai_key=record.openai_key)
        generated = agent.generate_actions(html, context or f"Resume:\n{record.resume}\nPreferences:\n{record.preferences}")
        response_actions = [Action(action=a.action, query_selector=a.query_selector, value=a.value) for a in generated]
    return jsonify([item.model_dump(mode="json") for item in response_actions])


@app.get("/api/settings")
def get_settings():
    installation_id = request.args.get("installation_id", "")
    record = _installation(installation_id)
    if record is None:
        return jsonify({"error": "installation not found"}), 404
    return jsonify({
        "installation_id": record.installation_id,
        "llm_provider": record.llm_provider or "ollama",
        "llm_model": getattr(record, "llm_model", None),
        "has_api_key": bool(record.openai_key),
        "auto_fill": bool(record.auto_fill),
        "resume": record.resume or "",
        "preferences": record.preferences or "",
    })


@app.patch("/api/settings")
def update_settings():
    data = SettingsRequest.model_validate(request.get_json() or {})
    with SessionLocal() as session:
        record = session.query(InstalledExtensions).filter_by(installation_id=data.installation_id).one_or_none()
        if record is None:
            record = InstalledExtensions(installation_id=data.installation_id, resume="", preferences="")
            session.add(record)
        record.llm_provider = data.llm_provider
        record.llm_model = data.llm_model or None
        record.openai_key = data.openai_key
        record.auto_fill = data.auto_fill
        record.resume = data.resume
        record.preferences = data.preferences
        session.commit()
    return jsonify({"status": "ok"})


@app.post("/api/auto-fill/check")
def auto_fill_check():
    data = ExtensionRequest.model_validate(request.get_json() or {})
    record = _installation(data.installation_id)
    if record is None or not record.auto_fill:
        return jsonify([])
    return _actions_for_page(data)


def _actions_for_page(data: ExtensionRequest):
    link = clean_url(data.url).removesuffix("/apply")
    with SessionLocal() as session:
        job = session.query(JobAnalysis).filter(JobAnalysis.link.like(f"%{link}%")).first()
        if job:
            actions = session.query(ApplicationActions).filter_by(job_analysis_id=job.id).all()
            if actions:
                return jsonify([Action(action=a.action, query_selector=a.query_selector, value=a.answer_text).model_dump(mode="json") for a in actions])
    return jsonify([])


# Compatibility aliases for clients from the previous extension version.
@app.post("/api/filler")
def filler_compat():
    return _actions_for_page(ExtensionRequest.model_validate(request.get_json() or {}))


@app.post("/api/install")
def install_compat():
    data = InstallRequest.model_validate(request.get_json() or {})
    with SessionLocal() as session:
        record = session.query(InstalledExtensions).filter_by(installation_id=data.installation_id).one_or_none()
        if record is None:
            record = InstalledExtensions(installation_id=data.installation_id, resume=data.resume, preferences=data.preferences, openai_key=data.openai_key, llm_provider=data.llm_provider, llm_model=data.llm_model or None)
            session.add(record)
        else:
            record.resume, record.preferences, record.openai_key, record.llm_provider, record.llm_model = data.resume, data.preferences, data.openai_key, data.llm_provider, data.llm_model or None
        session.commit()
    return jsonify({"status": "configured"})


def shutdown_pool():
    try:
        EXECUTOR.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass



atexit.register(shutdown_pool)
signal.signal(signal.SIGTERM, lambda *_: os._exit(0))
signal.signal(signal.SIGINT, lambda *_: os._exit(0))

if __name__ == "__main__":
    app.run(port=8080)
