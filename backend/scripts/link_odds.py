"""Link saved pregame odds snapshots to unlinked predictions."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database  # noqa: E402
from app.services.odds_linking_service import link_saved_odds  # noqa: E402

if __name__ == "__main__":
    initialize_database()
    with SessionLocal() as db:
        path = Path(__file__).resolve().parents[2] / "data" / "processed" / "odds_snapshots.jsonl"
        print(f"Linked {link_saved_odds(db, path)} predictions to immutable odds snapshots")
