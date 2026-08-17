#!/usr/bin/env python
"""Reprocess selected job-analysis rows from an existing processing run."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db.model import JobAnalysis, ProcessingRun, SessionLocal
from src.processors.processor import Processor


logger = logging.getLogger("reprocess_job_analysis")


def selected_jobs(run_id: str, statuses: list[str], limit: int | None = None):
    with SessionLocal() as session:
        query = (
            session.query(JobAnalysis)
            .filter(
                JobAnalysis.processing_run_id == run_id,
                JobAnalysis.processing_status.in_(statuses),
            )
            .order_by(JobAnalysis.created_at.asc(), JobAnalysis.id.asc())
        )
        if limit is not None:
            query = query.limit(limit)
        return [
            {"id": row.id, "link": row.link, "installation_id": row.installation_id}
            for row in query.all()
        ]


def set_status(job_id: int, status: str, *, has_error: bool = False):
    with SessionLocal() as session:
        session.query(JobAnalysis).filter(JobAnalysis.id == job_id).update(
            {
                "processing_status": status,
                "is_processing": status in {"pending", "running"},
                "has_error": has_error,
            }
        )
        session.commit()


async def reprocess(run_id: str, statuses: list[str], limit: int | None = None) -> int:
    with SessionLocal() as session:
        run = session.query(ProcessingRun).filter_by(id=run_id).one_or_none()
        if run is None:
            raise ValueError(f"Processing run not found: {run_id}")
        installation_id = run.installation_id

    jobs = selected_jobs(run_id, statuses, limit)
    if not jobs:
        logger.info("No job-analysis rows matched run=%s status=%s", run_id, statuses)
        return 0

    mismatched = [job for job in jobs if job["installation_id"] != installation_id]
    if mismatched:
        raise ValueError(f"Selected rows do not belong to processing run: {run_id}")

    processor = Processor(installation_id)
    failures = 0
    for job in jobs:
        set_status(job["id"], "running")
        try:
            await processor.process_job(job)
        except Exception:
            failures += 1
            set_status(job["id"], "failed", has_error=True)
            logger.exception("Failed to reprocess job id=%s url=%s", job["id"], job["link"])
        else:
            set_status(job["id"], "completed")
            logger.info("Reprocessed job id=%s url=%s", job["id"], job["link"])

    logger.info("Finished: %d selected, %d failed", len(jobs), failures)
    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processing-run-id", required=True)
    parser.add_argument(
        "--status",
        action="append",
        required=True,
        help="Status to reprocess; repeat for multiple statuses.",
    )
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be greater than zero")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        failures = asyncio.run(reprocess(args.processing_run_id, args.status, args.limit))
    except ValueError as exc:
        logger.error("%s", exc)
        return 2
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
