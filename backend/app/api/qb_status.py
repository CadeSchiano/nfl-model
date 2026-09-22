"""Manual QB status input and transparent injury-adjusted previews."""
from datetime import datetime, timezone
import math

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.game import Game
from app.models.prediction import Prediction
from app.models.qb_status import NflQbStatus
from app.schemas.api import QbStatusWrite

router = APIRouter(prefix="/qb-status", tags=["qb status"])


@router.get("/current-week")
def current_week(db: Session = Depends(get_db)):
    next_game = db.scalar(select(Game).where(Game.status == "scheduled", Game.date >= datetime.now(timezone.utc)).order_by(Game.date))
    if next_game is None:
        return []
    games = db.scalars(select(Game).where(Game.season == next_game.season, Game.week == next_game.week).order_by(Game.date)).all()
    result = []
    for game in games:
        prediction = db.scalar(select(Prediction).where(Prediction.game_id == game.id).order_by(Prediction.timestamp.desc()))
        statuses = db.scalars(select(NflQbStatus).where(NflQbStatus.game_id == game.id)).all()
        by_team = {status.team: status for status in statuses}
        home_adjustment = by_team.get(game.home_team).adjustment_points if game.home_team in by_team else 0.0
        away_adjustment = by_team.get(game.away_team).adjustment_points if game.away_team in by_team else 0.0
        adjusted_margin = prediction.predicted_margin + home_adjustment - away_adjustment if prediction and prediction.predicted_margin is not None else None
        adjusted_probability = _adjust_probability(prediction.home_win_probability, home_adjustment - away_adjustment) if prediction else None
        result.append({"game_id": game.id, "away_team": game.away_team, "home_team": game.home_team, "date": game.date, "home_status": _status_row(by_team.get(game.home_team)), "away_status": _status_row(by_team.get(game.away_team)), "base_home_probability": prediction.home_win_probability if prediction else None, "adjusted_home_probability": adjusted_probability, "base_margin": prediction.predicted_margin if prediction else None, "adjusted_margin": adjusted_margin})
    return result


@router.post("")
def save_status(payload: QbStatusWrite, db: Session = Depends(get_db)):
    game = db.get(Game, payload.game_id)
    if game is None or payload.team not in {game.home_team, game.away_team}:
        raise HTTPException(status_code=400, detail="team must be a participant in the selected game")
    status = db.scalar(select(NflQbStatus).where(NflQbStatus.game_id == payload.game_id, NflQbStatus.team == payload.team))
    values = payload.model_dump() | {"updated_at": datetime.now(timezone.utc)}
    if status is None:
        status = NflQbStatus(**values); db.add(status)
    else:
        for field, value in values.items(): setattr(status, field, value)
    db.commit()
    return {"saved": True}


def _status_row(status: NflQbStatus | None):
    return {"player_name": status.player_name, "status": status.status, "adjustment_points": status.adjustment_points, "updated_at": status.updated_at} if status else {"player_name": None, "status": "healthy", "adjustment_points": 0.0, "updated_at": None}


def _adjust_probability(probability: float, point_adjustment: float) -> float:
    """Convert a manual margin adjustment to a small, explicit probability shift."""
    clipped = min(max(probability, 0.001), 0.999)
    logit = math.log(clipped / (1 - clipped))
    return 1 / (1 + math.exp(-(logit + point_adjustment / 6.5)))
