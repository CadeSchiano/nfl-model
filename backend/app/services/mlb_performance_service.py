"""Transparent performance summaries for immutable MLB HR predictions."""

from __future__ import annotations

import math
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mlb import MlbGame, MlbHrPrediction


def hr_performance(session: Session) -> dict:
    """Return calibrated metrics from graded predictions only."""
    rows = session.execute(
        select(MlbHrPrediction, MlbGame.official_date)
        .join(MlbGame, MlbGame.id == MlbHrPrediction.game_id)
        .where(MlbHrPrediction.result.is_not(None))
        .order_by(MlbGame.official_date, MlbHrPrediction.timestamp)
    ).all()
    overall = _metrics([prediction for prediction, _ in rows])
    by_version: dict[str, list[MlbHrPrediction]] = defaultdict(list)
    by_date: dict[str, list[MlbHrPrediction]] = defaultdict(list)
    for prediction, official_date in rows:
        by_version[prediction.model_version].append(prediction)
        by_date[official_date.isoformat()].append(prediction)
    return {
        "overall": overall,
        "by_model_version": [{"model_version": version, **_metrics(predictions)} for version, predictions in sorted(by_version.items())],
        "daily": [{"date": day, **_metrics(predictions)} for day, predictions in sorted(by_date.items(), reverse=True)],
    }


def _metrics(predictions: list[MlbHrPrediction]) -> dict:
    if not predictions:
        return {"predictions": 0, "hits": 0, "misses": 0, "hit_rate": None, "brier_score": None, "log_loss": None}
    outcomes = [int(prediction.result == "HIT") for prediction in predictions]
    probabilities = [prediction.probability for prediction in predictions]
    clipped = [min(max(probability, 1e-15), 1 - 1e-15) for probability in probabilities]
    return {
        "predictions": len(predictions),
        "hits": sum(outcomes),
        "misses": len(outcomes) - sum(outcomes),
        "hit_rate": sum(outcomes) / len(outcomes),
        "brier_score": sum((probability - outcome) ** 2 for probability, outcome in zip(probabilities, outcomes)) / len(outcomes),
        "log_loss": -sum(outcome * math.log(probability) + (1 - outcome) * math.log(1 - probability) for probability, outcome in zip(clipped, outcomes)) / len(outcomes),
    }
