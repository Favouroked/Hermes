"""Hermes command-line workflows for cover letters and applications."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pyperclip

from src.agents.agent import Agent
from src.db.model import CoverLetterRun, InstalledExtensions, JobAnalysis, SessionLocal


TERMINAL_RUN_STATES = {"completed", "cancelled", "failed"}


def _now():
    return datetime.now(timezone.utc)


def _installation(installation_id: str):
    with SessionLocal() as session:
        record = session.query(InstalledExtensions).filter_by(installation_id=installation_id).one_or_none()
        if record is None:
            raise ValueError(f"Installation not found: {installation_id}")
        return {
            "resume": record.resume or "",
            "provider": record.llm_provider or "ollama",
            "openai_key": record.openai_key,
        }


def _run_jobs(run_id: str):
    with SessionLocal() as session:
        return session.query(JobAnalysis).filter_by(cover_letter_run_id=run_id).order_by(JobAnalysis.created_at, JobAnalysis.id).all()


def _run_json(run, jobs):
    counts = {}
    for job in jobs:
        counts[job.cover_letter_status] = counts.get(job.cover_letter_status, 0) + 1
    return {"run_id": run.id, "installation_id": run.installation_id, "status": run.status,
            "cancel_requested": bool(run.cancel_requested), "job_counts": counts,
            "jobs": [{"id": j.id, "title": j.title, "url": j.link, "status": j.cover_letter_status} for j in jobs]}


def create_run(installation_id: str, limit: int | None = None) -> str:
    _installation(installation_id)
    with SessionLocal() as session:
        query = session.query(JobAnalysis).filter(
            JobAnalysis.installation_id == installation_id,
            JobAnalysis.page_text.is_not(None),
            JobAnalysis.page_text != "",
            (JobAnalysis.cover_letter.is_(None) | (JobAnalysis.cover_letter == "")),
        ).order_by(JobAnalysis.created_at, JobAnalysis.id)
        if limit is not None:
            query = query.limit(limit)
        jobs = query.all()
        if not jobs:
            raise ValueError("No eligible jobs with page text and no cover letter")
        run_id = uuid4().hex
        session.add(CoverLetterRun(id=run_id, installation_id=installation_id, status="queued"))
        for job in jobs:
            job.cover_letter_run_id = run_id
            job.cover_letter_status = "pending"
            job.cover_letter_error = None
        session.commit()
    return run_id


def start_generation(installation_id: str, resume_file: str | None = None, limit: int | None = None) -> str:
    run_id = create_run(installation_id, limit)
    command = [sys.executable, "-m", "src.cli", "cover-letter", "_worker", "--run-id", run_id]
    if resume_file:
        command.extend(["--resume-file", resume_file])
    # Inherit the caller's working directory so the worker uses the same
    # relative SQLite database when Hermes is installed outside the repository.
    subprocess.Popen(command, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return run_id


def generate_worker(run_id: str, resume_file: str | None = None) -> int:
    with SessionLocal() as session:
        run = session.query(CoverLetterRun).filter_by(id=run_id).one_or_none()
        if run is None:
            raise ValueError(f"Cover-letter run not found: {run_id}")
        installation_id = run.installation_id
        if run.cancel_requested:
            run.status = "cancelled"
            run.finished_at = _now()
            session.commit()
            return 0
        run.status = "running"
        run.started_at = _now()
        session.commit()
    failed = False
    try:
        installation = _installation(installation_id)
        resume = Path(resume_file).read_text(encoding="utf-8") if resume_file else installation["resume"]
        agent = Agent(provider=installation["provider"], openai_key=installation["openai_key"])
        for job in _run_jobs(run_id):
            with SessionLocal() as session:
                run = session.query(CoverLetterRun).filter_by(id=run_id).one()
                if run.cancel_requested:
                    run.status = "cancelled"
                    run.finished_at = _now()
                    session.query(JobAnalysis).filter_by(cover_letter_run_id=run_id, cover_letter_status="pending").update({"cover_letter_status": "cancelled"}, synchronize_session=False)
                    session.commit()
                    return 0
                session.query(JobAnalysis).filter_by(id=job.id).update({"cover_letter_status": "running"})
                session.commit()
            try:
                letter = agent.generate_cover_letter(job.page_text, resume)
                if not letter:
                    raise ValueError("Provider returned an empty cover letter")
            except Exception as exc:
                failed = True
                with SessionLocal() as session:
                    session.query(JobAnalysis).filter_by(id=job.id).update({"cover_letter_status": "failed", "cover_letter_error": str(exc)})
                    session.commit()
            else:
                with SessionLocal() as session:
                    session.query(JobAnalysis).filter_by(id=job.id).update({"cover_letter": letter, "cover_letter_status": "completed", "cover_letter_error": None})
                    session.commit()
    except Exception as exc:
        failed = True
        with SessionLocal() as session:
            run = session.query(CoverLetterRun).filter_by(id=run_id).one_or_none()
            if run:
                run.status = "failed"
                run.finished_at = _now()
                session.query(JobAnalysis).filter_by(cover_letter_run_id=run_id, cover_letter_status="pending").update(
                    {"cover_letter_status": "failed", "cover_letter_error": str(exc)}, synchronize_session=False
                )
                session.commit()
    finally:
        with SessionLocal() as session:
            run = session.query(CoverLetterRun).filter_by(id=run_id).one_or_none()
            if run and run.status == "running":
                run.status = "failed" if failed else "completed"
                run.finished_at = _now()
                session.commit()
    return 1 if failed else 0


def show_status(run_id: str | None = None, installation_id: str | None = None) -> int:
    with SessionLocal() as session:
        query = session.query(CoverLetterRun)
        if run_id:
            run = query.filter_by(id=run_id).one_or_none()
        else:
            run = query.filter_by(installation_id=installation_id).order_by(CoverLetterRun.created_at.desc()).first()
        if run is None:
            raise ValueError("Cover-letter run not found")
        print(json.dumps(_run_json(run, session.query(JobAnalysis).filter_by(cover_letter_run_id=run.id).order_by(JobAnalysis.created_at, JobAnalysis.id).all()), indent=2, default=str))
    return 0


def stop_generation(run_id: str) -> int:
    with SessionLocal() as session:
        run = session.query(CoverLetterRun).filter_by(id=run_id).one_or_none()
        if run is None:
            raise ValueError("Cover-letter run not found")
        if run.status in TERMINAL_RUN_STATES:
            print(f"Run {run.id} is already {run.status}")
            return 0
        run.cancel_requested = True
        run.status = "cancelling"
        session.commit()
    print(f"Cancellation requested for {run_id}")
    return 0


def save_note(job_id: int, installation_id: str, notes: str):
    with SessionLocal() as session:
        job = session.query(JobAnalysis).filter_by(id=job_id, installation_id=installation_id).one_or_none()
        if job is None:
            raise ValueError(f"Job not found: {job_id}")
        job.notes = notes
        session.commit()


def apply_loop(installation_id: str, limit: int | None = None) -> int:
    with SessionLocal() as session:
        query = session.query(JobAnalysis).filter(
            JobAnalysis.installation_id == installation_id,
            JobAnalysis.is_processed.is_(False),
            JobAnalysis.cover_letter.is_not(None),
            JobAnalysis.cover_letter != "",
        ).order_by(JobAnalysis.created_at, JobAnalysis.id)
        jobs = query.limit(limit).all() if limit else query.all()
    for position, job in enumerate(jobs, 1):
        print(f"\n[{position}/{len(jobs)}] {job.title} — {job.company or 'Unknown company'}")
        print(job.link)
        pyperclip.copy(job.cover_letter)
        print("Cover letter copied. Press Enter to mark processed, n to edit notes, or s to stop.")
        while True:
            try:
                command = input("> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nLoop stopped; current job was not marked processed.")
                return 0
            if command == "":
                with SessionLocal() as session:
                    session.query(JobAnalysis).filter_by(id=job.id).update({"is_processed": True})
                    session.commit()
                break
            if command in {"s", "q"}:
                print("Loop stopped; current job was not marked processed.")
                return 0
            if command == "n":
                notes = input(f"Notes [{job.notes or ''}]: ")
                save_note(job.id, installation_id, notes)
                job.notes = notes
                print("Notes saved. Press Enter to continue or choose another command.")
                continue
            print("Use Enter, n, or s.")
    print("No more eligible jobs.")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="hermes")
    commands = parser.add_subparsers(dest="command", required=True)
    cover = commands.add_parser("cover-letter")
    sub = cover.add_subparsers(dest="action", required=True)
    generate = sub.add_parser("generate")
    generate.add_argument("--installation-id", required=True)
    generate.add_argument("--resume-file")
    generate.add_argument("--limit", type=int)
    status = sub.add_parser("status")
    status.add_argument("--run-id")
    status.add_argument("--installation-id")
    stop = sub.add_parser("stop", aliases=["cancel"])
    stop.add_argument("--run-id", required=True)
    loop = sub.add_parser("apply-loop", aliases=["apply"])
    loop.add_argument("--installation-id", required=True)
    loop.add_argument("--limit", type=int)
    worker = sub.add_parser("_worker")
    worker.add_argument("--run-id", required=True)
    worker.add_argument("--resume-file")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.action == "generate":
            if args.limit is not None and args.limit < 1:
                raise ValueError("--limit must be greater than zero")
            run_id = start_generation(args.installation_id, args.resume_file, args.limit)
            print(run_id)
            return 0
        if args.action == "status":
            if not args.run_id and not args.installation_id:
                raise ValueError("provide --run-id or --installation-id")
            return show_status(args.run_id, args.installation_id)
        if args.action in {"stop", "cancel"}:
            return stop_generation(args.run_id)
        if args.action in {"apply-loop", "apply"}:
            return apply_loop(args.installation_id, args.limit)
        return generate_worker(args.run_id, args.resume_file)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
