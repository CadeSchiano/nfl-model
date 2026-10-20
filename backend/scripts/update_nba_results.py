"""Import recently completed NBA scores and player box scores."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database
from app.services.nba_data_service import update_completed_nba_games
initialize_database()
with SessionLocal() as db: print(f"Imported {update_completed_nba_games(db)} completed NBA games")
