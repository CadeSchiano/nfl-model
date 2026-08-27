"""Chronological model and baseline evaluation helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss, mean_absolute_error, root_mean_squared_error


def moneyline_metrics(outcomes: pd.Series, probabilities: np.ndarray) -> dict[str, float]:
    """Return probability-quality metrics for binary home-win outcomes."""
    values = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
    targets = outcomes.to_numpy(dtype=int)
    return {
        "accuracy": float(np.mean((values >= 0.5) == targets)),
        "brier_score": float(brier_score_loss(targets, values)),
        "log_loss": float(log_loss(targets, values, labels=[0, 1])),
    }


def spread_metrics(actual_margins: pd.Series, predicted_margins: np.ndarray) -> dict[str, float]:
    """Return point-differential forecast error metrics."""
    targets = actual_margins.to_numpy(dtype=float)
    predictions = np.asarray(predicted_margins, dtype=float)
    return {
        "mae": float(mean_absolute_error(targets, predictions)),
        "rmse": float(root_mean_squared_error(targets, predictions)),
    }


def baseline_moneyline_metrics(games: pd.DataFrame) -> dict[str, dict[str, float | int]]:
    """Evaluate required categorical winner baselines on a fixed period.

    These are side-selection baselines, not calibrated probability models, so
    reporting Brier score or log loss for their forced 0/1 outputs would be
    misleading. They are compared on accuracy only.
    """
    outcomes = games["home_win"]
    home_prediction = np.ones(len(games), dtype=int)
    record_prediction = (games["home_win_pct"] >= games["away_win_pct"]).to_numpy(dtype=int)
    results: dict[str, dict[str, float | int]] = {
        "always_home": {"accuracy": float(np.mean(home_prediction == outcomes.to_numpy(dtype=int)))},
        "better_record": {"accuracy": float(np.mean(record_prediction == outcomes.to_numpy(dtype=int)))},
    }
    market_games = games.dropna(subset=["home_moneyline", "away_moneyline"])
    if not market_games.empty:
        favorite_prediction = (
            market_games["home_moneyline"] < market_games["away_moneyline"]
        ).to_numpy(dtype=int)
        results["sportsbook_favorite"] = {
            "games": int(len(market_games)),
            "accuracy": float(np.mean(favorite_prediction == market_games["home_win"].to_numpy(dtype=int))),
        }
    return results
