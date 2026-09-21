from pathlib import Path
import sys
from datetime import datetime
import argparse
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database  # noqa: E402
from app.services.cfb_data_service import import_fbs_games  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", action="store_true", help="Backfill 2019 through the current season; only needed for initial setup.")
    args = parser.parse_args()
    initialize_database()
    with SessionLocal() as db:
        current = datetime.now().year
        seasons = range(2019, current + 1) if args.history else range(current, current + 1)
        print(f"Imported {import_fbs_games(db, seasons)} new FBS-vs-FBS CFB games")
