"""FBS-only totals training, publishing, and grading."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.cfb_total_model import FEATURES, build_total_features, train_total_model
from app.models.cfb import CfbGame, CfbMarketTotal, CfbTotalPrediction, CfbTotalResult

ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = ROOT / "backend/app/ml/models/cfb/cfb_total_ridge_v1.joblib"


def train_cfb_total_model(session: Session) -> Path:
    games = _games_frame(session)
    return train_total_model(build_total_features(games), MODEL_PATH)


def publish_cfb_total_predictions(session: Session) -> int:
    if not MODEL_PATH.exists():
        raise FileNotFoundError("Train the CFB total model before publishing predictions.")
    games = _games_frame(session)
    features = build_total_features(games).set_index("id")
    artifact = joblib.load(MODEL_PATH)
    added = 0
    scheduled = session.scalars(select(CfbGame).where(CfbGame.status == "scheduled", CfbGame.kickoff > datetime.now(timezone.utc)).order_by(CfbGame.kickoff)).all()
    for game in scheduled:
        if session.scalar(select(CfbTotalPrediction.id).where(CfbTotalPrediction.game_id == game.id)) is not None:
            continue
        market = session.scalar(select(CfbMarketTotal).where(CfbMarketTotal.game_id == game.id).order_by(CfbMarketTotal.timestamp.desc()))
        if market is None or game.id not in features.index:
            continue
        projection = float(artifact["model"].predict(features.loc[[game.id], FEATURES])[0])
        edge = projection - market.total
        recommendation = "OVER" if edge >= 2.0 else "UNDER" if edge <= -2.0 else "PASS"
        session.add(CfbTotalPrediction(game_id=game.id, model_version=artifact["model_version"], timestamp=datetime.now(timezone.utc), market_total=market.total, projected_total=projection, edge=edge, recommendation=recommendation))
        added += 1
    session.commit()
    return added


def grade_cfb_total_predictions(session: Session) -> int:
    rows = session.execute(select(CfbTotalPrediction, CfbGame).join(CfbGame).outerjoin(CfbTotalResult, CfbTotalResult.prediction_id == CfbTotalPrediction.id).where(CfbTotalResult.prediction_id.is_(None), CfbGame.home_score.is_not(None), CfbGame.away_score.is_not(None))).all()
    for prediction, game in rows:
        actual = float(game.home_score + game.away_score)
        result = "PUSH" if actual == prediction.market_total else "WIN" if (prediction.recommendation == "OVER" and actual > prediction.market_total) or (prediction.recommendation == "UNDER" and actual < prediction.market_total) else "LOSS" if prediction.recommendation != "PASS" else "PASS"
        session.add(CfbTotalResult(prediction_id=prediction.id, result=result, actual_total=actual, graded_at=datetime.now(timezone.utc)))
    session.commit()
    return len(rows)


def _games_frame(session: Session) -> pd.DataFrame:
    rows = session.scalars(select(CfbGame).order_by(CfbGame.kickoff)).all()
    return pd.DataFrame([{"id": game.id, "season": game.season, "week": game.week, "kickoff": game.kickoff, "home_team": game.home_team, "away_team": game.away_team, "home_score": game.home_score, "away_score": game.away_score} for game in rows])
