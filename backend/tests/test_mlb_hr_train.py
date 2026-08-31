from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.ml.mlb_hr_train import train_hr_model
from app.models.mlb import MlbBatterFeature, MlbGame, MlbPlayerGame


def test_training_creates_a_new_versioned_artifact_from_past_games(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    with Session(engine) as session:
        for index in range(60):
            game_time = start + timedelta(days=index)
            session.add(MlbGame(id=index + 1, game_date=game_time, official_date=date(2026, 4, 1) + timedelta(days=index), home_team="Home", away_team="Away", status="final"))
            session.add(MlbPlayerGame(game_id=index + 1, player_id=index + 100, player_name="Batter", team="Home", appeared=True, home_runs=int(index % 5 == 0), plate_appearances=4))
            session.add(MlbBatterFeature(game_id=index + 1, player_id=index + 100, as_of=game_time, prior_games=index, prior_plate_appearances=index * 4, prior_home_runs=index // 5, hr_per_plate_appearance=.05))
        session.commit()

        trained_at = start + timedelta(days=100)
        record = train_hr_model(session, tmp_path, training_timestamp=trained_at)
        assert record.version == "mlb_hr_20260710T000000Z"
        assert (tmp_path / f"{record.version}.joblib").exists()
        assert record.training_data_through.replace(tzinfo=timezone.utc) == start + timedelta(days=59)
