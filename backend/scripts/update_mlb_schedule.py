"""Import today's MLB schedule and probable pitchers before prediction publishing."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database  # noqa: E402
from app.services.mlb_prediction_service import update_schedule  # noqa: E402

if __name__ == "__main__":
    initialize_database()
    with SessionLocal() as db:
        print(f"Updated {update_schedule(db)} MLB scheduled games")
