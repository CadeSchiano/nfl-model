import json

import pandas as pd

from app.ml.train import (
    FINAL_TEST_SEASONS,
    MODEL_FEATURE_COLUMNS,
    TRAIN_SEASONS,
    VALIDATION_SEASONS,
    chronological_split,
    train_and_evaluate,
)


def feature_table() -> pd.DataFrame:
    rows = []
    for season in (*TRAIN_SEASONS, *VALIDATION_SEASONS, *FINAL_TEST_SEASONS):
        for outcome in (0, 1):
            row = {column: float(outcome + 1) for column in MODEL_FEATURE_COLUMNS}
            row.update(
                {
                    "season": season,
                    "home_win": outcome,
                    "margin": -7.0 if outcome == 0 else 7.0,
                    "home_win_pct": float(outcome),
                    "away_win_pct": float(1 - outcome),
                    "home_moneyline": 120 if outcome == 0 else -140,
                    "away_moneyline": -140 if outcome == 0 else 120,
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)


def test_chronological_split_keeps_final_season_out_of_development() -> None:
    train, validation, final_test = chronological_split(feature_table())

    assert set(train["season"]) == set(TRAIN_SEASONS)
    assert set(validation["season"]) == set(VALIDATION_SEASONS)
    assert set(final_test["season"]) == set(FINAL_TEST_SEASONS)


def test_training_serializes_versioned_selected_models_and_metadata(tmp_path) -> None:
    report = train_and_evaluate(feature_table(), tmp_path)

    assert report["selection"]["moneyline"] == "logistic_v1"
    assert report["selection"]["spread"] in {"spread_linear_v1", "spread_ridge_v1"}
    assert (tmp_path / "logistic_v1.joblib").exists()
    assert (tmp_path / f"{report['selection']['spread']}.joblib").exists()
    assert json.loads((tmp_path / "model_metadata.json").read_text())["split"]["final_test"] == [2025]
