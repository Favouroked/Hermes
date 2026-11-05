#!/usr/bin/env python
"""Replace Google /goto URLs in job-analysis rows with their destination URLs."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from urllib.parse import urlsplit

import requests

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db.model import JobAnalysis, SessionLocal

logger = logging.getLogger("fix_google_goto_links")


def _is_google_goto(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        hostname = (parsed.hostname or "").lower().rstrip(".")
    except ValueError:
        return False

    return (
            (hostname == "google.com" or hostname.endswith(".google.com"))
            and parsed.path.rstrip("/") == "/goto"
    )


def destination_url(url: str) -> str | None:
    """Return the HTTP(S) destination from a Google /goto URL, if valid."""
    try:
        r = requests.get(url)
        r.raise_for_status()
        return r.url
    except Exception as e:
        logger.error(f"Error extracting destination for url [{url}]: [{e}]")
        return None


def update_links(*, dry_run: bool = False, limit: int | None = None) -> tuple[int, int]:
    """Update matching job rows and return (updated, skipped)."""
    updated = 0
    skipped = 0

    with SessionLocal() as session:
        processed_links = session.query(JobAnalysis.link).filter(JobAnalysis.link.not_ilike("%google.com/goto%")).all()
        processed_links = {link[0] for link in processed_links}

        query = (
            session.query(JobAnalysis)
            .filter(JobAnalysis.link.ilike("%google.com/goto%"))
            .order_by(JobAnalysis.id.asc())
        )
        if limit is not None:
            query = query.limit(limit)

        for row in query.all():
            destination = destination_url(row.link)
            if destination is None or destination in processed_links:
                skipped += 1
                warning_msg = f"job id={row.id} duplicate link detected: [{destination}]" if destination in processed_links else f"Could not extract destination for job id={row.id}"
                logger.warning(warning_msg)
                continue

            logger.info("job id=%s: %s -> %s", row.id, row.link, destination)
            if not dry_run:
                row.link = destination
            processed_links.add(destination)
            updated += 1

        if not dry_run:
            session.commit()

    return updated, skipped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show matching changes without writing them to the database.",
    )
    parser.add_argument("--limit", type=int, help="Process at most this many rows.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be greater than zero")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    updated, skipped = update_links(dry_run=args.dry_run, limit=args.limit)
    action = "Would update" if args.dry_run else "Updated"
    logger.info(
        "%s %d job links; skipped %d invalid Google goto links",
        action,
        updated,
        skipped,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
