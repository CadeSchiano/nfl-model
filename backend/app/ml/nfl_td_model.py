"""Leakage-safe NFL anytime-touchdown model training."""
from __future__ import annotations
from collections import defaultdict, deque
from pathlib import Path
from datetime import datetime, timezone
import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = ["prior_games", "carries_avg", "targets_avg", "td_rate"]


def build_td_features(players: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    data = players.merge(games[["game_id", "date"]], on="game_id", how="inner").sort_values(["player_id", "date", "game_id"])
    histories = defaultdict(lambda: deque(maxlen=5)); rows = []
    for row in data.itertuples(index=False):
        history = histories[row.player_id]
        rows.append({"date": row.date, "player_id": row.player_id, "team": row.team, "scored_touchdown": row.scored_touchdown, "two_plus_touchdowns": int(getattr(row, "touchdowns", 0) >= 2), "prior_games": len(history), "carries_avg": sum(x[0] for x in history) / len(history) if history else 0., "targets_avg": sum(x[1] for x in history) / len(history) if history else 0., "td_rate": sum(x[2] for x in history) / len(history) if history else 0.})
        history.append((row.carries, row.targets, row.scored_touchdown))
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def train_td_model(features: pd.DataFrame, directory: Path) -> Path:
    cutoff = int(len(features) * .8); train = features.iloc[:cutoff]
    if train.scored_touchdown.nunique() < 2: raise ValueError("TD training requires both outcomes")
    model = Pipeline([("scale", StandardScaler()), ("model", LogisticRegression(max_iter=1000, random_state=0))])
    model.fit(train[FEATURES], train.scored_touchdown)
    two_td_model = Pipeline([("scale", StandardScaler()), ("model", LogisticRegression(max_iter=1000, random_state=0, class_weight="balanced"))])
    two_td_model.fit(train[FEATURES], train.two_plus_touchdowns)
    directory.mkdir(parents=True, exist_ok=True)
    version = f"nfl_td_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    path = directory / f"{version}.joblib"
    joblib.dump({"model": model, "two_td_model": two_td_model, "features": FEATURES, "training_rows": len(train), "model_version": version}, path)
    return path
