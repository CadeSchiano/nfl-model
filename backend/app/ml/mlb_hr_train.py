"""Chronologically safe training for the MLB home-run probability model."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mlb import MlbBatterFeature, MlbGame, MlbModelVersion, MlbPlayerGame


FEATURE_COLUMNS = ["prior_games", "prior_plate_appearances", "prior_home_runs", "hr_per_plate_appearance"]


def train_hr_model(session: Session, model_directory: Path, training_timestamp: datetime | None = None) -> MlbModelVersion:
    """Train and save a new immutable model version from games complete before now."""
    training_timestamp = training_timestamp or datetime.now(timezone.utc)
    rows = session.execute(
        select(MlbBatterFeature, MlbPlayerGame, MlbGame.game_date)
        .join(MlbPlayerGame, (MlbPlayerGame.game_id == MlbBatterFeature.game_id) & (MlbPlayerGame.player_id == MlbBatterFeature.player_id))
        .join(MlbGame, MlbGame.id == MlbBatterFeature.game_id)
        .where(MlbGame.status == "final", MlbGame.game_date < training_timestamp)
        .order_by(MlbGame.game_date, MlbBatterFeature.id)
    ).all()
    if len(rows) < 50:
        raise ValueError("need at least 50 completed batter-game rows before training")

    data = pd.DataFrame([
        {**{column: getattr(feature, column) for column in FEATURE_COLUMNS}, "target": int(player_game.home_runs > 0), "game_date": game_date}
        for feature, player_game, game_date in rows
    ])
    if data["target"].nunique() < 2:
        raise ValueError("training data must contain both HR and non-HR outcomes")

    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(max_iter=1000, random_state=0)),
    ])
    model.fit(data[FEATURE_COLUMNS], data["target"])
    last_game = data["game_date"].max()
    version = f"mlb_hr_{training_timestamp.strftime('%Y%m%dT%H%M%SZ')}"
    model_directory.mkdir(parents=True, exist_ok=True)
    artifact = model_directory / f"{version}.joblib"
    joblib.dump({"model": model, "features": FEATURE_COLUMNS, "trained_at": training_timestamp.isoformat()}, artifact)
    record = MlbModelVersion(
        version=version,
        trained_at=training_timestamp,
        training_data_through=last_game,
        artifact_path=str(artifact),
    )
    session.add(record)
    session.commit()
    return record
