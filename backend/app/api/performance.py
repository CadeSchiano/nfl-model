import math

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.game import Game
from app.models.prediction import Prediction, Result


router = APIRouter(prefix="/performance", tags=["performance"])


def _completed_predictions(db: Session):
    return db.execute(
        select(Prediction, Game, Result).join(Game).join(Result).where(Game.home_score.is_not(None), Game.away_score.is_not(None))
    ).all()


@router.get("")
def performance(db: Session = Depends(get_db)):
    return {"moneyline": moneyline_performance(db), "spread": spread_performance(db)}


@router.get("/moneyline")
def moneyline_performance(db: Session = Depends(get_db)):
    rows = _completed_predictions(db)
    if not rows:
        return {"games": 0, "accuracy": None, "brier_score": None}
    outcomes = [int(game.home_score > game.away_score) for _, game, _ in rows]
    probabilities = [prediction.home_win_probability for prediction, _, _ in rows]
    calibration = []
    for lower in range(0, 100, 10):
        bucket = [outcome for probability, outcome in zip(probabilities, outcomes) if lower / 100 <= probability < (lower + 10) / 100]
        if bucket:
            calibration.append({"predicted_range": f"{lower}-{lower + 10}%", "actual_home_win_rate": sum(bucket) / len(bucket), "games": len(bucket)})
    return {
        "games": len(rows),
        "accuracy": sum((probability >= 0.5) == outcome for probability, outcome in zip(probabilities, outcomes)) / len(rows),
        "brier_score": sum((probability - outcome) ** 2 for probability, outcome in zip(probabilities, outcomes)) / len(rows),
        "calibration": calibration,
    }


@router.get("/spread")
def spread_performance(db: Session = Depends(get_db)):
    rows = [(prediction, game, result) for prediction, game, result in _completed_predictions(db) if prediction.predicted_margin is not None]
    if not rows:
        return {"games": 0, "mae": None, "rmse": None}
    errors = [prediction.predicted_margin - (game.home_score - game.away_score) for prediction, game, _ in rows]
    ats = [result.spread_result for _, _, result in rows if result.spread_result is not None]
    return {"games": len(rows), "mae": sum(abs(error) for error in errors) / len(rows), "rmse": math.sqrt(sum(error ** 2 for error in errors) / len(rows)), "ats": {"wins": ats.count("WIN"), "losses": ats.count("LOSS"), "pushes": ats.count("PUSH"), "percentage": ats.count("WIN") / (ats.count("WIN") + ats.count("LOSS")) if ats.count("WIN") + ats.count("LOSS") else None}, "hypothetical_roi": None}
