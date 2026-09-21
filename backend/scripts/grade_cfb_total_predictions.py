from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database  # noqa: E402
from app.services.cfb_prediction_service import grade_cfb_total_predictions  # noqa: E402

if __name__ == "__main__":
    initialize_database()
    with SessionLocal() as db:
        print(f"Graded {grade_cfb_total_predictions(db)} CFB total predictions")
