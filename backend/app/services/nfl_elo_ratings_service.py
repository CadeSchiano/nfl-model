"""Current team Elo ratings built only from completed NFL games."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.game import Game
from app.services.elo_service import EloConfig, canonical_team_code, expected_home_win_probability

ROOT = Path(__file__).resolve().parents[3]
HISTORY_PATH = ROOT / "data/processed/games_2015_2025.csv"


def current_elo_ratings(session: Session) -> list[dict]:
    """Return final ratings after every locally imported completed game."""
    historical = pd.read_csv(HISTORY_PATH, parse_dates=["date"])
    completed = session.scalars(select(Game).where(Game.home_score.is_not(None), Game.away_score.is_not(None)).order_by(Game.date)).all()
    additions = pd.DataFrame([{"game_id": game.id, "season": game.season, "week": game.week, "date": game.date, "home": game.home_team, "away": game.away_team, "home_score": game.home_score, "away_score": game.away_score} for game in completed])
    if not additions.empty:
        games = pd.concat([historical, additions], ignore_index=True).drop_duplicates("game_id", keep="last")
    else:
        games = historical
    return calculate_elo_ratings(games)


def calculate_elo_ratings(games: pd.DataFrame, config: EloConfig = EloConfig()) -> list[dict]:
    """Calculate postgame Elo, latest-game movement, and current-season record."""
    normalized = games.copy()
    normalized["date"] = pd.to_datetime(normalized["date"], utc=True)
    ordered = normalized.dropna(subset=["home_score", "away_score"]).sort_values(["season", "week", "date", "game_id"], kind="stable")
    ratings: dict[str, float] = {}
    changes: dict[str, float] = {}
    records: dict[str, list[int]] = {}
    previous_season: int | None = None
    for game in ordered.itertuples(index=False):
        season = int(game.season)
        if previous_season is not None and season != previous_season:
            ratings = {team: config.initial_rating + (rating - config.initial_rating) * config.offseason_regression for team, rating in ratings.items()}
        previous_season = season
        home, away = canonical_team_code(game.home), canonical_team_code(game.away)
        home_elo, away_elo = ratings.get(home, config.initial_rating), ratings.get(away, config.initial_rating)
        home_probability = expected_home_win_probability(home_elo, away_elo, config.home_field_advantage)
        home_result = 1.0 if game.home_score > game.away_score else 0.5 if game.home_score == game.away_score else 0.0
        change = config.k_factor * (home_result - home_probability)
        ratings[home], ratings[away] = home_elo + change, away_elo - change
        changes[home], changes[away] = change, -change
        if season == int(ordered.season.max()):
            records.setdefault(home, [0, 0, 0]); records.setdefault(away, [0, 0, 0])
            if home_result == 1:
                records[home][0] += 1; records[away][1] += 1
            elif home_result == 0:
                records[away][0] += 1; records[home][1] += 1
            else:
                records[home][2] += 1; records[away][2] += 1
    return [{"team": team, "rating": round(rating, 1), "change": round(changes.get(team, 0.0), 1), "wins": records.get(team, [0, 0, 0])[0], "losses": records.get(team, [0, 0, 0])[1], "ties": records.get(team, [0, 0, 0])[2]} for team, rating in sorted(ratings.items(), key=lambda item: item[1], reverse=True)]
