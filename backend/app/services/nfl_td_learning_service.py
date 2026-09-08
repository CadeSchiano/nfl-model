"""Safe weekly data refresh for the NFL touchdown model."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.game import Game
from app.services.nfl_td_data import download_td_player_games

ROOT = Path(__file__).resolve().parents[3]
BASE_HISTORY_PATH = ROOT / "data/processed/nfl_td_player_games_2019_2025.parquet"
CURRENT_HISTORY_PATH = ROOT / "data/processed/nfl_td_player_games_2019_current.parquet"
BASE_GAMES_PATH = ROOT / "data/processed/games_2015_2025.csv"
CURRENT_GAMES_PATH = ROOT / "data/processed/nfl_td_games_2019_current.csv"


def refresh_completed_td_history(session: Session) -> int:
    """Append only scored 2026+ games; safe to run repeatedly after each week."""
    completed = session.scalars(select(Game).where(Game.season >= 2026, Game.home_score.is_not(None), Game.away_score.is_not(None))).all()
    base = pd.read_parquet(BASE_HISTORY_PATH)
    if not completed:
        base.to_parquet(CURRENT_HISTORY_PATH, index=False)
        _write_training_games(completed)
        return 0
    game_ids = {game.id for game in completed}
    seasons = sorted({game.season for game in completed})
    recent = download_td_player_games(seasons)
    recent = recent.loc[recent.game_id.astype(str).isin(game_ids)]
    data = pd.concat([base, recent], ignore_index=True).drop_duplicates(["game_id", "player_id"], keep="last")
    data.to_parquet(CURRENT_HISTORY_PATH, index=False)
    _write_training_games(completed)
    return len(recent)


def _write_training_games(completed: list[Game]) -> None:
    games = pd.read_csv(BASE_GAMES_PATH)
    additions = pd.DataFrame([{"game_id": game.id, "season": game.season, "week": game.week, "date": game.date, "home": game.home_team, "away": game.away_team, "home_score": game.home_score, "away_score": game.away_score} for game in completed])
    if not additions.empty:
        games = pd.concat([games, additions], ignore_index=True).drop_duplicates("game_id", keep="last")
    games.to_csv(CURRENT_GAMES_PATH, index=False)
