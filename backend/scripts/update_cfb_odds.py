from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database  # noqa: E402
from app.services.cfb_data_service import import_cfb_market_totals  # noqa: E402

if __name__ == "__main__":
    initialize_database()
    with SessionLocal() as db:
        print(f"Saved {import_cfb_market_totals(db)} FBS CFB total-market snapshots")
