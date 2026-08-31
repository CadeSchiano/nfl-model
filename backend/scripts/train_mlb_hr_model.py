"""Manually train a new, versioned MLB HR model after ingestion and feature refresh."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database  # noqa: E402
from app.ml.mlb_hr_train import train_hr_model  # noqa: E402

if __name__ == "__main__":
    initialize_database()
    with SessionLocal() as db:
        record = train_hr_model(db, Path(__file__).resolve().parents[1] / "app" / "ml" / "models" / "mlb")
        print(f"Trained {record.version} through {record.training_data_through.isoformat()}")
