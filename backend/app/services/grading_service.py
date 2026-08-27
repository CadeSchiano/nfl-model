"""Automatic, immutable grading for completed V0.1 predictions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.game import Game
from app.models.prediction import Prediction, Result


def grade_moneyline(home_probability: float, home_score: int, away_score: int) -> str:
    if home_score == away_score:
        return "PUSH"
    predicted_home = home_probability >= 0.5
    actual_home = home_score > away_score
    return "WIN" if predicted_home == actual_home else "LOSS"


def grade_spread(home_spread: float, actual_home_margin: float) -> str:
    outcome = actual_home_margin + home_spread
    if outcome == 0:
        return "PUSH"
    return "WIN" if outcome > 0 else "LOSS"


def grade_completed_predictions(session: Session) -> int:
    """Create results once for finished games; never replace an existing grade."""
    rows = session.execute(
        select(Prediction, Game)
        .join(Game)
        .outerjoin(Result, Result.prediction_id == Prediction.id)
        .where(Game.home_score.is_not(None), Game.away_score.is_not(None), Result.prediction_id.is_(None))
    ).all()
    for prediction, game in rows:
        margin = game.home_score - game.away_score
        session.add(Result(
            prediction_id=prediction.id,
            moneyline_result=grade_moneyline(prediction.home_win_probability, game.home_score, game.away_score),
            spread_result=grade_spread(prediction.market_spread, margin) if prediction.market_spread is not None else None,
            actual_margin=margin,
            closing_spread=prediction.market_spread,
        ))
    session.commit()
    return len(rows)
