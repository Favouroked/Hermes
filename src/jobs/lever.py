import asyncio
from datetime import datetime, timezone

from src.config.logger import get_logger
from src.db.model import JobAnalysis, ProcessingRun, SessionLocal
from src.processors.lever import LeverProcessor, ProcessingCancelled

logger = get_logger(__name__)


def pending_jobs(installation_id: str, run_id: str):
    with SessionLocal() as session:
        records = (
            session.query(JobAnalysis)
            .filter(
                JobAnalysis.installation_id == installation_id,
                JobAnalysis.processing_run_id == run_id,
                JobAnalysis.processing_status == "pending",
            )
            .order_by(JobAnalysis.created_at.asc(), JobAnalysis.id.asc())
            .all()
        )
        return [{"link": record.link, "id": record.id} for record in records]


def _set_job_status(job_id: int, status: str, *, has_error: bool = False):
    with SessionLocal() as session:
        session.query(JobAnalysis).filter(JobAnalysis.id == job_id).update({
            "processing_status": status,
            "is_processing": status in {"pending", "running"},
            "has_error": has_error,
        })
        session.commit()


def _cancel_pending_jobs(run_id: str):
    with SessionLocal() as session:
        session.query(JobAnalysis).filter(
            JobAnalysis.processing_run_id == run_id,
            JobAnalysis.processing_status == "pending",
        ).update({"processing_status": "cancelled", "is_processing": False}, synchronize_session=False)
        session.commit()


async def _execute(installation_id: str, run_id: str, stop_event):
    with SessionLocal() as session:
        run = session.query(ProcessingRun).filter_by(id=run_id).one_or_none()
        if run is None:
            return
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        session.commit()

    processor = LeverProcessor(installation_id)
    cancelled = False
    for data in pending_jobs(installation_id, run_id):
        if stop_event.is_set():
            cancelled = True
            break
        _set_job_status(data["id"], "running")
        try:
            await processor.process_job(data, stop_event)
        except ProcessingCancelled:
            _set_job_status(data["id"], "cancelled")
            cancelled = True
            break
        except Exception as exc:
            logger.exception("Job [%s] error: %s", data, exc)
            _set_job_status(data["id"], "failed", has_error=True)
        else:
            _set_job_status(data["id"], "completed")

    if stop_event.is_set():
        cancelled = True
    if cancelled:
        _cancel_pending_jobs(run_id)
    with SessionLocal() as session:
        run = session.query(ProcessingRun).filter_by(id=run_id).one_or_none()
        if run is not None:
            run.status = "cancelled" if cancelled else "completed"
            run.finished_at = datetime.now(timezone.utc)
            session.commit()


def execute(installation_id: str, run_id: str, stop_event):
    try:
        return asyncio.run(_execute(installation_id, run_id, stop_event))
    except Exception as e:
        logger.exception(e)
        with SessionLocal() as session:
            run = session.query(ProcessingRun).filter_by(id=run_id).one_or_none()
            if run is not None:
                run.status = "failed"
                run.finished_at = datetime.now(timezone.utc)
                session.commit()
