"""Read-only endpoints for NFL anytime-touchdown predictions and history."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.game import Game
from app.models.prediction import TouchdownPrediction

router = APIRouter(prefix="/touchdowns", tags=["touchdowns"])


def _row(prediction: TouchdownPrediction, game: Game) -> dict:
    return {"id": prediction.id, "game_id": game.id, "away_team": game.away_team, "home_team": game.home_team, "date": game.date, "player_name": prediction.player_name, "team": prediction.team, "probability": prediction.probability, "td_score": prediction.td_score, "two_td_probability": prediction.two_td_probability, "two_td_call": prediction.two_td_call, "result": prediction.result, "model_version": prediction.model_version}


@router.get("/current-week")
def current_week(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    game = db.scalar(select(Game).where(Game.status == "scheduled", Game.date >= now).order_by(Game.date))
    if game is None:
        return []
    rows = db.execute(select(TouchdownPrediction, Game).join(Game).where(Game.season == game.season, Game.week == game.week).order_by(TouchdownPrediction.probability.desc())).all()
    return [_row(prediction, game) for prediction, game in rows]


@router.get("/history")
def history(db: Session = Depends(get_db)):
    rows = db.execute(select(TouchdownPrediction, Game).join(Game).where(TouchdownPrediction.result.is_not(None)).order_by(Game.date.desc(), TouchdownPrediction.probability.desc()).limit(500)).all()
    predictions = [_row(prediction, game) for prediction, game in rows]
    hits = sum(row["result"] == "HIT" for row in predictions)
    misses = sum(row["result"] == "MISS" for row in predictions)
    return {"predictions": predictions, "record": {"hits": hits, "misses": misses, "accuracy": hits / (hits + misses) if hits + misses else None}}
