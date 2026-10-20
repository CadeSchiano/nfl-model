"""Import the upcoming week of NBA games from ESPN."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database
from app.services.nba_data_service import update_nba_schedule
initialize_database()
with SessionLocal() as db: print(f"Updated {update_nba_schedule(db)} NBA games")
