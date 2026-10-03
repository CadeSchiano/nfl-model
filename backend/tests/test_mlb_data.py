from datetime import date, datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.models.mlb import MlbGame
from app.services.mlb_data import MLB_GAME_TYPES, _appearance_and_hr, ingest_completed_game


def test_extracts_actual_appearances_and_home_runs() -> None:
    feed = {"liveData": {"plays": {"allPlays": [{"matchup": {"batter": {"id": 10}, "pitcher": {"id": 20}}, "result": {"eventType": "home_run"}}, {"matchup": {"batter": {"id": 10}, "pitcher": {"id": 21}}, "result": {"eventType": "strikeout"}}]}}}
    appeared, homers = _appearance_and_hr(feed)
    assert appeared == {10, 20, 21}
    assert homers == {10: 1}


def test_supported_schedule_types_include_postseason_rounds() -> None:
    assert set(MLB_GAME_TYPES.split(",")) == {"R", "F", "D", "L", "W"}


def test_scoreless_final_feed_is_not_saved_as_a_completed_game() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    feed = {
        "gamePk": 99,
        "gameData": {
            "datetime": {"dateTime": "2026-10-02T20:00:00Z", "officialDate": "2026-10-02"},
            "teams": {"home": {"name": "Home"}, "away": {"name": "Away"}},
        },
        "liveData": {"linescore": {"teams": {"home": {}, "away": {}}}},
    }
    with Session(engine) as session:
        assert ingest_completed_game(session, feed) is False
        session.commit()
        game = session.get(MlbGame, 99)
        assert game is not None
        assert game.status == "incomplete"
        assert game.home_score is None
        assert game.away_score is None
