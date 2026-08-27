import math

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.game import Game
from app.models.prediction import Prediction


router = APIRouter(prefix="/performance", tags=["performance"])


def _completed_predictions(db: Session):
    return db.execute(
        select(Prediction, Game).join(Game).where(Game.home_score.is_not(None), Game.away_score.is_not(None))
    ).all()


@router.get("")
def performance(db: Session = Depends(get_db)):
    return {"moneyline": moneyline_performance(db), "spread": spread_performance(db)}


@router.get("/moneyline")
def moneyline_performance(db: Session = Depends(get_db)):
    rows = _completed_predictions(db)
    if not rows:
        return {"games": 0, "accuracy": None, "brier_score": None}
    outcomes = [int(game.home_score > game.away_score) for _, game in rows]
    probabilities = [prediction.home_win_probability for prediction, _ in rows]
    return {
        "games": len(rows),
        "accuracy": sum((probability >= 0.5) == outcome for probability, outcome in zip(probabilities, outcomes)) / len(rows),
        "brier_score": sum((probability - outcome) ** 2 for probability, outcome in zip(probabilities, outcomes)) / len(rows),
    }


@router.get("/spread")
def spread_performance(db: Session = Depends(get_db)):
    rows = [(prediction, game) for prediction, game in _completed_predictions(db) if prediction.predicted_margin is not None]
    if not rows:
        return {"games": 0, "mae": None, "rmse": None}
    errors = [prediction.predicted_margin - (game.home_score - game.away_score) for prediction, game in rows]
    return {"games": len(rows), "mae": sum(abs(error) for error in errors) / len(rows), "rmse": math.sqrt(sum(error ** 2 for error in errors) / len(rows))}
