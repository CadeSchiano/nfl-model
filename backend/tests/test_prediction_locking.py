from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.models.game import Game, Team
from app.models.prediction import Prediction
from app.services.prediction_service import PredictionLockedError, create_prediction


def test_prediction_creation_is_locked_after_kickoff() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([Team(abbreviation="BUF", name="Buffalo Bills"), Team(abbreviation="NYJ", name="New York Jets")])
        session.add(Game(id="past", season=2025, week=1, date=datetime.now(timezone.utc) - timedelta(minutes=1), home_team="BUF", away_team="NYJ", status="completed"))
        session.commit()

        prediction = Prediction(game_id="past", model_version="elo_v1", timestamp=datetime.now(timezone.utc), home_win_probability=0.6, away_win_probability=0.4)
        with pytest.raises(PredictionLockedError):
            create_prediction(session, prediction)
