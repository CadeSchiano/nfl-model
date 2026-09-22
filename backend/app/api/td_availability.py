"""Manual confirmed-inactive input for pre-kickoff TD replacement publishing."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.game import Game
from app.models.prediction import TouchdownPrediction
from app.models.td_availability import NflTdAvailability

router = APIRouter(prefix="/td-availability", tags=["td availability"])


class AvailabilityWrite(BaseModel):
    prediction_id: int


@router.get("/current-week")
def current_week(db: Session = Depends(get_db)):
    next_game = db.scalar(select(Game).where(Game.status == "scheduled", Game.date >= datetime.now(timezone.utc)).order_by(Game.date))
    if next_game is None:
        return []
    rows = db.execute(select(TouchdownPrediction, Game).join(Game).where(Game.season == next_game.season, Game.week == next_game.week, TouchdownPrediction.publication_status == "ACTIVE").order_by(Game.date, TouchdownPrediction.probability.desc())).all()
    return [{"prediction_id": prediction.id, "game_id": game.id, "away_team": game.away_team, "home_team": game.home_team, "player_id": prediction.player_id, "player_name": prediction.player_name, "team": prediction.team, "probability": prediction.probability} for prediction, game in rows]


@router.post("/out")
def mark_out(payload: AvailabilityWrite, db: Session = Depends(get_db)):
    prediction = db.get(TouchdownPrediction, payload.prediction_id)
    if prediction is None or prediction.publication_status != "ACTIVE":
        raise HTTPException(status_code=400, detail="select an active touchdown prediction")
    record = db.scalar(select(NflTdAvailability).where(NflTdAvailability.game_id == prediction.game_id, NflTdAvailability.player_id == prediction.player_id))
    if record is None:
        db.add(NflTdAvailability(game_id=prediction.game_id, player_id=prediction.player_id, player_name=prediction.player_name, team=prediction.team, status="OUT", updated_at=datetime.now(timezone.utc)))
    else:
        record.status, record.updated_at = "OUT", datetime.now(timezone.utc)
    prediction.publication_status, prediction.voided_at = "VOID", datetime.now(timezone.utc)
    db.commit()
    return {"saved": True, "instruction": "Run the TD revalidation script to publish a replacement."}
