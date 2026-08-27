from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.game import Game
from app.models.odds import Odds
from app.schemas.api import OddsRead


router = APIRouter(prefix="/odds", tags=["odds"])


@router.get("/{game_id}", response_model=list[OddsRead])
def game_odds(game_id: str, db: Session = Depends(get_db)):
    if db.get(Game, game_id) is None:
        raise HTTPException(status_code=404, detail="game not found")
    return db.scalars(select(Odds).where(Odds.game_id == game_id).order_by(Odds.timestamp.desc())).all()
