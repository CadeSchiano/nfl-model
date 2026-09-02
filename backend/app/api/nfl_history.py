"""Immutable NFL prediction history with grading results."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.game import Game
from app.models.prediction import Prediction, Result

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("/history")
def prediction_history(db: Session = Depends(get_db)):
    rows = db.execute(select(Prediction, Game, Result).join(Game).outerjoin(Result, Result.prediction_id == Prediction.id).order_by(Game.date.desc()).limit(250)).all()
    records = [{"id": prediction.id, "away_team": game.away_team, "home_team": game.home_team, "date": game.date, "home_win_probability": prediction.home_win_probability, "model_version": prediction.model_version, "result": result.moneyline_result if result else None} for prediction, game, result in rows]
    return {"predictions": records, "record": {"wins": sum(item["result"] == "WIN" for item in records), "losses": sum(item["result"] == "LOSS" for item in records), "pushes": sum(item["result"] == "PUSH" for item in records)}}
