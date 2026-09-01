"""Chronological rolling-window selection for the MLB HR model."""

from __future__ import annotations

from collections import defaultdict, deque

import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.mlb_hr_train import FEATURE_COLUMNS
from app.models.mlb import MlbGame, MlbPlayerGame


WINDOWS = (15, 25, 30, 40, 60)


def evaluate_rolling_windows(session: Session, windows: tuple[int, ...] = WINDOWS) -> list[dict]:
    """Compare windows using a train-past/test-future split with no leakage."""
    source = session.execute(
        select(MlbPlayerGame, MlbGame.game_date)
        .join(MlbGame, MlbGame.id == MlbPlayerGame.game_id)
        .where(MlbGame.status == "final", MlbPlayerGame.plate_appearances.is_not(None))
        .order_by(MlbPlayerGame.player_id, MlbGame.game_date, MlbPlayerGame.game_id)
    ).all()
    return [_evaluate_window(source, window) for window in windows]


def _evaluate_window(source: list[tuple[MlbPlayerGame, object]], window: int) -> dict:
    histories: dict[int, deque[tuple[int, int]]] = defaultdict(lambda: deque(maxlen=window))
    observations = []
    for player_game, game_date in source:
        history = histories[player_game.player_id]
        pa = sum(item_pa for _, item_pa in history)
        hr = sum(item_hr for item_hr, _ in history)
        observations.append({
            "game_date": game_date,
            "prior_games": len(history),
            "prior_plate_appearances": pa,
            "prior_home_runs": hr,
            "hr_per_plate_appearance": hr / pa if pa else 0.0,
            "target": int(player_game.home_runs > 0),
        })
        history.append((player_game.home_runs, player_game.plate_appearances or 0))
    return evaluate_observations(pd.DataFrame(observations), window)


def evaluate_observations(data: pd.DataFrame, window: int) -> dict:
    """Evaluate precomputed observations; exposed for deterministic unit tests."""
    data = data.sort_values("game_date").reset_index(drop=True)
    cutoff = int(len(data) * .8)
    train, test = data.iloc[:cutoff], data.iloc[cutoff:]
    if len(train) < 50 or len(test) < 20 or train.target.nunique() < 2 or test.target.nunique() < 2:
        return {"window": window, "eligible": False, "observations": len(data), "brier_score": None, "log_loss": None}
    model = Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler()), ("model", LogisticRegression(max_iter=1000, random_state=0))])
    model.fit(train[FEATURE_COLUMNS], train.target)
    probabilities = model.predict_proba(test[FEATURE_COLUMNS])[:, 1]
    return {"window": window, "eligible": True, "observations": len(data), "brier_score": float(brier_score_loss(test.target, probabilities)), "log_loss": float(log_loss(test.target, probabilities))}
