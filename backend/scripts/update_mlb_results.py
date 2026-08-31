"""Manually ingest completed MLB games, optionally across a date range."""
import argparse
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database  # noqa: E402
from app.services.mlb_data import update_completed_games  # noqa: E402


def iso_date(value: str) -> date:
    """Parse a CLI date with a clear error for unsupported formats."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("dates must use YYYY-MM-DD") from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import final MLB games into the local MLB-only database.")
    parser.add_argument("--start", type=iso_date, help="First date to import (YYYY-MM-DD)")
    parser.add_argument("--end", type=iso_date, help="Last date to import (YYYY-MM-DD)")
    args = parser.parse_args(argv)
    if (args.start is None) != (args.end is None):
        parser.error("use --start and --end together")
    if args.start and args.start > args.end:
        parser.error("--start cannot be after --end")
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    initialize_database()
    with SessionLocal() as db:
        print(f"Imported {update_completed_games(db, start=args.start, end=args.end)} completed MLB games")


if __name__ == "__main__":
    main()
