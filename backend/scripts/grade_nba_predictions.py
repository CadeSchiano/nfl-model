"""Grade completed NBA moneyline and confirmed-starter predictions."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database
from app.services.nba_prediction_service import grade_nba_predictions
initialize_database()
with SessionLocal() as db: print(grade_nba_predictions(db))
