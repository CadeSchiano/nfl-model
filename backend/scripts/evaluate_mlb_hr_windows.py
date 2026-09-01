"""Print chronological MLB HR rolling-window backtest results."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database  # noqa: E402
from app.ml.mlb_hr_evaluate import evaluate_rolling_windows  # noqa: E402

if __name__ == "__main__":
    initialize_database()
    with SessionLocal() as db:
        print(json.dumps(evaluate_rolling_windows(db), indent=2))
