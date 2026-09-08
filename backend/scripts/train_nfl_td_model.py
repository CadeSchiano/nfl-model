from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ml.nfl_td_model import build_td_features, train_td_model  # noqa
if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    history = root / "data/processed/nfl_td_player_games_2019_current.parquet"
    games = root / "data/processed/nfl_td_games_2019_current.csv"
    features = build_td_features(__import__("pandas").read_parquet(history if history.exists() else root / "data/processed/nfl_td_player_games_2019_2025.parquet"), __import__("pandas").read_csv(games if games.exists() else root / "data/processed/games_2015_2025.csv"))
    print(f"Trained TD model at {train_td_model(features, root / 'backend/app/ml/models/td')}")
