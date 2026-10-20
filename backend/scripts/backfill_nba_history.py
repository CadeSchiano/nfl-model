"""One-time NBA box-score backfill for a date range (default: 2025-26 season)."""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal, initialize_database
from app.services.nba_data_service import update_completed_nba_games

parser = argparse.ArgumentParser()
parser.add_argument("--start", default="2025-10-01")
parser.add_argument("--end", default="2026-06-30")
args = parser.parse_args()
initialize_database()
with SessionLocal() as db:
    print(f"Imported {update_completed_nba_games(db, date.fromisoformat(args.start), date.fromisoformat(args.end))} completed NBA games")
