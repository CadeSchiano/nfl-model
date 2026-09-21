"""Time-locked first-touchdown picks based on the strongest anytime-TD candidate."""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

import pandas as pd
import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.game import Game
from app.models.prediction import FirstTouchdownPrediction, TouchdownPrediction
from app.services.nfl_td_data import PBP_URL


def publish_first_touchdown_predictions(session: Session) -> int:
    next_game = session.scalar(select(Game).where(Game.status == "scheduled", Game.date >= datetime.now(timezone.utc)).order_by(Game.date))
    if next_game is None:
        return 0
    games = session.scalars(select(Game).where(Game.season == next_game.season, Game.week == next_game.week, Game.status == "scheduled")).all()
    added = 0
    for game in games:
        if session.scalar(select(FirstTouchdownPrediction.id).where(FirstTouchdownPrediction.game_id == game.id)) is not None:
            continue
        candidate = session.scalar(select(TouchdownPrediction).where(TouchdownPrediction.game_id == game.id).order_by(TouchdownPrediction.probability.desc()))
        if candidate is None:
            continue
        session.add(FirstTouchdownPrediction(game_id=game.id, player_id=candidate.player_id, player_name=candidate.player_name, team=candidate.team, model_version=f"first_td_from_{candidate.model_version}", timestamp=datetime.now(timezone.utc), anytime_probability=candidate.probability))
        added += 1
    session.commit()
    return added


def grade_first_touchdown_predictions(session: Session, regrade: bool = False) -> int:
    statement = select(FirstTouchdownPrediction, Game).join(Game).where(Game.home_score.is_not(None), Game.away_score.is_not(None))
    if not regrade:
        statement = statement.where(FirstTouchdownPrediction.result.is_(None))
    pending = session.execute(statement).all()
    if not pending:
        return 0
    seasons = sorted({game.season for _, game in pending})
    first_scorers = _first_scorers(seasons)
    now = datetime.now(timezone.utc)
    for prediction, game in pending:
        prediction.result = "HIT" if first_scorers.get(str(game.id)) == str(prediction.player_id) else "MISS"
        prediction.graded_at = now
    session.commit()
    return len(pending)


def _first_scorers(seasons: list[int]) -> dict[str, str]:
    rows = []
    for season in seasons:
        response = requests.get(PBP_URL.format(season=season), timeout=180)
        response.raise_for_status()
        plays = pd.read_parquet(BytesIO(response.content), columns=["game_id", "season_type", "play_id", "touchdown", "td_player_id"])
        rows.append(plays.loc[plays.season_type.eq("REG") & plays.touchdown.fillna(0).eq(1) & plays.td_player_id.notna(), ["game_id", "play_id", "td_player_id"]])
    touchdowns = pd.concat(rows, ignore_index=True).sort_values(["game_id", "play_id"])
    return touchdowns.drop_duplicates("game_id").set_index("game_id").td_player_id.astype(str).to_dict()
