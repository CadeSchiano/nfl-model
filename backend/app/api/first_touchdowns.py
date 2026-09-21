from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.game import Game
from app.models.prediction import FirstTouchdownPrediction

router = APIRouter(prefix="/first-touchdowns", tags=["first touchdowns"])


def _row(prediction: FirstTouchdownPrediction, game: Game):
    return {"id": prediction.id, "player_name": prediction.player_name, "team": prediction.team, "game_id": game.id, "away_team": game.away_team, "home_team": game.home_team, "date": game.date, "anytime_probability": prediction.anytime_probability, "result": prediction.result, "model_version": prediction.model_version}


@router.get("")
def current_week(db: Session = Depends(get_db)):
    next_game = db.scalar(select(Game).where(Game.status == "scheduled", Game.date >= datetime.now(timezone.utc)).order_by(Game.date))
    if next_game is None:
        return []
    rows = db.execute(select(FirstTouchdownPrediction, Game).join(Game).where(Game.season == next_game.season, Game.week == next_game.week).order_by(Game.date)).all()
    return [_row(prediction, game) for prediction, game in rows]


@router.get("/history")
def history(db: Session = Depends(get_db)):
    rows = db.execute(select(FirstTouchdownPrediction, Game).join(Game).where(FirstTouchdownPrediction.result.is_not(None)).order_by(Game.date.desc())).all()
    predictions = [_row(prediction, game) for prediction, game in rows]
    hits = sum(row["result"] == "HIT" for row in predictions)
    return {"predictions": predictions, "record": {"hits": hits, "misses": len(predictions) - hits, "accuracy": hits / len(predictions) if predictions else None}}
