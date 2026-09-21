from pathlib import Path
import sys
import argparse
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database  # noqa: E402
from app.services.nfl_first_touchdown_service import grade_first_touchdown_predictions  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--regrade", action="store_true"); args = parser.parse_args()
    initialize_database()
    with SessionLocal() as db:
        print(f"Graded {grade_first_touchdown_predictions(db, regrade=args.regrade)} first-touchdown predictions")
