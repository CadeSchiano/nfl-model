"""Create local V0.1 SQLite tables."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import initialize_database  # noqa: E402

if __name__ == "__main__":
    initialize_database()
    print("Database tables are ready")
