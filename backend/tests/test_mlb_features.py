from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.models.mlb import MlbBatterFeature, MlbGame, MlbPlayerGame
from app.services.mlb_feature_service import refresh_batter_features


def test_features_use_only_completed_games_before_the_current_game() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    with Session(engine) as session:
        for game_id, hours, homers, pa in [(1, 0, 1, 4), (2, 24, 0, 5), (3, 48, 2, 4)]:
            game_time = start + timedelta(hours=hours)
            session.add(MlbGame(id=game_id, game_date=game_time, official_date=date(2026, 4, game_id), home_team="Home", away_team="Away", status="final"))
            session.add(MlbPlayerGame(game_id=game_id, player_id=7, player_name="Batter", team="Home", appeared=True, home_runs=homers, plate_appearances=pa))
        session.commit()

        assert refresh_batter_features(session) == 3
        features = {row.game_id: row for row in session.query(MlbBatterFeature).all()}
        assert features[1].prior_games == 0
        assert features[2].prior_home_runs == 1
        assert features[2].prior_plate_appearances == 4
        assert features[3].prior_home_runs == 1  # game 3's two HRs are excluded
        assert features[3].prior_plate_appearances == 9
