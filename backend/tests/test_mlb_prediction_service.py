from datetime import date, datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.ml.mlb_game_model import _team_history
from app.models.mlb import MlbGame
from app.services.mlb_prediction_service import confirmed_batters


def test_confirmed_batters_requires_nine_batting_slots_per_team() -> None:
    def team(name, offset):
        return {"team": {"name": name}, "players": {str(offset + number): {"person": {"id": offset + number, "fullName": f"{name} {number}"}, "battingOrder": str(number * 100)} for number in range(1, 10)}}

    feed = {"liveData": {"boxscore": {"teams": {"away": team("Away", 100), "home": team("Home", 200)}}}}
    lineup = confirmed_batters(feed)
    assert len(lineup) == 18
    assert lineup[0]["player_name"] == "Away 1"
    del feed["liveData"]["boxscore"]["teams"]["home"]["players"]["209"]
    assert confirmed_batters(feed) == []


def test_team_history_ignores_legacy_final_rows_without_scores() -> None:
    time = datetime(2026, 9, 27, tzinfo=timezone.utc)
    scoreless = MlbGame(id=1, game_date=time, official_date=date(2026, 9, 27), home_team="Home", away_team="Away", status="final")
    scored = MlbGame(id=2, game_date=time, official_date=date(2026, 9, 27), home_team="Home", away_team="Away", home_score=5, away_score=3, status="final")

    history = _team_history([scoreless, scored])

    assert list(history["Home"]) == [(1, 2)]
    assert list(history["Away"]) == [(0, -2)]
