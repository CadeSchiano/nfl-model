"""NBA moneyline and confirmed-starter projection endpoints."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.nba import NbaGame, NbaGamePrediction, NbaPlayerGame, NbaPlayerPrediction, NbaPlayerPredictionResult, NbaStartingLineup
from app.services.nba_data_service import nba_team_roster

router = APIRouter(prefix="/nba", tags=["nba"])


class StarterWrite(BaseModel):
    game_id: str
    player_id: str
    player_name: str
    team: str


def _game_row(prediction: NbaGamePrediction, game: NbaGame):
    return {"id": prediction.id, "game_id": game.id, "away_team": game.away_team, "home_team": game.home_team, "date": game.game_date, "home_win_probability": prediction.home_win_probability, "away_win_probability": prediction.away_win_probability, "predicted_home_margin": prediction.predicted_home_margin, "model_pick": game.home_team if prediction.home_win_probability >= .5 else game.away_team, "result": prediction.result}


@router.get("/games")
def games(db: Session = Depends(get_db)):
    rows = db.execute(select(NbaGamePrediction, NbaGame).join(NbaGame).where(NbaGame.status == "scheduled", NbaGame.game_date > datetime.now(timezone.utc)).order_by(NbaGame.game_date)).all()
    return [_game_row(prediction, game) for prediction, game in rows]


@router.get("/upcoming-games")
def upcoming_games(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(NbaGame)
        .where(NbaGame.status == "scheduled", NbaGame.game_date > datetime.now(timezone.utc))
        .order_by(NbaGame.game_date)
    ).all()
    return [
        {
            "game_id": game.id,
            "away_team": game.away_team,
            "home_team": game.home_team,
            "date": game.game_date,
        }
        for game in rows
    ]


@router.get("/props")
def props(db: Session = Depends(get_db)):
    rows = db.execute(select(NbaPlayerPrediction, NbaGame).join(NbaGame).where(NbaGame.status == "scheduled", NbaGame.game_date > datetime.now(timezone.utc)).order_by(NbaGame.game_date, NbaPlayerPrediction.team, NbaPlayerPrediction.player_name)).all()
    return [{"id": prediction.id, "game_id": game.id, "away_team": game.away_team, "home_team": game.home_team, "date": game.game_date, "player_name": prediction.player_name, "team": prediction.team, "projected_points": prediction.projected_points, "projected_rebounds": prediction.projected_rebounds, "projected_assists": prediction.projected_assists, "projected_threes": prediction.projected_threes} for prediction, game in rows]


@router.get("/players")
def players(query: str = Query(min_length=2), db: Session = Depends(get_db)):
    rows = db.execute(select(NbaPlayerGame.player_id, NbaPlayerGame.player_name, NbaPlayerGame.team).where(NbaPlayerGame.player_name.ilike(f"%{query}%")).group_by(NbaPlayerGame.player_id, NbaPlayerGame.player_name, NbaPlayerGame.team).order_by(NbaPlayerGame.player_name).limit(30)).all()
    return [{"player_id": row.player_id, "player_name": row.player_name, "team": row.team} for row in rows]


@router.get("/lineups")
def lineups(db: Session = Depends(get_db)):
    rows = db.execute(select(NbaStartingLineup, NbaGame).join(NbaGame).where(NbaGame.status == "scheduled", NbaGame.game_date > datetime.now(timezone.utc)).order_by(NbaGame.game_date, NbaStartingLineup.team)).all()
    return [{"game_id": game.id, "away_team": game.away_team, "home_team": game.home_team, "date": game.game_date, "player_id": lineup.player_id, "player_name": lineup.player_name, "team": lineup.team} for lineup, game in rows]


@router.get("/rosters/{game_id}")
def rosters(game_id: str, db: Session = Depends(get_db)):
    game = db.get(NbaGame, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="NBA game not found")
    return {"game_id": game.id, "away_team": game.away_team, "home_team": game.home_team, "away": nba_team_roster(game.away_team), "home": nba_team_roster(game.home_team)}


@router.post("/lineups")
def confirm_starter(payload: StarterWrite, db: Session = Depends(get_db)):
    game = db.get(NbaGame, payload.game_id)
    if game is None or game.status != "scheduled" or payload.team not in {game.home_team, game.away_team}:
        raise HTTPException(status_code=400, detail="player team must be in an upcoming NBA game")
    count = db.scalar(select(func.count()).select_from(NbaStartingLineup).where(NbaStartingLineup.game_id == payload.game_id, NbaStartingLineup.team == payload.team))
    exists = db.scalar(select(NbaStartingLineup.id).where(NbaStartingLineup.game_id == payload.game_id, NbaStartingLineup.player_id == payload.player_id))
    if not exists and count >= 5:
        raise HTTPException(status_code=400, detail="a team can have at most five confirmed starters")
    if not exists:
        db.add(NbaStartingLineup(**payload.model_dump(), confirmed_at=datetime.now(timezone.utc)))
        db.commit()
    return {"saved": True}


@router.post("/lineups/toggle")
def toggle_starter(payload: StarterWrite, db: Session = Depends(get_db)):
    game = db.get(NbaGame, payload.game_id)
    if game is None or game.status != "scheduled" or payload.team not in {game.home_team, game.away_team}:
        raise HTTPException(status_code=400, detail="player team must be in an upcoming NBA game")
    existing = db.scalar(select(NbaStartingLineup).where(NbaStartingLineup.game_id == payload.game_id, NbaStartingLineup.player_id == payload.player_id))
    if existing:
        db.delete(existing); db.commit()
        return {"selected": False}
    count = db.scalar(select(func.count()).select_from(NbaStartingLineup).where(NbaStartingLineup.game_id == payload.game_id, NbaStartingLineup.team == payload.team))
    if count >= 5:
        raise HTTPException(status_code=400, detail="a team can have at most five confirmed starters")
    db.add(NbaStartingLineup(**payload.model_dump(), confirmed_at=datetime.now(timezone.utc)))
    db.commit()
    return {"selected": True}


@router.get("/history")
def history(db: Session = Depends(get_db)):
    games = db.execute(select(NbaGamePrediction, NbaGame).join(NbaGame).where(NbaGamePrediction.result.is_not(None)).order_by(NbaGame.game_date.desc()).limit(200)).all()
    players = db.execute(select(NbaPlayerPrediction, NbaGame, NbaPlayerPredictionResult).join(NbaGame).join(NbaPlayerPredictionResult, NbaPlayerPredictionResult.prediction_id == NbaPlayerPrediction.id).order_by(NbaGame.game_date.desc()).limit(500)).all()
    wins = sum(prediction.result == "WIN" for prediction, _ in games); losses = sum(prediction.result == "LOSS" for prediction, _ in games)
    return {"game_record": {"wins": wins, "losses": losses, "accuracy": wins / (wins + losses) if wins + losses else None}, "games": [_game_row(prediction, game) for prediction, game in games], "players": [{"player_name": prediction.player_name, "team": prediction.team, "game_id": game.id, "projected_points": prediction.projected_points, "projected_rebounds": prediction.projected_rebounds, "projected_assists": prediction.projected_assists, "projected_threes": prediction.projected_threes, "actual_points": result.actual_points, "actual_rebounds": result.actual_rebounds, "actual_assists": result.actual_assists, "actual_threes": result.actual_threes} for prediction, game, result in players]}
