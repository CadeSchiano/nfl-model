"""Publish locked MLB HR predictions only after the MLB feed lists both starting lineups."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database  # noqa: E402
from app.services.mlb_prediction_service import publish_hr_predictions  # noqa: E402

if __name__ == "__main__":
    initialize_database()
    with SessionLocal() as db:
        print(f"Published {publish_hr_predictions(db)} official MLB HR predictions")
