from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.game import Game
from app.schemas.api import GameRead


router = APIRouter(prefix="/games", tags=["games"])


@router.get("", response_model=list[GameRead])
def list_games(db: Session = Depends(get_db)):
    return db.scalars(select(Game).order_by(Game.date)).all()


@router.get("/current-week", response_model=list[GameRead])
def current_week_games(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    next_game = db.scalar(select(Game).where(Game.date >= now).order_by(Game.date))
    if next_game is None:
        return []
    return db.scalars(select(Game).where(Game.season == next_game.season, Game.week == next_game.week).order_by(Game.date)).all()


@router.get("/{game_id}", response_model=GameRead)
def get_game(game_id: str, db: Session = Depends(get_db)):
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="game not found")
    return game
