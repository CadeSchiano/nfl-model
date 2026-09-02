"""Read-only operational status for the isolated MLB workflow."""

from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.mlb import MlbBatterFeature, MlbGame, MlbGamePrediction, MlbHrPrediction, MlbModelVersion, MlbPlayerGame
from app.services.mlb_prediction_service import _pregame_batter_features
from app.services.mlb_performance_service import hr_performance
from app.services.mlb_game_grading_service import game_performance


router = APIRouter(prefix="/mlb", tags=["mlb"])


@router.get("/top-10")
def daily_top_10(db: Session = Depends(get_db)):
    """Today's ten highest official, confirmed-lineup HR probabilities."""
    now = datetime.now(timezone.utc)
    predictions = db.execute(
        select(MlbHrPrediction, MlbGame)
        .join(MlbGame, MlbGame.id == MlbHrPrediction.game_id)
        .where(MlbGame.status == "scheduled", MlbGame.game_date > now)
        .order_by(MlbHrPrediction.probability.desc(), MlbHrPrediction.timestamp)
        .limit(10)
    ).all()
    return [{"player_name": prediction.player_name, "team": prediction.team, "probability": prediction.probability, "model_version": prediction.model_version, "game": f"{game.away_team} @ {game.home_team}", "first_pitch": game.game_date} for prediction, game in predictions]


@router.get("/game-predictions")
def game_predictions(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    rows = db.execute(select(MlbGamePrediction, MlbGame).join(MlbGame, MlbGame.id == MlbGamePrediction.game_id).where(MlbGame.game_date > now).order_by(MlbGame.game_date)).all()
    return [{"game_id": game.id, "away_team": game.away_team, "home_team": game.home_team, "first_pitch": game.game_date, "home_win_probability": prediction.home_win_probability, "away_win_probability": prediction.away_win_probability, "predicted_home_margin": prediction.predicted_home_margin, "market_home_probability": prediction.market_home_probability, "market_spread": prediction.market_spread, "moneyline_difference": prediction.moneyline_difference, "spread_difference": prediction.spread_difference, "model_version": prediction.model_version} for prediction, game in rows]


@router.get("/game-performance")
def mlb_game_performance(db: Session = Depends(get_db)):
    return game_performance(db)


@router.get("/history")
def mlb_history(db: Session = Depends(get_db)):
    """Completed and past-start-time MLB predictions, preserved for review."""
    now = datetime.now(timezone.utc)
    hr_rows = db.execute(select(MlbHrPrediction, MlbGame).join(MlbGame, MlbGame.id == MlbHrPrediction.game_id).where(MlbGame.game_date <= now).order_by(MlbGame.game_date.desc(), MlbHrPrediction.probability.desc()).limit(250)).all()
    game_rows = db.execute(select(MlbGamePrediction, MlbGame).join(MlbGame, MlbGame.id == MlbGamePrediction.game_id).where(MlbGame.game_date <= now).order_by(MlbGame.game_date.desc()).limit(100)).all()
    return {"hr_predictions": [{"id": prediction.id, "player_name": prediction.player_name, "team": prediction.team, "probability": prediction.probability, "result": prediction.result, "game": f"{game.away_team} @ {game.home_team}", "first_pitch": game.game_date, "model_version": prediction.model_version} for prediction, game in hr_rows], "game_predictions": [{"id": prediction.id, "away_team": game.away_team, "home_team": game.home_team, "first_pitch": game.game_date, "home_win_probability": prediction.home_win_probability, "predicted_home_margin": prediction.predicted_home_margin, "model_version": prediction.model_version} for prediction, game in game_rows]}


@router.get("/performance")
def mlb_performance(db: Session = Depends(get_db)):
    return hr_performance(db)


@router.get("/batters")
def search_batters(query: str = Query(min_length=2), db: Session = Depends(get_db)):
    """Search batters from the local completed-game history for the player picker."""
    rows = db.execute(
        select(MlbPlayerGame, MlbGame.game_date)
        .join(MlbGame, MlbGame.id == MlbPlayerGame.game_id)
        .where(MlbGame.status == "final", MlbPlayerGame.plate_appearances.is_not(None), MlbPlayerGame.player_name.ilike(f"%{query}%"))
        .order_by(MlbGame.game_date.desc())
    ).all()
    results, seen = [], set()
    for player_game, _ in rows:
        if player_game.player_id in seen:
            continue
        seen.add(player_game.player_id)
        results.append({"player_id": player_game.player_id, "player_name": player_game.player_name, "team": player_game.team})
        if len(results) == 12:
            break
    return results


@router.get("/batters/{player_id}/projection")
def batter_projection(player_id: int, db: Session = Depends(get_db)):
    """Calculate a non-persisted projection for a searched batter's next game.

    It becomes an official prediction only when the lineup-gated publishing
    script records it before first pitch.
    """
    now = datetime.now(timezone.utc)
    latest_player_game = db.execute(
        select(MlbPlayerGame, MlbGame.game_date)
        .join(MlbGame, MlbGame.id == MlbPlayerGame.game_id)
        .where(MlbPlayerGame.player_id == player_id, MlbGame.status == "final")
        .order_by(MlbGame.game_date.desc())
    ).first()
    if latest_player_game is None:
        raise HTTPException(status_code=404, detail="batter not found")
    player_game, _ = latest_player_game
    game = db.scalar(
        select(MlbGame)
        .where(
            MlbGame.status == "scheduled",
            MlbGame.game_date > now,
            (MlbGame.home_team == player_game.team) | (MlbGame.away_team == player_game.team),
        )
        .order_by(MlbGame.game_date)
    )
    if game is None:
        return {"available": False, "player_name": player_game.player_name, "team": player_game.team, "message": "No upcoming scheduled game was found for this batter."}
    model_version = db.scalar(select(MlbModelVersion).order_by(MlbModelVersion.trained_at.desc()))
    if model_version is None or not Path(model_version.artifact_path).exists():
        return {"available": False, "player_name": player_game.player_name, "team": player_game.team, "message": "No local MLB model artifact is available yet."}
    features = _pregame_batter_features(db, player_id, game.game_date)
    if features["prior_games"] == 0:
        return {"available": False, "player_name": player_game.player_name, "team": player_game.team, "message": "This batter has no completed-game history for a projection yet."}
    artifact = joblib.load(model_version.artifact_path)
    probability = float(artifact["model"].predict_proba(pd.DataFrame([features])[artifact["features"]])[:, 1][0])
    return {
        "available": True,
        "official": False,
        "player_name": player_game.player_name,
        "team": player_game.team,
        "probability": probability,
        "game": {"id": game.id, "away_team": game.away_team, "home_team": game.home_team, "first_pitch": game.game_date},
        "model_version": model_version.version,
    }


@router.get("/status")
def mlb_status(db: Session = Depends(get_db)):
    """Return MLB-only ingestion, model, and prediction state for the dashboard."""
    latest_game = db.scalar(select(MlbGame).where(MlbGame.status == "final").order_by(MlbGame.game_date.desc()))
    scheduled_games = db.scalars(select(MlbGame).where(MlbGame.status == "scheduled", MlbGame.game_date > datetime.now(timezone.utc)).order_by(MlbGame.game_date)).all()
    models = db.scalars(select(MlbModelVersion).order_by(MlbModelVersion.trained_at.desc())).all()
    predictions = db.scalars(
        select(MlbHrPrediction).order_by(MlbHrPrediction.timestamp.desc()).limit(50)
    ).all()
    return {
        "completed_games": db.scalar(select(func.count()).select_from(MlbGame).where(MlbGame.status == "final")) or 0,
        "player_game_rows": db.scalar(select(func.count()).select_from(MlbPlayerGame)) or 0,
        "feature_rows": db.scalar(select(func.count()).select_from(MlbBatterFeature)) or 0,
        "latest_completed_game": latest_game.game_date if latest_game else None,
        "scheduled_games": [
            {
                "id": game.id,
                "away_team": game.away_team,
                "home_team": game.home_team,
                "first_pitch": game.game_date,
                "probable_away_pitcher": game.probable_away_pitcher,
                "probable_home_pitcher": game.probable_home_pitcher,
            }
            for game in scheduled_games
        ],
        "models": [
            {
                "version": model.version,
                "trained_at": model.trained_at,
                "training_data_through": model.training_data_through,
            }
            for model in models
        ],
        "predictions": [
            {
                "id": prediction.id,
                "game_id": prediction.game_id,
                "player_id": prediction.player_id,
                "player_name": prediction.player_name,
                "team": prediction.team,
                "model_version": prediction.model_version,
                "timestamp": prediction.timestamp,
                "first_pitch": prediction.first_pitch,
                "probability": prediction.probability,
                "result": prediction.result,
            }
            for prediction in predictions
        ],
    }
