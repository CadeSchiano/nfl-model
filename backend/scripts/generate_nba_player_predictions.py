"""Publish NBA PTS/REB/AST/3PM projections for confirmed starters only."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database
from app.services.nba_prediction_service import publish_nba_player_predictions
initialize_database()
with SessionLocal() as db: print(f"Published {publish_nba_player_predictions(db)} NBA starter predictions")
