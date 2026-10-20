"""Publish upcoming NBA moneyline predictions."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database
from app.services.nba_prediction_service import publish_nba_game_predictions
initialize_database()
with SessionLocal() as db: print(f"Published {publish_nba_game_predictions(db)} NBA game predictions")
