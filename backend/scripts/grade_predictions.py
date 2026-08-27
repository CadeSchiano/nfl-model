"""Grade every ungraded prediction whose game has completed."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database  # noqa: E402
from app.services.grading_service import grade_completed_predictions  # noqa: E402

if __name__ == "__main__":
    initialize_database()
    with SessionLocal() as session:
        print(f"Graded {grade_completed_predictions(session)} predictions")
