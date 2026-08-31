"""Immutable grading for official MLB home-run predictions."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mlb import MlbGame, MlbHrPrediction, MlbPlayerGame


def grade_completed_hr_predictions(session: Session) -> int:
    """Mark each ungraded pick in a final game HIT or MISS exactly once.

    A player who did not appear is correctly graded MISS.  This updates only the
    grading fields and deliberately preserves the original model version,
    timestamp, and probability.
    """
    rows = session.execute(
        select(MlbHrPrediction, MlbPlayerGame.home_runs)
        .join(MlbGame, MlbGame.id == MlbHrPrediction.game_id)
        .outerjoin(
            MlbPlayerGame,
            (MlbPlayerGame.game_id == MlbHrPrediction.game_id)
            & (MlbPlayerGame.player_id == MlbHrPrediction.player_id),
        )
        .where(MlbGame.status == "final", MlbHrPrediction.result.is_(None))
    ).all()
    graded_at = datetime.now(timezone.utc)
    for prediction, home_runs in rows:
        prediction.result = "HIT" if (home_runs or 0) > 0 else "MISS"
        prediction.graded_at = graded_at
    session.commit()
    return len(rows)
