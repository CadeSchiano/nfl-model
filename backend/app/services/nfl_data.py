"""Reproducible historical regular-season game loading from nflverse.

This module deliberately creates only game-level inputs.  It does not derive
team statistics, so no future game can enter a future feature by accident.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from typing import Iterable

import pandas as pd
import requests


NFLVERSE_GAMES_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
)
DEFAULT_SEASONS = tuple(range(2015, 2026))
VALID_TEAM_CODES = frozenset(
    {
        "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN",
        "DET", "GB", "HOU", "IND", "JAX", "KC", "LAC", "LAR", "LV", "MIA",
        "LA", "MIN", "NE", "NO", "NYG", "NYJ", "OAK", "PHI", "PIT", "SD", "SEA",
        "SF", "STL", "TB", "TEN", "WAS",
    }
)


class DataValidationError(ValueError):
    """Raised when a source record makes the historical dataset unreliable."""


@dataclass(frozen=True)
class ValidationReport:
    """Non-fatal source quality findings that must be visible to the operator."""

    warnings: tuple[str, ...]


def download_nflverse_games(url: str = NFLVERSE_GAMES_URL) -> pd.DataFrame:
    """Download the nflverse schedule release with an explicit network timeout."""
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return pd.read_csv(StringIO(response.text), low_memory=False)


def build_historical_games(
    raw_games: pd.DataFrame, seasons: Iterable[int] = DEFAULT_SEASONS
) -> tuple[pd.DataFrame, ValidationReport]:
    """Return validated, chronologically ordered completed regular-season games.

    `home_win` and `margin` use only the completed game's score and are labels,
    never pregame model features. Sportsbook fields stay nullable because the
    source may not provide a historical price for every otherwise valid game.
    """
    required_columns = {
        "game_id", "season", "week", "game_type", "gameday", "gametime",
        "home_team", "away_team", "home_score", "away_score", "spread_line",
        "home_moneyline", "away_moneyline", "home_rest", "away_rest",
    }
    missing = sorted(required_columns.difference(raw_games.columns))
    if missing:
        raise DataValidationError(f"nflverse source is missing required columns: {missing}")

    requested_seasons = tuple(seasons)
    games = raw_games.loc[
        raw_games["season"].isin(requested_seasons) & raw_games["game_type"].eq("REG")
    ].copy()
    if games.empty:
        raise DataValidationError("no requested regular-season games were found")

    games = games.rename(
        columns={
            "home_team": "home",
            "away_team": "away",
            "spread_line": "spread",
            "home_moneyline": "home_moneyline",
            "away_moneyline": "away_moneyline",
        }
    )
    games["season"] = pd.to_numeric(games["season"], errors="raise").astype(int)
    games["week"] = pd.to_numeric(games["week"], errors="raise").astype(int)
    games["home_score"] = pd.to_numeric(games["home_score"], errors="coerce")
    games["away_score"] = pd.to_numeric(games["away_score"], errors="coerce")
    games["spread"] = pd.to_numeric(games["spread"], errors="coerce")
    games["home_moneyline"] = pd.to_numeric(games["home_moneyline"], errors="coerce")
    games["away_moneyline"] = pd.to_numeric(games["away_moneyline"], errors="coerce")
    games["home_rest"] = pd.to_numeric(games["home_rest"], errors="coerce")
    games["away_rest"] = pd.to_numeric(games["away_rest"], errors="coerce")

    _validate_required_game_values(games, requested_seasons)
    _validate_teams(games)
    _validate_duplicates(games)

    games["date"] = pd.to_datetime(
        games["gameday"].astype(str) + " " + games["gametime"].fillna("00:00").astype(str),
        errors="coerce",
        utc=True,
    )
    if games["date"].isna().any():
        count = int(games["date"].isna().sum())
        raise DataValidationError(f"{count} games have an invalid gameday/gametime")

    games = games.sort_values(["season", "week", "date", "game_id"], kind="stable").reset_index(drop=True)
    if not games["date"].is_monotonic_increasing:
        raise DataValidationError("game ordering is not chronological after sorting")

    games["home_win"] = (games["home_score"] > games["away_score"]).astype(int)
    games["margin"] = games["home_score"] - games["away_score"]
    games["rest"] = games["home_rest"] - games["away_rest"]

    warnings = _quality_warnings(games)
    columns = [
        "game_id", "season", "week", "date", "home", "away", "home_score", "away_score",
        "spread", "home_moneyline", "away_moneyline", "home_rest", "away_rest", "rest",
        "home_win", "margin",
    ]
    return games.loc[:, columns], ValidationReport(tuple(warnings))


def _validate_required_game_values(games: pd.DataFrame, seasons: tuple[int, ...]) -> None:
    missing_seasons = sorted(set(seasons).difference(games["season"].unique()))
    if missing_seasons:
        raise DataValidationError(f"requested seasons absent from source: {missing_seasons}")
    if not games["week"].between(1, 18).all():
        raise DataValidationError("regular-season data contains a week outside 1–18")
    required = ["game_id", "home", "away", "home_score", "away_score"]
    null_counts = games[required].isna().sum()
    failures = {name: int(count) for name, count in null_counts.items() if count}
    if failures:
        raise DataValidationError(f"completed regular-season games have missing values: {failures}")
    if (games[["home_score", "away_score"]] < 0).any().any():
        raise DataValidationError("negative scores found in source")


def _validate_teams(games: pd.DataFrame) -> None:
    seen = set(games["home"]).union(games["away"])
    unknown = sorted(seen.difference(VALID_TEAM_CODES))
    if unknown:
        raise DataValidationError(f"unmapped historical team codes: {unknown}")
    if (games["home"] == games["away"]).any():
        raise DataValidationError("a game has the same home and away team")


def _validate_duplicates(games: pd.DataFrame) -> None:
    duplicate_ids = games["game_id"].duplicated(keep=False)
    if duplicate_ids.any():
        raise DataValidationError(f"duplicate game_id values: {int(duplicate_ids.sum())}")
    duplicate_matchups = games.duplicated(["season", "week", "home", "away"], keep=False)
    if duplicate_matchups.any():
        raise DataValidationError(f"duplicate season/week/home/away games: {int(duplicate_matchups.sum())}")


def _quality_warnings(games: pd.DataFrame) -> list[str]:
    warnings: list[str] = []
    for field in ("spread", "home_moneyline", "away_moneyline", "home_rest", "away_rest"):
        missing = int(games[field].isna().sum())
        if missing:
            warnings.append(f"{field}: {missing} missing values retained as null")
    invalid_moneylines = (games[["home_moneyline", "away_moneyline"]] == 0).any(axis=1).sum()
    if invalid_moneylines:
        warnings.append(f"moneyline: {int(invalid_moneylines)} zero values retained for review")
    return warnings
