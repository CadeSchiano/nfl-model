"""V0.1 SQLAlchemy table models."""

from app.models.game import Game, Team
from app.models.odds import Odds
from app.models.prediction import Prediction, Result

__all__ = ["Game", "Odds", "Prediction", "Result", "Team"]
