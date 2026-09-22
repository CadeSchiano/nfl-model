"""Void manually confirmed inactive TD picks and publish eligible replacements."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database  # noqa: E402
from app.services.nfl_first_touchdown_service import publish_first_touchdown_predictions  # noqa: E402
from app.services.nfl_td_prediction_service import publish_touchdown_predictions  # noqa: E402

if __name__ == "__main__":
    initialize_database()
    with SessionLocal() as db:
        print(f"Published {publish_touchdown_predictions(db)} replacement NFL touchdown predictions")
        print(f"Published {publish_first_touchdown_predictions(db)} current first-touchdown predictions")
