from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.game import Game
from app.models.prediction import Prediction
from app.schemas.api import PredictionRead


router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("", response_model=list[PredictionRead])
def list_predictions(db: Session = Depends(get_db)):
    return db.scalars(select(Prediction).order_by(Prediction.timestamp.desc())).all()


@router.get("/current-week", response_model=list[PredictionRead])
def current_week_predictions(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    next_game = db.scalar(select(Game).where(Game.date >= now).order_by(Game.date))
    if next_game is None:
        return []
    statement = select(Prediction).join(Game).where(Game.season == next_game.season, Game.week == next_game.week)
    return db.scalars(statement.order_by(Prediction.timestamp.desc())).all()


@router.get("/{game_id}", response_model=list[PredictionRead])
def game_predictions(game_id: str, db: Session = Depends(get_db)):
    if db.get(Game, game_id) is None:
        raise HTTPException(status_code=404, detail="game not found")
    return db.scalars(select(Prediction).where(Prediction.game_id == game_id).order_by(Prediction.timestamp.desc())).all()
