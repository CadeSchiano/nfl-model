from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database  # noqa
from app.services.live_prediction_service import generate_current_week_predictions  # noqa
from app.services.odds_linking_service import link_saved_odds  # noqa
if __name__ == "__main__":
    initialize_database()
    with SessionLocal() as db:
        generated = generate_current_week_predictions(db)
        snapshots = Path(__file__).resolve().parents[2] / "data" / "processed" / "odds_snapshots.jsonl"
        linked = link_saved_odds(db, snapshots)
        print(f"Generated {generated} current-week predictions; linked {linked} to immutable odds snapshots")
