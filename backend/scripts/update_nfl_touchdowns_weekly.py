"""One-command weekly NFL TD refresh, retrain, and future-pick publisher."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from app.db.database import SessionLocal, initialize_database  # noqa: E402
from app.ml.nfl_td_model import build_td_features, train_td_model  # noqa: E402
from app.services.nfl_first_touchdown_service import grade_first_touchdown_predictions, publish_first_touchdown_predictions  # noqa: E402
from app.services.nfl_td_learning_service import CURRENT_GAMES_PATH, CURRENT_HISTORY_PATH, refresh_completed_td_history  # noqa: E402
from app.services.nfl_td_prediction_service import grade_touchdown_predictions, publish_touchdown_predictions  # noqa: E402
from app.services.nfl_player_stats_service import refresh_player_season_stats  # noqa: E402


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    initialize_database()
    with SessionLocal() as db:
        print(f"Graded {grade_touchdown_predictions(db)} NFL touchdown predictions")
        print(f"Graded {grade_first_touchdown_predictions(db)} first-touchdown predictions")
        print(f"Added {refresh_completed_td_history(db)} completed player-game TD observations")
        print(f"Updated {refresh_player_season_stats(db, 2026)} NFL player season stat lines")
        features = build_td_features(pd.read_parquet(CURRENT_HISTORY_PATH), pd.read_csv(CURRENT_GAMES_PATH))
        model_path = train_td_model(features, root / "backend/app/ml/models/td")
        print(f"Trained {model_path.stem}")
        print(f"Published {publish_touchdown_predictions(db)} NFL touchdown predictions")
        print(f"Published {publish_first_touchdown_predictions(db)} first-touchdown predictions")
