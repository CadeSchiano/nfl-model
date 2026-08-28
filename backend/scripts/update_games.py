"""Import current regular-season NFL schedule into the local database."""
from pathlib import Path
import sys
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.database import SessionLocal, initialize_database  # noqa: E402
from app.models.game import Game, Team  # noqa: E402
from app.services.elo_service import canonical_team_code  # noqa: E402
from app.services.nfl_data import download_nflverse_games  # noqa: E402


def main() -> None:
    raw = download_nflverse_games()
    season = int(raw.season.max())
    games = raw[(raw.season == season) & (raw.game_type == "REG")].copy()
    games["date"] = pd.to_datetime(games.gameday.astype(str) + " " + games.gametime.fillna("00:00")).dt.tz_localize("America/New_York").dt.tz_convert("UTC")
    initialize_database()
    with SessionLocal() as db:
        teams = set(games.home_team).union(games.away_team)
        for code in teams:
            code = canonical_team_code(code)
            if db.scalar(db.query(Team).filter_by(abbreviation=code).statement) is None:
                db.add(Team(abbreviation=code, name=code))
        for row in games.itertuples():
            game_id = str(row.game_id)
            existing = db.get(Game, game_id)
            if existing is None:
                db.add(Game(id=game_id, season=season, week=int(row.week), date=row.date.to_pydatetime(), home_team=canonical_team_code(row.home_team), away_team=canonical_team_code(row.away_team), status="scheduled", home_rest=int(row.home_rest) if pd.notna(row.home_rest) else None, away_rest=int(row.away_rest) if pd.notna(row.away_rest) else None, division_game=bool(row.div_game)))
            else:
                existing.date, existing.home_rest, existing.away_rest, existing.division_game = row.date.to_pydatetime(), (int(row.home_rest) if pd.notna(row.home_rest) else None), (int(row.away_rest) if pd.notna(row.away_rest) else None), bool(row.div_game)
        db.commit()
    print(f"Imported {len(games)} {season} regular-season games")


if __name__ == "__main__":
    main()
