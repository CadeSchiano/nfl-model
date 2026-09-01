from datetime import date, datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.models.mlb import MlbGame, MlbHrPrediction
from app.services.mlb_performance_service import hr_performance


def test_reports_hit_miss_and_probability_metrics_without_ungraded_picks() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    time = datetime(2026, 4, 1, tzinfo=timezone.utc)
    with Session(engine) as session:
        session.add(MlbGame(id=1, game_date=time, official_date=date(2026, 4, 1), home_team="Home", away_team="Away", status="final"))
        session.add_all([
            MlbHrPrediction(game_id=1, player_id=1, model_version="v1", timestamp=time, first_pitch=time, probability=.25, result="HIT"),
            MlbHrPrediction(game_id=1, player_id=2, model_version="v1", timestamp=time, first_pitch=time, probability=.10, result="MISS"),
            MlbHrPrediction(game_id=1, player_id=3, model_version="v2", timestamp=time, first_pitch=time, probability=.20),
        ])
        session.commit()
        report = hr_performance(session)
        assert report["overall"]["predictions"] == 2
        assert report["overall"]["hits"] == 1
        assert report["overall"]["hit_rate"] == .5
        assert round(report["overall"]["brier_score"], 4) == .2863
        assert len(report["by_model_version"]) == 1
