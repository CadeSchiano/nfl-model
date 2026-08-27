"""Prediction helpers for serialized V0.1 model pipelines."""

from __future__ import annotations

import numpy as np
import pandas as pd


def predict_home_win_probability(model: object, features: pd.DataFrame) -> np.ndarray:
    """Return P(home win) from a fitted classifier pipeline."""
    return model.predict_proba(features)[:, 1]


def predict_home_margin(model: object, features: pd.DataFrame) -> np.ndarray:
    """Return expected home score minus away score from a fitted regressor."""
    return model.predict(features)
