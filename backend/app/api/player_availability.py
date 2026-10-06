"""Manual player OUT/ACTIVE overrides for NFL props and TD publishing."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.game import Game
from app.models.player_availability import NflPlayerAvailability
from app.models.prediction import FirstTouchdownPrediction, TouchdownPrediction
from app.models.qb_starter import NflExpectedQbStarter

router = APIRouter(prefix="/player-availability", tags=["player availability"])


class PlayerAvailabilityWrite(BaseModel):
    player_id: str
    player_name: str
    team: str


class StartingQbWrite(PlayerAvailabilityWrite):
    game_id: str


@router.get("")
def list_overrides(db: Session = Depends(get_db)):
    rows = db.scalars(select(NflPlayerAvailability).where(NflPlayerAvailability.status == "OUT").order_by(NflPlayerAvailability.team, NflPlayerAvailability.player_name)).all()
    return [{"player_id": row.player_id, "player_name": row.player_name, "team": row.team, "status": row.status, "updated_at": row.updated_at} for row in rows]


@router.post("/out")
def mark_out(payload: PlayerAvailabilityWrite, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    record = db.get(NflPlayerAvailability, payload.player_id)
    if record is None:
        db.add(NflPlayerAvailability(player_id=payload.player_id, player_name=payload.player_name, team=payload.team, status="OUT", updated_at=now))
    else:
        record.player_name, record.team, record.status, record.updated_at = payload.player_name, payload.team, "OUT", now
    future_game_ids = select(Game.id).where(Game.status == "scheduled", Game.date >= now)
    db.execute(update(TouchdownPrediction).where(TouchdownPrediction.player_id == payload.player_id, TouchdownPrediction.game_id.in_(future_game_ids), TouchdownPrediction.publication_status == "ACTIVE").values(publication_status="VOID", voided_at=now))
    db.execute(update(FirstTouchdownPrediction).where(FirstTouchdownPrediction.player_id == payload.player_id, FirstTouchdownPrediction.game_id.in_(future_game_ids), FirstTouchdownPrediction.publication_status == "ACTIVE").values(publication_status="VOID", voided_at=now))
    db.commit()
    return {"saved": True, "instruction": "Run TD revalidation to publish any needed replacement."}


@router.post("/active")
def mark_active(payload: PlayerAvailabilityWrite, db: Session = Depends(get_db)):
    record = db.get(NflPlayerAvailability, payload.player_id)
    if record is not None:
        record.status, record.updated_at = "ACTIVE", datetime.now(timezone.utc)
        db.commit()
    return {"saved": True, "instruction": "Run the TD publisher to consider this player again."}


@router.get("/starting-qbs")
def starting_qbs(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    rows = db.scalars(select(NflExpectedQbStarter).join(Game).where(Game.status == "scheduled", Game.date >= now).order_by(Game.date)).all()
    return [{"game_id": row.game_id, "player_id": row.player_id, "player_name": row.player_name, "team": row.team, "updated_at": row.updated_at} for row in rows]


@router.post("/starting-qb")
def set_starting_qb(payload: StartingQbWrite, db: Session = Depends(get_db)):
    game = db.get(Game, payload.game_id)
    if game is None or payload.team not in {game.home_team, game.away_team}:
        raise HTTPException(status_code=400, detail="team must be playing in this game")
    record = db.scalar(select(NflExpectedQbStarter).where(NflExpectedQbStarter.game_id == payload.game_id, NflExpectedQbStarter.team == payload.team))
    values = {"player_id": payload.player_id, "player_name": payload.player_name, "updated_at": datetime.now(timezone.utc)}
    if record is None:
        db.add(NflExpectedQbStarter(game_id=payload.game_id, team=payload.team, **values))
    else:
        for field, value in values.items():
            setattr(record, field, value)
    db.commit()
    return {"saved": True}
