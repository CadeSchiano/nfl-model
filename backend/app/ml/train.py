"""Chronological training and selection for the V0.1 moneyline and spread models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.evaluate import baseline_moneyline_metrics, moneyline_metrics, spread_metrics
from app.ml.predict import predict_home_margin, predict_home_win_probability


TRAIN_SEASONS = tuple(range(2015, 2023))
VALIDATION_SEASONS = (2023, 2024)
FINAL_TEST_SEASONS = (2025,)
MODEL_FEATURE_COLUMNS = [
    "home_elo", "away_elo", "elo_diff", "rest_diff", "division_game",
    "home_win_pct", "away_win_pct", "home_point_diff", "away_point_diff",
    "home_points_avg", "away_points_avg", "home_points_allowed_avg", "away_points_allowed_avg",
    "home_ypp", "away_ypp", "home_pass_ypp", "away_pass_ypp", "home_rush_ypp", "away_rush_ypp",
    "home_ypp_allowed", "away_ypp_allowed", "home_pass_ypp_allowed", "away_pass_ypp_allowed",
    "home_rush_ypp_allowed", "away_rush_ypp_allowed", "home_turnover_diff", "away_turnover_diff",
    "home_last3_margin", "away_last3_margin", "home_last5_margin", "away_last5_margin",
]


def chronological_split(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return the fixed, non-random train/validation/final-test partitions."""
    _validate_training_frame(features)
    train = features.loc[features["season"].isin(TRAIN_SEASONS)].copy()
    validation = features.loc[features["season"].isin(VALIDATION_SEASONS)].copy()
    final_test = features.loc[features["season"].isin(FINAL_TEST_SEASONS)].copy()
    if train.empty or validation.empty or final_test.empty:
        raise ValueError("fixed chronological split produced an empty partition")
    return train, validation, final_test


def train_and_evaluate(features: pd.DataFrame, model_directory: Path | None = None) -> dict[str, Any]:
    """Fit simple V0.1 models, select on validation, and report untouched 2025 results.

    The returned final-test metrics are produced once after selection. The saved
    models are then refit on train+validation data for future pregame use.
    """
    train, validation, final_test = chronological_split(features)
    x_train, y_train_win, y_train_margin = _x(train), train["home_win"], train["margin"]
    x_validation, x_test = _x(validation), _x(final_test)

    logistic = _classifier_pipeline()
    logistic.fit(x_train, y_train_win)
    logistic_validation = moneyline_metrics(validation["home_win"], predict_home_win_probability(logistic, x_validation))

    point_candidates = {
        "spread_linear_v1": _linear_pipeline(),
        "spread_ridge_v1": _ridge_pipeline(),
    }
    validation_spread: dict[str, dict[str, float]] = {}
    for version, model in point_candidates.items():
        model.fit(x_train, y_train_margin)
        validation_spread[version] = spread_metrics(validation["margin"], predict_home_margin(model, x_validation))
    selected_spread_version = min(validation_spread, key=lambda version: validation_spread[version]["rmse"])

    final_logistic = _classifier_pipeline().fit(pd.concat([x_train, x_validation]), pd.concat([y_train_win, validation["home_win"]]))
    final_spread = _spread_pipeline(selected_spread_version).fit(
        pd.concat([x_train, x_validation]), pd.concat([y_train_margin, validation["margin"]])
    )
    report: dict[str, Any] = {
        "split": {"train": list(TRAIN_SEASONS), "validation": list(VALIDATION_SEASONS), "final_test": list(FINAL_TEST_SEASONS)},
        "feature_columns": MODEL_FEATURE_COLUMNS,
        "validation": {
            "moneyline": {"logistic_v1": logistic_validation},
            "spread": validation_spread,
            "baselines": baseline_moneyline_metrics(validation),
        },
        "selection": {"moneyline": "logistic_v1", "spread": selected_spread_version},
        "final_test": {
            "moneyline": {"logistic_v1": moneyline_metrics(final_test["home_win"], predict_home_win_probability(final_logistic, x_test))},
            "spread": {selected_spread_version: spread_metrics(final_test["margin"], predict_home_margin(final_spread, x_test))},
            "baselines": baseline_moneyline_metrics(final_test),
        },
    }
    if model_directory is not None:
        _save_models(model_directory, final_logistic, final_spread, report)
    return report


def _validate_training_frame(features: pd.DataFrame) -> None:
    required = {"season", "home_win", "margin", *MODEL_FEATURE_COLUMNS}
    missing = sorted(required.difference(features.columns))
    if missing:
        raise ValueError(f"feature table is missing training columns: {missing}")
    unexpected = sorted(set(features["season"].unique()).difference((*TRAIN_SEASONS, *VALIDATION_SEASONS, *FINAL_TEST_SEASONS)))
    if unexpected:
        raise ValueError(f"feature table contains seasons outside the V0.1 split: {unexpected}")


def _x(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.loc[:, MODEL_FEATURE_COLUMNS].copy()


def _classifier_pipeline() -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(max_iter=1000, random_state=0)),
    ])


def _linear_pipeline() -> Pipeline:
    return Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", LinearRegression())])


def _ridge_pipeline() -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", Ridge(alpha=10.0)),
    ])


def _spread_pipeline(version: str) -> Pipeline:
    if version == "spread_linear_v1":
        return _linear_pipeline()
    if version == "spread_ridge_v1":
        return _ridge_pipeline()
    raise ValueError(f"unknown spread model version: {version}")


def _save_models(directory: Path, moneyline_model: Pipeline, spread_model: Pipeline, report: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    joblib.dump(moneyline_model, directory / "logistic_v1.joblib")
    spread_version = report["selection"]["spread"]
    joblib.dump(spread_model, directory / f"{spread_version}.joblib")
    (directory / "model_metadata.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
