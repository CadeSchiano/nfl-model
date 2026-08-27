"""Leakage-safe pregame feature construction for historical NFL games."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd

from app.services.elo_service import canonical_team_code, generate_elo_predictions


STRENGTH_METRICS = (
    "win_pct", "point_diff", "points_avg", "points_allowed_avg", "ypp", "pass_ypp",
    "rush_ypp", "ypp_allowed", "pass_ypp_allowed", "rush_ypp_allowed", "turnover_diff",
)


def build_pregame_features(games: pd.DataFrame, team_game_stats: pd.DataFrame) -> pd.DataFrame:
    """Create one historical feature row per game using only earlier results.

    The state is read for both teams before either state is updated with the
    game's outcome. This is equivalent to shifting each team history by one
    game, while retaining correct alignment for home and away teams.
    """
    if not {"home_pre_game_elo", "away_pre_game_elo", "elo_difference"}.issubset(games.columns):
        games = generate_elo_predictions(games)
    required_games = {
        "game_id", "season", "week", "date", "home", "away", "home_score", "away_score",
        "home_rest", "away_rest", "division_game",
    }
    missing_games = sorted(required_games.difference(games.columns))
    if missing_games:
        raise ValueError(f"games are missing columns required for features: {missing_games}")
    stats = _prepare_stats(team_game_stats, games)
    ordered = games.sort_values(["season", "week", "date", "game_id"], kind="stable").copy()
    states: dict[str, list[dict[str, float]]] = defaultdict(list)
    prior_season: dict[str, dict[str, float]] = {}
    previous_season: int | None = None
    feature_rows: list[dict[str, Any]] = []

    for game in ordered.itertuples(index=False):
        season = int(game.season)
        if previous_season is not None and season != previous_season:
            prior_season = {team: _mean_metrics(history) for team, history in states.items() if history}
            states = defaultdict(list)
        previous_season = season

        home_team = canonical_team_code(game.home)
        away_team = canonical_team_code(game.away)
        home_features = _snapshot(states[home_team], prior_season.get(home_team), int(game.week))
        away_features = _snapshot(states[away_team], prior_season.get(away_team), int(game.week))
        row = game._asdict()
        row.update({f"home_{name}": value for name, value in home_features.items()})
        row.update({f"away_{name}": value for name, value in away_features.items()})
        row["home_elo"] = row["home_pre_game_elo"]
        row["away_elo"] = row["away_pre_game_elo"]
        row["elo_diff"] = row["elo_difference"]
        row["rest_diff"] = float(game.home_rest) - float(game.away_rest)
        row["division_game"] = bool(game.division_game)
        feature_rows.append(row)

        home_game = _team_game_record(game, stats[(game.game_id, home_team)], stats[(game.game_id, away_team)], True)
        away_game = _team_game_record(game, stats[(game.game_id, away_team)], stats[(game.game_id, home_team)], False)
        states[home_team].append(home_game)
        states[away_team].append(away_game)

    return pd.DataFrame(feature_rows)


def _prepare_stats(team_game_stats: pd.DataFrame, games: pd.DataFrame) -> dict[tuple[str, str], dict[str, float]]:
    required = {"game_id", "team", "ypp", "pass_ypp", "rush_ypp", "turnovers"}
    missing = sorted(required.difference(team_game_stats.columns))
    if missing:
        raise ValueError(f"team game stats are missing columns required for features: {missing}")
    stats = team_game_stats.copy()
    stats["team"] = stats["team"].map(canonical_team_code)
    if stats.duplicated(["game_id", "team"]).any():
        raise ValueError("team game stats contain duplicate game/team rows")
    indexed = stats.set_index(["game_id", "team"])
    expected = {(game.game_id, canonical_team_code(team)) for game in games.itertuples(index=False) for team in (game.home, game.away)}
    missing_stats = sorted(expected.difference(indexed.index))
    if missing_stats:
        raise ValueError(f"missing team statistics for {len(missing_stats)} game/team rows")
    return {key: {name: float(value) for name, value in values.items()} for key, values in indexed.to_dict("index").items()}


def _snapshot(current: list[dict[str, float]], prior: dict[str, float] | None, week: int) -> dict[str, float]:
    current_mean = _mean_metrics(current) if current else {}
    prior_weight = _prior_weight(week)
    output = {
        metric: _blend(prior.get(metric, np.nan) if prior else np.nan, current_mean.get(metric, np.nan), prior_weight)
        for metric in STRENGTH_METRICS
    }
    margins = [game["point_diff"] for game in current]
    output["last3_margin"] = float(np.mean(margins[-3:])) if margins else np.nan
    output["last5_margin"] = float(np.mean(margins[-5:])) if margins else np.nan
    return output


def _prior_weight(week: int) -> float:
    """Initial, documented prior-season weights for Weeks 1–7; test later."""
    if week <= 1:
        return 0.90
    if week == 2:
        return 0.75
    if week == 3:
        return 0.60
    if week == 4:
        return 0.50
    if week <= 7:
        return (8 - week) * 0.125
    return 0.0


def _blend(prior: float, current: float, prior_weight: float) -> float:
    if np.isfinite(prior) and np.isfinite(current):
        return prior_weight * prior + (1.0 - prior_weight) * current
    if np.isfinite(prior):
        return prior
    return current


def _mean_metrics(history: list[dict[str, float]]) -> dict[str, float]:
    return {metric: float(np.nanmean([game[metric] for game in history])) for metric in STRENGTH_METRICS}


def _team_game_record(game: Any, own: dict[str, float], opponent: dict[str, float], home: bool) -> dict[str, float]:
    score_for = float(game.home_score if home else game.away_score)
    score_against = float(game.away_score if home else game.home_score)
    margin = score_for - score_against
    return {
        "win_pct": 1.0 if margin > 0 else 0.5 if margin == 0 else 0.0,
        "point_diff": margin,
        "points_avg": score_for,
        "points_allowed_avg": score_against,
        "ypp": own["ypp"],
        "pass_ypp": own["pass_ypp"],
        "rush_ypp": own["rush_ypp"],
        "ypp_allowed": opponent["ypp"],
        "pass_ypp_allowed": opponent["pass_ypp"],
        "rush_ypp_allowed": opponent["rush_ypp"],
        "turnover_diff": opponent["turnovers"] - own["turnovers"],
    }
