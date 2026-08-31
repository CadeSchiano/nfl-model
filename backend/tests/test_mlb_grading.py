from datetime import date, datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.models.mlb import MlbGame, MlbHrPrediction, MlbPlayerGame
from app.services.mlb_grading_service import grade_completed_hr_predictions


def test_grades_only_final_ungraded_predictions_without_changing_original_pick() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    timestamp = datetime(2026, 8, 30, 18, tzinfo=timezone.utc)
    with Session(engine) as session:
        session.add_all([
            MlbGame(id=1, game_date=timestamp, official_date=date(2026, 8, 30), home_team="Home", away_team="Away", status="final"),
            MlbGame(id=2, game_date=timestamp, official_date=date(2026, 8, 30), home_team="Home", away_team="Away", status="scheduled"),
            MlbPlayerGame(game_id=1, player_id=10, player_name="Homer", team="Home", appeared=True, home_runs=1),
            MlbHrPrediction(game_id=1, player_id=10, model_version="hr_v1", timestamp=timestamp, first_pitch=timestamp, probability=.18),
            MlbHrPrediction(game_id=1, player_id=11, model_version="hr_v1", timestamp=timestamp, first_pitch=timestamp, probability=.12),
            MlbHrPrediction(game_id=2, player_id=12, model_version="hr_v1", timestamp=timestamp, first_pitch=timestamp, probability=.15),
        ])
        session.commit()

        assert grade_completed_hr_predictions(session) == 2
        predictions = {prediction.player_id: prediction for prediction in session.query(MlbHrPrediction).all()}
        assert predictions[10].result == "HIT"
        assert predictions[11].result == "MISS"  # did not appear
        assert predictions[12].result is None
        assert predictions[10].model_version == "hr_v1"
        assert predictions[10].probability == .18
        assert grade_completed_hr_predictions(session) == 0
