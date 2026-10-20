"""Leakage-safe NBA moneyline and confirmed-starter stat projections."""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.nba import NbaGame, NbaGamePrediction, NbaPlayerGame, NbaPlayerPrediction, NbaPlayerPredictionResult, NbaStartingLineup

GAME_MODEL_VERSION = "nba_rolling_moneyline_v1"
PLAYER_MODEL_VERSION = "nba_confirmed_starter_v1"


def publish_nba_game_predictions(session: Session) -> int:
    games = session.scalars(select(NbaGame).where(NbaGame.status == "scheduled", NbaGame.game_date > datetime.now(timezone.utc)).order_by(NbaGame.game_date)).all()
    added = 0
    for game in games:
        if session.scalar(select(NbaGamePrediction.id).where(NbaGamePrediction.game_id == game.id)):
            continue
        home_margin, home_games = _team_margin(session, game.home_team, game.game_date)
        away_margin, away_games = _team_margin(session, game.away_team, game.game_date)
        # Conservative prior early in a season; home court is explicitly modeled.
        expected_margin = 2.2 + home_margin - away_margin
        probability = 1 / (1 + math.exp(-expected_margin / 11.0))
        session.add(NbaGamePrediction(game_id=game.id, model_version=GAME_MODEL_VERSION, timestamp=datetime.now(timezone.utc), home_win_probability=probability, away_win_probability=1 - probability, predicted_home_margin=expected_margin))
        added += 1
    session.commit(); return added


def publish_nba_player_predictions(session: Session) -> int:
    """Publish only confirmed-starter props for today and tomorrow (Eastern Time)."""
    now = datetime.now(timezone.utc)
    cutoff = _starter_prediction_cutoff(now)
    lineups = session.execute(select(NbaStartingLineup, NbaGame).join(NbaGame).where(NbaGame.status == "scheduled", NbaGame.game_date > now, NbaGame.game_date < cutoff)).all()
    added = 0
    for lineup, game in lineups:
        if session.scalar(select(NbaPlayerPrediction.id).where(NbaPlayerPrediction.game_id == game.id, NbaPlayerPrediction.player_id == lineup.player_id)):
            continue
        history = session.execute(select(NbaPlayerGame, NbaGame).join(NbaGame).where(NbaPlayerGame.player_id == lineup.player_id, NbaGame.status == "final", NbaGame.game_date < game.game_date).order_by(NbaGame.game_date.desc()).limit(10)).all()
        if not history:
            continue
        player_games = [row[0] for row in history]
        average_minutes = sum(row.minutes for row in player_games) / len(player_games)
        expected_minutes = min(38.0, max(28.0, average_minutes))
        factor = expected_minutes / max(average_minutes, 1.0)
        def projected(name: str) -> float: return round(sum(getattr(row, name) for row in player_games) / len(player_games) * factor, 1)
        session.add(NbaPlayerPrediction(game_id=game.id, player_id=lineup.player_id, player_name=lineup.player_name, team=lineup.team, model_version=PLAYER_MODEL_VERSION, timestamp=datetime.now(timezone.utc), projected_points=projected("points"), projected_rebounds=projected("rebounds"), projected_assists=projected("assists"), projected_threes=projected("three_pointers_made")))
        added += 1
    session.commit(); return added


def grade_nba_predictions(session: Session) -> dict[str, int]:
    game_rows = session.execute(select(NbaGamePrediction, NbaGame).join(NbaGame).where(NbaGame.status == "final", NbaGamePrediction.result.is_(None))).all()
    for prediction, game in game_rows:
        prediction.result, prediction.graded_at = ("WIN" if (prediction.home_win_probability >= .5) == (game.home_score > game.away_score) else "LOSS"), datetime.now(timezone.utc)
    player_rows = session.execute(select(NbaPlayerPrediction, NbaGame).join(NbaGame).outerjoin(NbaPlayerPredictionResult, NbaPlayerPredictionResult.prediction_id == NbaPlayerPrediction.id).where(NbaGame.status == "final", NbaPlayerPredictionResult.prediction_id.is_(None))).all()
    for prediction, game in player_rows:
        stat = session.scalar(select(NbaPlayerGame).where(NbaPlayerGame.game_id == game.id, NbaPlayerGame.player_id == prediction.player_id))
        if stat:
            session.add(NbaPlayerPredictionResult(prediction_id=prediction.id, actual_points=stat.points, actual_rebounds=stat.rebounds, actual_assists=stat.assists, actual_threes=stat.three_pointers_made, graded_at=datetime.now(timezone.utc)))
    session.commit(); return {"games": len(game_rows), "players": len(player_rows)}


def _team_margin(session: Session, team: str, before: datetime) -> tuple[float, int]:
    games = session.scalars(select(NbaGame).where(NbaGame.status == "final", NbaGame.game_date < before, (NbaGame.home_team == team) | (NbaGame.away_team == team)).order_by(NbaGame.game_date.desc()).limit(10)).all()
    if not games: return 0.0, 0
    margins = [(game.home_score - game.away_score) if game.home_team == team else (game.away_score - game.home_score) for game in games]
    return sum(margins) / len(margins), len(games)


def _starter_prediction_cutoff(now: datetime) -> datetime:
    eastern = ZoneInfo("America/New_York")
    return datetime.combine(now.astimezone(eastern).date() + timedelta(days=2), time.min, tzinfo=eastern).astimezone(timezone.utc)
