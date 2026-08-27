"""Chronological, leakage-safe Elo ratings for NFL pregame predictions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd


# nflverse's historic abbreviations map to the same continuing franchise.
FRANCHISE_ALIASES: Mapping[str, str] = {"LA": "LAR", "STL": "LAR", "OAK": "LV", "SD": "LAC"}


@dataclass(frozen=True)
class EloConfig:
    """Documented V0.1 starting assumptions for the Elo baseline."""

    initial_rating: float = 1500.0
    home_field_advantage: float = 55.0
    k_factor: float = 20.0
    offseason_regression: float = 0.70
    model_version: str = "elo_v1"


def expected_home_win_probability(home_elo: float, away_elo: float, home_field_advantage: float) -> float:
    """Return the pregame probability that the home team wins.

    Home-field advantage is expressed in Elo points and applied only to this
    expectation; it is not added permanently to either team's rating.
    """
    rating_difference = home_elo + home_field_advantage - away_elo
    return 1.0 / (1.0 + 10.0 ** (-rating_difference / 400.0))


def generate_elo_predictions(games: pd.DataFrame, config: EloConfig = EloConfig()) -> pd.DataFrame:
    """Produce historical pregame Elo predictions in chronological order.

    Each row receives its ratings and probability before its result updates
    either team. This ordering is the central anti-leakage constraint.
    """
    required_columns = {"game_id", "season", "week", "date", "home", "away", "home_score", "away_score", "home_win"}
    missing = sorted(required_columns.difference(games.columns))
    if missing:
        raise ValueError(f"games are missing columns required for Elo: {missing}")
    if not 0.0 <= config.offseason_regression <= 1.0:
        raise ValueError("offseason_regression must be between 0 and 1")
    if config.k_factor <= 0:
        raise ValueError("k_factor must be positive")

    ordered = games.sort_values(["season", "week", "date", "game_id"], kind="stable").copy()
    ratings: dict[str, float] = {}
    previous_season: int | None = None
    home_elos: list[float] = []
    away_elos: list[float] = []
    probabilities: list[float] = []

    for game in ordered.itertuples(index=False):
        season = int(game.season)
        if previous_season is not None and season != previous_season:
            ratings = {
                team: config.initial_rating + (rating - config.initial_rating) * config.offseason_regression
                for team, rating in ratings.items()
            }
        previous_season = season

        home_team = canonical_team_code(game.home)
        away_team = canonical_team_code(game.away)
        home_elo = ratings.get(home_team, config.initial_rating)
        away_elo = ratings.get(away_team, config.initial_rating)
        probability = expected_home_win_probability(home_elo, away_elo, config.home_field_advantage)

        home_elos.append(home_elo)
        away_elos.append(away_elo)
        probabilities.append(probability)

        actual_home_result = _home_result(float(game.home_score), float(game.away_score))
        rating_change = config.k_factor * (actual_home_result - probability)
        ratings[home_team] = home_elo + rating_change
        ratings[away_team] = away_elo - rating_change

    ordered["home_pre_game_elo"] = home_elos
    ordered["away_pre_game_elo"] = away_elos
    ordered["elo_difference"] = ordered["home_pre_game_elo"] - ordered["away_pre_game_elo"]
    ordered["home_win_probability"] = probabilities
    ordered["model_version"] = config.model_version
    return ordered


def evaluate_elo_predictions(predictions: pd.DataFrame) -> dict[str, float | int]:
    """Calculate accuracy and Brier score for non-tied historical games."""
    required_columns = {"home_win_probability", "home_win", "home_score", "away_score"}
    missing = sorted(required_columns.difference(predictions.columns))
    if missing:
        raise ValueError(f"predictions are missing columns required for evaluation: {missing}")

    non_ties = predictions.loc[predictions["home_score"] != predictions["away_score"]]
    if non_ties.empty:
        raise ValueError("cannot evaluate Elo without at least one non-tied game")
    probabilities = non_ties["home_win_probability"].to_numpy(dtype=float)
    outcomes = non_ties["home_win"].to_numpy(dtype=float)
    predicted_home_wins = probabilities >= 0.5
    return {
        "games": int(len(predictions)),
        "evaluated_games": int(len(non_ties)),
        "ties_excluded": int(len(predictions) - len(non_ties)),
        "accuracy": float(np.mean(predicted_home_wins == outcomes)),
        "brier_score": float(np.mean((probabilities - outcomes) ** 2)),
    }


def canonical_team_code(team: str) -> str:
    """Map a historical abbreviation to its continuing franchise code."""
    return FRANCHISE_ALIASES.get(team, team)


def _home_result(home_score: float, away_score: float) -> float:
    if home_score > away_score:
        return 1.0
    if home_score < away_score:
        return 0.0
    return 0.5
