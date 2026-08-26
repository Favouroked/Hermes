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
            "model": getattr(record, "llm_model", None),
            "api_key": record.openai_key,
        }


def _mask_api_key(api_key: str | None) -> str | None:
    if not api_key:
        return None
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}...{api_key[-4:]}"


def _settings_json(record) -> dict:
    return {
        "installation_id": record.installation_id,
        "llm_provider": record.llm_provider or "ollama",
        "llm_model": getattr(record, "llm_model", None),
        "auto_fill": bool(record.auto_fill),
        "resume": record.resume or "",
        "preferences": record.preferences or "",
        "has_api_key": bool(record.openai_key),
        "api_key": _mask_api_key(record.openai_key),
    }


def show_settings(installation_id: str) -> int:
    with SessionLocal() as session:
        record = session.query(InstalledExtensions).filter_by(installation_id=installation_id).one_or_none()
        if record is None:
            raise ValueError(f"Installation not found: {installation_id}")
        print(json.dumps(_settings_json(record), indent=2))
    return 0


def update_settings(
    installation_id: str,
    *,
    resume: str | None = None,
    resume_file: str | None = None,
    preferences: str | None = None,
    preferences_file: str | None = None,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    api_key: str | None = None,
    clear_api_key: bool = False,
    auto_fill: bool | None = None,
    clear_resume: bool = False,
    clear_preferences: bool = False,
) -> int:
    if resume is not None and resume_file:
        raise ValueError("--resume and --resume-file cannot be used together")
    if preferences is not None and preferences_file:
        raise ValueError("--preferences and --preferences-file cannot be used together")
    if api_key is not None and clear_api_key:
        raise ValueError("--api-key and --clear-api-key cannot be used together")
    if resume is not None and clear_resume or resume_file and clear_resume:
        raise ValueError("resume value and --clear-resume cannot be used together")
    if preferences is not None and clear_preferences or preferences_file and clear_preferences:
        raise ValueError("preferences value and --clear-preferences cannot be used together")
    if api_key == "":
        raise ValueError("--api-key cannot be empty; use --clear-api-key")

    if resume_file:
        resume = Path(resume_file).read_text(encoding="utf-8")
    if preferences_file:
        preferences = Path(preferences_file).read_text(encoding="utf-8")

    if all(value is None for value in (resume, preferences, llm_provider, llm_model, api_key, auto_fill)) and not (
        clear_api_key or clear_resume or clear_preferences
    ):
        raise ValueError("provide at least one setting to update")

    with SessionLocal() as session:
        record = session.query(InstalledExtensions).filter_by(installation_id=installation_id).one_or_none()
        if record is None:
            raise ValueError(f"Installation not found: {installation_id}")

        if resume is not None:
            record.resume = resume
        elif clear_resume:
            record.resume = ""
        if preferences is not None:
            record.preferences = preferences
        elif clear_preferences:
            record.preferences = ""
        if llm_provider is not None:
            record.llm_provider = llm_provider
        if llm_model is not None:
            record.llm_model = llm_model or None
        if api_key is not None:
            record.openai_key = api_key
        elif clear_api_key:
            record.openai_key = None
        if auto_fill is not None:
            record.auto_fill = auto_fill
        session.commit()
        print(json.dumps(_settings_json(record), indent=2))
    return 0


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
        agent = Agent(provider=installation["provider"], model=installation["model"], openai_key=installation["api_key"])
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

    settings = commands.add_parser("settings")
    settings_sub = settings.add_subparsers(dest="settings_action", required=True)
    settings_show = settings_sub.add_parser("show")
    settings_show.add_argument("--installation-id", required=True)
    settings_update = settings_sub.add_parser("update")
    settings_update.add_argument("--installation-id", required=True)
    settings_update.add_argument("--resume")
    settings_update.add_argument("--resume-file")
    settings_update.add_argument("--preferences")
    settings_update.add_argument("--preferences-file")
    settings_update.add_argument("--llm-provider", choices=["ollama", "openai", "lm_studio"])
    settings_update.add_argument("--llm-model")
    settings_update.add_argument("--api-key")
    settings_update.add_argument("--clear-api-key", action="store_true")
    settings_update.add_argument("--auto-fill", dest="auto_fill", action="store_true")
    settings_update.add_argument("--no-auto-fill", dest="auto_fill", action="store_false")
    settings_update.set_defaults(auto_fill=None)
    settings_update.add_argument("--clear-resume", action="store_true")
    settings_update.add_argument("--clear-preferences", action="store_true")

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
        if args.command == "settings":
            if args.settings_action == "show":
                return show_settings(args.installation_id)
            return update_settings(
                args.installation_id,
                resume=args.resume,
                resume_file=args.resume_file,
                preferences=args.preferences,
                preferences_file=args.preferences_file,
                llm_provider=args.llm_provider,
                llm_model=args.llm_model,
                api_key=args.api_key,
                clear_api_key=args.clear_api_key,
                auto_fill=args.auto_fill,
                clear_resume=args.clear_resume,
                clear_preferences=args.clear_preferences,
            )
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
