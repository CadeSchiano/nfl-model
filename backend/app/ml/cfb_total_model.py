"""Leakage-safe FBS total-points projection model."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = ["home_games", "away_games", "home_points_for", "home_points_against", "away_points_for", "away_points_against"]


def build_total_features(games: pd.DataFrame) -> pd.DataFrame:
    ordered = games.sort_values(["season", "week", "kickoff", "id"], kind="stable")
    state = defaultdict(list); previous_season = None; rows = []
    for game in ordered.itertuples(index=False):
        if previous_season is not None and game.season != previous_season:
            state = defaultdict(list)
        previous_season = game.season
        def values(team):
            history = state[team]
            return len(history), (sum(item[0] for item in history) / len(history) if history else 0.0), (sum(item[1] for item in history) / len(history) if history else 0.0)
        home_games, home_for, home_against = values(game.home_team)
        away_games, away_for, away_against = values(game.away_team)
        total = game.home_score + game.away_score if pd.notna(game.home_score) and pd.notna(game.away_score) else None
        rows.append({"id": game.id, "season": game.season, "kickoff": game.kickoff, "final_total": total, "home_games": home_games, "away_games": away_games, "home_points_for": home_for, "home_points_against": home_against, "away_points_for": away_for, "away_points_against": away_against})
        if total is not None:
            state[game.home_team].append((game.home_score, game.away_score))
            state[game.away_team].append((game.away_score, game.home_score))
    return pd.DataFrame(rows)


def train_total_model(features: pd.DataFrame, path: Path) -> Path:
    train = features.dropna(subset=["final_total"])
    if len(train) < 100:
        raise ValueError("CFB totals training requires at least 100 completed FBS games")
    model = Pipeline([("scale", StandardScaler()), ("model", Ridge(alpha=10.0))])
    model.fit(train[FEATURES], train.final_total)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": FEATURES, "training_rows": len(train), "model_version": "cfb_total_ridge_v1"}, path)
    return path
