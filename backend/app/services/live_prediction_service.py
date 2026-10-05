"""Current-season, pregame NFL prediction generation.

Published predictions stay immutable. New predictions use the saved historical
models with prior-season strength plus only completed games from the current
season that occurred before the target week's first kickoff.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.features import _mean_metrics, _snapshot, _team_game_record
from app.ml.predict import predict_home_margin, predict_home_win_probability
from app.ml.train import MODEL_FEATURE_COLUMNS
from app.models.game import Game
from app.models.prediction import Prediction
from app.services.elo_service import (
    EloConfig,
    canonical_team_code,
    expected_home_win_probability,
    generate_elo_predictions,
)
from app.services.nfl_data import download_team_game_stats


ROOT = Path(__file__).resolve().parents[3]


def generate_current_week_predictions(session: Session) -> int:
    next_game = session.scalar(
        select(Game)
        .where(Game.status == "scheduled", Game.date >= datetime.now(timezone.utc))
        .order_by(Game.date)
    )
    if next_game is None:
        return 0

    week_games = session.scalars(
        select(Game).where(Game.season == next_game.season, Game.week == next_game.week)
    ).all()
    games = [
        game
        for game in week_games
        if session.scalar(
            select(Prediction.id).where(
                Prediction.game_id == game.id,
                Prediction.model_version == "logistic_v1",
            )
        )
        is None
    ]
    if not games:
        return 0

    features = _current_season_features(session, games)
    models = ROOT / "backend" / "app" / "ml" / "models"
    moneyline = joblib.load(models / "logistic_v1.joblib")
    spread = joblib.load(models / "spread_ridge_v1.joblib")
    probabilities = predict_home_win_probability(moneyline, features)
    margins = predict_home_margin(spread, features)

    for game, probability, margin in zip(games, probabilities, margins):
        session.add(
            Prediction(
                game_id=game.id,
                model_version="logistic_v1",
                timestamp=datetime.now(timezone.utc),
                home_win_probability=float(probability),
                away_win_probability=float(1 - probability),
                predicted_margin=float(margin),
            )
        )
    session.commit()
    return len(games)


def _current_season_features(session: Session, live_games: list[Game]) -> pd.DataFrame:
    """Build target-week features using only games completed before kickoff."""
    season = live_games[0].season
    target_kickoff = min(_as_utc(game.date) for game in live_games)
    history = pd.read_csv(
        ROOT / "data" / "processed" / "games_2015_2025.csv", parse_dates=["date"]
    )
    historical = history.loc[history["season"] < season].copy()
    prior_season = historical.loc[historical["season"] == season - 1]
    if prior_season.empty:
        raise ValueError(f"no completed prior-season history is available for {season}")

    prior_stats = download_team_game_stats([season - 1])
    completed_current = session.scalars(
        select(Game)
        .where(
            Game.season == season,
            Game.home_score.is_not(None),
            Game.away_score.is_not(None),
            Game.date < target_kickoff,
        )
        .order_by(Game.date, Game.id)
    ).all()
    current_stats = download_team_game_stats([season]) if completed_current else pd.DataFrame()
    return _build_current_season_features(
        live_games,
        historical,
        prior_stats,
        completed_current,
        current_stats,
    )


def _build_current_season_features(
    live_games: list[Game],
    historical: pd.DataFrame,
    prior_stats: pd.DataFrame,
    completed_current: list[Game],
    current_stats: pd.DataFrame,
) -> pd.DataFrame:
    """Build features from prior-season state and completed current-season games."""
    season = live_games[0].season
    prior_season = historical.loc[
        historical["season"] == season - 1
    ].sort_values("date")
    prior_lookup = _stats_lookup(prior_stats)
    prior_state: dict[str, list[dict[str, float]]] = defaultdict(list)
    for row in prior_season.itertuples(index=False):
        _append_game_state(
            prior_state,
            game_id=row.game_id,
            home_team=row.home,
            away_team=row.away,
            home_score=row.home_score,
            away_score=row.away_score,
            stats=prior_lookup,
        )
    prior_strength = {
        team: _mean_metrics(records)
        for team, records in prior_state.items()
        if records
    }

    current_lookup = _stats_lookup(current_stats) if completed_current else {}
    current_state: dict[str, list[dict[str, float]]] = defaultdict(list)
    for game in sorted(completed_current, key=lambda item: (_as_utc(item.date), item.id)):
        _append_game_state(
            current_state,
            game_id=game.id,
            home_team=game.home_team,
            away_team=game.away_team,
            home_score=game.home_score,
            away_score=game.away_score,
            stats=current_lookup,
        )

    ratings = _current_elo_ratings(historical, completed_current, season)
    config = EloConfig()
    rows = []
    for game in live_games:
        home_team = canonical_team_code(game.home_team)
        away_team = canonical_team_code(game.away_team)
        home = _snapshot(current_state[home_team], prior_strength.get(home_team), game.week)
        away = _snapshot(current_state[away_team], prior_strength.get(away_team), game.week)
        home_rating = ratings.get(home_team, config.initial_rating)
        away_rating = ratings.get(away_team, config.initial_rating)
        row = {f"home_{name}": value for name, value in home.items()}
        row.update({f"away_{name}": value for name, value in away.items()})
        row.update(
            {
                "home_elo": home_rating,
                "away_elo": away_rating,
                "elo_diff": home_rating - away_rating,
                "rest_diff": (game.home_rest or 0) - (game.away_rest or 0),
                "division_game": game.division_game,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)[MODEL_FEATURE_COLUMNS]


def _stats_lookup(stats: pd.DataFrame) -> dict[tuple[str, str], dict[str, float]]:
    if stats.empty:
        return {}
    required = {"game_id", "team", "ypp", "pass_ypp", "rush_ypp", "turnovers"}
    missing = required.difference(stats.columns)
    if missing:
        raise ValueError(f"team statistics are missing required columns: {sorted(missing)}")
    normalized = stats.copy()
    normalized["team"] = normalized["team"].map(canonical_team_code)
    values = normalized.set_index(["game_id", "team"])[
        ["ypp", "pass_ypp", "rush_ypp", "turnovers"]
    ].to_dict("index")
    return {
        (str(game_id), team): {name: float(value) for name, value in record.items()}
        for (game_id, team), record in values.items()
    }


def _append_game_state(
    state: dict[str, list[dict[str, float]]],
    *,
    game_id: str,
    home_team: str,
    away_team: str,
    home_score: int | float | None,
    away_score: int | float | None,
    stats: dict[tuple[str, str], dict[str, float]],
) -> None:
    if home_score is None or away_score is None:
        raise ValueError(f"completed game {game_id} is missing a final score")
    home = canonical_team_code(home_team)
    away = canonical_team_code(away_team)
    try:
        home_stats = stats[(str(game_id), home)]
        away_stats = stats[(str(game_id), away)]
    except KeyError as exc:
        raise ValueError(
            f"missing play-by-play team statistics for completed game {game_id}"
        ) from exc
    record = type(
        "HistoricalGame",
        (),
        {
            "home_score": float(home_score),
            "away_score": float(away_score),
        },
    )()
    state[home].append(_team_game_record(record, home_stats, away_stats, True))
    state[away].append(_team_game_record(record, away_stats, home_stats, False))


def _current_elo_ratings(
    historical: pd.DataFrame, completed_current: list[Game], season: int
) -> dict[str, float]:
    """Return Elo ratings after prior history and current completed games."""
    history = historical.loc[historical["season"] < season].copy()
    elo = generate_elo_predictions(history)
    config = EloConfig()
    ratings: dict[str, float] = {}
    for row in elo.itertuples(index=False):
        home = canonical_team_code(row.home)
        away = canonical_team_code(row.away)
        result = (
            1.0
            if row.home_score > row.away_score
            else 0.5
            if row.home_score == row.away_score
            else 0.0
        )
        delta = config.k_factor * (result - row.home_win_probability)
        ratings[home] = row.home_pre_game_elo + delta
        ratings[away] = row.away_pre_game_elo - delta
    ratings = {
        team: config.initial_rating
        + (rating - config.initial_rating) * config.offseason_regression
        for team, rating in ratings.items()
    }
    for game in sorted(completed_current, key=lambda item: (_as_utc(item.date), item.id)):
        home = canonical_team_code(game.home_team)
        away = canonical_team_code(game.away_team)
        home_rating = ratings.get(home, config.initial_rating)
        away_rating = ratings.get(away, config.initial_rating)
        expected = expected_home_win_probability(
            home_rating, away_rating, config.home_field_advantage
        )
        result = (
            1.0
            if game.home_score > game.away_score
            else 0.5
            if game.home_score == game.away_score
            else 0.0
        )
        delta = config.k_factor * (result - expected)
        ratings[home] = home_rating + delta
        ratings[away] = away_rating - delta
    return ratings


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
