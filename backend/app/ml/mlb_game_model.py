"""Leakage-safe MLB game winner and margin model."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path

import joblib
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mlb import MlbGame, MlbGameModelVersion, MlbGamePrediction


GAME_FEATURES = ["home_win_rate", "away_win_rate", "home_avg_margin", "away_avg_margin"]
TEAM_WINDOW = 30


def train_game_model(session: Session, model_directory: Path, training_timestamp: datetime | None = None) -> MlbGameModelVersion:
    training_timestamp = training_timestamp or datetime.now(timezone.utc)
    games = session.scalars(select(MlbGame).where(MlbGame.status == "final", MlbGame.home_score.is_not(None), MlbGame.away_score.is_not(None), MlbGame.game_date < training_timestamp).order_by(MlbGame.game_date, MlbGame.id)).all()
    data = historical_game_features(games)
    if len(data) < 100 or data.home_win.nunique() < 2:
        raise ValueError("need at least 100 completed MLB games with both win outcomes")
    win_model = _pipeline(LogisticRegression(max_iter=1000, random_state=0))
    margin_model = _pipeline(Ridge(alpha=10.0))
    win_model.fit(data[GAME_FEATURES], data.home_win)
    margin_model.fit(data[GAME_FEATURES], data.home_margin)
    version = f"mlb_game_{training_timestamp.strftime('%Y%m%dT%H%M%SZ')}"
    model_directory.mkdir(parents=True, exist_ok=True)
    artifact = model_directory / f"{version}.joblib"
    joblib.dump({"win_model": win_model, "margin_model": margin_model, "features": GAME_FEATURES}, artifact)
    record = MlbGameModelVersion(version=version, trained_at=training_timestamp, training_data_through=data.game_date.max(), artifact_path=str(artifact))
    session.add(record)
    session.commit()
    return record


def publish_game_predictions(session: Session, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    version = session.scalar(select(MlbGameModelVersion).order_by(MlbGameModelVersion.trained_at.desc()))
    if version is None or not Path(version.artifact_path).exists():
        raise ValueError("train an MLB game model before publishing predictions")
    payload = joblib.load(version.artifact_path)
    games = session.scalars(select(MlbGame).where(MlbGame.status == "scheduled", MlbGame.game_date > now).order_by(MlbGame.game_date)).all()
    history = _team_history(session.scalars(select(MlbGame).where(MlbGame.status == "final", MlbGame.game_date < now).order_by(MlbGame.game_date, MlbGame.id)).all())
    created = 0
    for game in games:
        if session.scalar(select(MlbGamePrediction.id).where(MlbGamePrediction.game_id == game.id)):
            continue
        features = matchup_features(history, game.home_team, game.away_team)
        input_frame = pd.DataFrame([features])[payload["features"]]
        home_probability = float(payload["win_model"].predict_proba(input_frame)[:, 1][0])
        margin = float(payload["margin_model"].predict(input_frame)[0])
        session.add(MlbGamePrediction(game_id=game.id, model_version=version.version, timestamp=now, home_win_probability=home_probability, away_win_probability=1 - home_probability, predicted_home_margin=margin))
        created += 1
    session.commit()
    return created


def historical_game_features(games: list[MlbGame]) -> pd.DataFrame:
    history: dict[str, deque[tuple[int, float]]] = defaultdict(lambda: deque(maxlen=TEAM_WINDOW))
    rows = []
    for _, group in groupby(games, key=lambda game: game.game_date):
        batch = list(group)
        for game in batch:
            rows.append({**matchup_features(history, game.home_team, game.away_team), "game_date": game.game_date, "home_win": int(game.home_score > game.away_score), "home_margin": game.home_score - game.away_score})
        for game in batch:
            margin = game.home_score - game.away_score
            history[game.home_team].append((int(margin > 0), margin))
            history[game.away_team].append((int(margin < 0), -margin))
    return pd.DataFrame(rows)


def matchup_features(history: dict[str, deque[tuple[int, float]]], home_team: str, away_team: str) -> dict[str, float]:
    def team_values(team: str) -> tuple[float, float]:
        values = history[team]
        if not values:
            return .5, 0.0
        return sum(win for win, _ in values) / len(values), sum(margin for _, margin in values) / len(values)
    home_win, home_margin = team_values(home_team)
    away_win, away_margin = team_values(away_team)
    return {"home_win_rate": home_win, "away_win_rate": away_win, "home_avg_margin": home_margin, "away_avg_margin": away_margin}


def _team_history(games: list[MlbGame]) -> dict[str, deque[tuple[int, float]]]:
    history: dict[str, deque[tuple[int, float]]] = defaultdict(lambda: deque(maxlen=TEAM_WINDOW))
    for _, group in groupby(games, key=lambda game: game.game_date):
        for game in list(group):
            margin = game.home_score - game.away_score
            history[game.home_team].append((int(margin > 0), margin))
            history[game.away_team].append((int(margin < 0), -margin))
    return history


def _pipeline(model: object) -> Pipeline:
    return Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler()), ("model", model)])
