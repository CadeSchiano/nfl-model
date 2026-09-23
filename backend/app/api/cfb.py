from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.cfb import CfbGame, CfbTotalPrediction, CfbTotalResult

router = APIRouter(prefix="/cfb", tags=["cfb"])


def _row(prediction, game, result=None):
    return {"id": prediction.id, "away_team": game.away_team, "home_team": game.home_team, "kickoff": game.kickoff, "market_total": prediction.market_total, "projected_total": prediction.projected_total, "edge": prediction.edge, "recommendation": prediction.recommendation, "model_version": prediction.model_version, "result": result.result if result else None, "actual_total": result.actual_total if result else None}


@router.get("/predictions")
def predictions(db: Session = Depends(get_db)):
    rows = db.execute(select(CfbTotalPrediction, CfbGame).join(CfbGame).where(CfbGame.status == "scheduled").order_by(CfbGame.kickoff)).all()
    return [_row(prediction, game) for prediction, game in rows]


@router.get("/history")
def history(db: Session = Depends(get_db)):
    rows = db.execute(select(CfbTotalPrediction, CfbGame, CfbTotalResult).join(CfbGame).join(CfbTotalResult, CfbTotalResult.prediction_id == CfbTotalPrediction.id).order_by(CfbGame.kickoff.desc())).all()
    data = [_row(prediction, game, result) for prediction, game, result in rows]
    actionable = [item for item in data if item["recommendation"] != "PASS"]
    wins = sum(item["result"] == "WIN" for item in actionable); losses = sum(item["result"] == "LOSS" for item in actionable); pushes = sum(item["result"] == "PUSH" for item in actionable)
    weekly: dict[tuple[int, int], dict] = {}
    for prediction, game, result in rows:
        summary = weekly.setdefault((game.season, game.week), {"season": game.season, "week": game.week, "over": {"wins": 0, "losses": 0, "pushes": 0}, "under": {"wins": 0, "losses": 0, "pushes": 0}, "passes": 0})
        if prediction.recommendation == "PASS":
            summary["passes"] += 1
        elif prediction.recommendation in {"OVER", "UNDER"}:
            bucket = summary[prediction.recommendation.lower()]
            if result.result == "WIN": bucket["wins"] += 1
            elif result.result == "LOSS": bucket["losses"] += 1
            elif result.result == "PUSH": bucket["pushes"] += 1
    return {"weekly": sorted(weekly.values(), key=lambda item: (item["season"], item["week"]), reverse=True), "record": {"wins": wins, "losses": losses, "pushes": pushes}}
