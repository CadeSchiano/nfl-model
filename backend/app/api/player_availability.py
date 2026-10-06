"""Manual player OUT/ACTIVE overrides for NFL props and TD publishing."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.game import Game
from app.models.player_availability import NflPlayerAvailability
from app.models.prediction import FirstTouchdownPrediction, TouchdownPrediction

router = APIRouter(prefix="/player-availability", tags=["player availability"])


class PlayerAvailabilityWrite(BaseModel):
    player_id: str
    player_name: str
    team: str


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
