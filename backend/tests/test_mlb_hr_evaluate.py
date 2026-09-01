from datetime import datetime, timedelta, timezone

import pandas as pd

from app.ml.mlb_hr_evaluate import evaluate_observations


def test_window_evaluation_uses_a_chronological_holdout_on_synthetic_data() -> None:
    start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    data = pd.DataFrame([{
        "game_date": start + timedelta(days=index),
        "prior_games": min(index, 30),
        "prior_plate_appearances": min(index, 30) * 4,
        "prior_home_runs": index // 12,
        "hr_per_plate_appearance": (index // 12) / max(index * 4, 1),
        "target": int(index % 9 == 0),
    } for index in range(120)])
    result = evaluate_observations(data, 30)
    assert result["eligible"] is True
    assert result["observations"] == 120
    assert 0 <= result["brier_score"] <= 1
    assert result["log_loss"] > 0
