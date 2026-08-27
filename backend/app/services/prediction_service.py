"""Creation-only prediction persistence that enforces kickoff locking."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.game import Game
from app.models.prediction import Prediction


class PredictionLockedError(ValueError):
    pass


def create_prediction(session: Session, prediction: Prediction, now: datetime | None = None) -> Prediction:
    game = session.get(Game, prediction.game_id)
    if game is None:
        raise ValueError("game not found")
    current_time = now or datetime.now(timezone.utc)
    kickoff = game.date if game.date.tzinfo else game.date.replace(tzinfo=timezone.utc)
    if kickoff <= current_time:
        raise PredictionLockedError("predictions cannot be created or changed after kickoff")
    session.add(prediction)
    session.commit()
    session.refresh(prediction)
    return prediction
