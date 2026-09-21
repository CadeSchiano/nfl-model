from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database  # noqa: E402
from app.models.game import Game  # noqa: E402
from app.services.nfl_player_stats_service import refresh_player_season_stats  # noqa: E402

if __name__ == "__main__":
    initialize_database()
    with SessionLocal() as db:
        season = max(game.season for game in db.query(Game).all())
        print(f"Updated {refresh_player_season_stats(db, season)} NFL player season stat lines")
