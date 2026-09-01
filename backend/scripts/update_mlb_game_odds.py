"""Fetch current MLB game market snapshots into MLB-only tables."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database  # noqa: E402
from app.services.mlb_odds_service import update_mlb_game_odds  # noqa: E402
if __name__ == "__main__":
    initialize_database()
    with SessionLocal() as db:
        print(f"Saved {update_mlb_game_odds(db)} MLB odds snapshots")
