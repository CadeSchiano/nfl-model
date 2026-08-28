from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database  # noqa
from app.services.live_prediction_service import generate_current_week_predictions  # noqa
if __name__ == "__main__":
    initialize_database()
    with SessionLocal() as db: print(f"Generated {generate_current_week_predictions(db)} current-week predictions")
