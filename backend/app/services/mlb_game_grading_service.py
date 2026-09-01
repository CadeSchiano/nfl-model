"""Immutable grading and performance for MLB game predictions."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mlb import MlbGame, MlbGamePrediction, MlbGamePredictionResult


def grade_game_predictions(session: Session) -> int:
    rows = session.execute(select(MlbGamePrediction, MlbGame).join(MlbGame).outerjoin(MlbGamePredictionResult, MlbGamePredictionResult.prediction_id == MlbGamePrediction.id).where(MlbGame.status == "final", MlbGamePredictionResult.prediction_id.is_(None))).all()
    for prediction, game in rows:
        actual = game.home_score - game.away_score
        predicted_home = prediction.home_win_probability >= .5
        actual_home = actual > 0
        session.add(MlbGamePredictionResult(prediction_id=prediction.id, winner_result="WIN" if predicted_home == actual_home else "LOSS", actual_home_margin=actual, graded_at=datetime.now(timezone.utc)))
    session.commit()
    return len(rows)


def game_performance(session: Session) -> dict:
    rows = session.execute(select(MlbGamePrediction, MlbGamePredictionResult).join(MlbGamePredictionResult, MlbGamePredictionResult.prediction_id == MlbGamePrediction.id)).all()
    if not rows:
        return {"games": 0, "accuracy": None, "brier_score": None, "margin_mae": None, "margin_rmse": None}
    outcomes = [int(result.actual_home_margin > 0) for _, result in rows]
    probabilities = [prediction.home_win_probability for prediction, _ in rows]
    errors = [prediction.predicted_home_margin - result.actual_home_margin for prediction, result in rows]
    return {"games": len(rows), "accuracy": sum((probability >= .5) == outcome for probability, outcome in zip(probabilities, outcomes)) / len(rows), "brier_score": sum((probability - outcome) ** 2 for probability, outcome in zip(probabilities, outcomes)) / len(rows), "margin_mae": sum(abs(error) for error in errors) / len(errors), "margin_rmse": math.sqrt(sum(error ** 2 for error in errors) / len(errors))}
