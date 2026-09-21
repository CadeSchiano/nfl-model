from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database  # noqa: E402
from app.services.cfb_data_service import import_fbs_games  # noqa: E402

if __name__ == "__main__":
    initialize_database()
    with SessionLocal() as db:
        print(f"Imported {import_fbs_games(db, range(2019, 2027))} new FBS-vs-FBS CFB games")
