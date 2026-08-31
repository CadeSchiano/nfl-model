"""Read-only operational status for the isolated MLB workflow."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.mlb import MlbBatterFeature, MlbGame, MlbHrPrediction, MlbModelVersion, MlbPlayerGame


router = APIRouter(prefix="/mlb", tags=["mlb"])


@router.get("/status")
def mlb_status(db: Session = Depends(get_db)):
    """Return MLB-only ingestion, model, and prediction state for the dashboard."""
    latest_game = db.scalar(select(MlbGame).where(MlbGame.status == "final").order_by(MlbGame.game_date.desc()))
    models = db.scalars(select(MlbModelVersion).order_by(MlbModelVersion.trained_at.desc())).all()
    predictions = db.scalars(
        select(MlbHrPrediction).order_by(MlbHrPrediction.timestamp.desc()).limit(50)
    ).all()
    return {
        "completed_games": db.scalar(select(func.count()).select_from(MlbGame).where(MlbGame.status == "final")) or 0,
        "player_game_rows": db.scalar(select(func.count()).select_from(MlbPlayerGame)) or 0,
        "feature_rows": db.scalar(select(func.count()).select_from(MlbBatterFeature)) or 0,
        "latest_completed_game": latest_game.game_date if latest_game else None,
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
                "model_version": prediction.model_version,
                "timestamp": prediction.timestamp,
                "first_pitch": prediction.first_pitch,
                "probability": prediction.probability,
                "result": prediction.result,
            }
            for prediction in predictions
        ],
    }
