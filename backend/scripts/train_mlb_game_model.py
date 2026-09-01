from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database  # noqa: E402
from app.ml.mlb_game_model import train_game_model  # noqa: E402
if __name__ == "__main__":
    initialize_database()
    with SessionLocal() as db:
        model = train_game_model(db, Path(__file__).resolve().parents[1] / "app" / "ml" / "models" / "mlb_games")
        print(f"Trained {model.version}")
