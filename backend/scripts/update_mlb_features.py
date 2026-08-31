"""Refresh leakage-safe MLB batter rolling features after final results import."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database  # noqa: E402
from app.services.mlb_feature_service import refresh_batter_features  # noqa: E402

if __name__ == "__main__":
    initialize_database()
    with SessionLocal() as db:
        print(f"Refreshed {refresh_batter_features(db)} MLB batter feature rows")
