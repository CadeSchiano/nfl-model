"""Live NFL odds snapshots and market-comparison utilities for V0.1."""

from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
TEAM_ABBREVIATIONS = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
    "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
}


class OddsApiError(RuntimeError):
    """Raised for safe, non-secret-bearing Odds API failures."""


@dataclass(frozen=True)
class OddsSnapshot:
    """One bookmaker's immutable observation for one scheduled NFL game."""

    odds_event_id: str
    commence_time: str
    home_team: str
    away_team: str
    bookmaker: str
    timestamp: str
    home_moneyline: int
    away_moneyline: int
    home_spread: float
    home_spread_odds: int
    away_spread: float
    away_spread_odds: int


def load_odds_api_key(env_path: Path | None = None) -> str:
    """Load the key from the environment or project-local ignored `.env` file."""
    key = os.environ.get("ODDS_API_KEY")
    if key:
        return key
    path = env_path or Path(__file__).resolve().parents[3] / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            name, separator, value = line.partition("=")
            if name.strip() == "ODDS_API_KEY" and separator and value.strip():
                return value.strip().strip('"').strip("'")
    raise OddsApiError("ODDS_API_KEY is not configured")


def fetch_current_odds(api_key: str) -> tuple[list[OddsSnapshot], list[str], dict[str, str]]:
    """Fetch US NFL h2h/spread odds and normalize each bookmaker snapshot."""
    try:
        response = requests.get(
            ODDS_API_URL,
            params={"apiKey": api_key, "regions": "us", "markets": "h2h,spreads", "oddsFormat": "american"},
            timeout=30,
        )
    except requests.RequestException as error:
        raise OddsApiError("unable to reach The Odds API") from error
    if not response.ok:
        raise OddsApiError(f"The Odds API request failed with HTTP {response.status_code}")
    try:
        events = response.json()
    except ValueError as error:
        raise OddsApiError("The Odds API returned invalid JSON") from error
    if not isinstance(events, list):
        raise OddsApiError("The Odds API returned an unexpected response shape")
    snapshots, warnings = normalize_odds_events(events)
    quota_headers = {
        key: response.headers[key]
        for key in ("x-requests-remaining", "x-requests-used", "x-requests-last")
        if key in response.headers
    }
    return snapshots, warnings, quota_headers


def normalize_odds_events(events: list[dict[str, Any]]) -> tuple[list[OddsSnapshot], list[str]]:
    """Convert API events to complete bookmaker snapshots; surface omissions."""
    snapshots: list[OddsSnapshot] = []
    warnings: list[str] = []
    for event in events:
        try:
            home = _team_abbreviation(event["home_team"])
            away = _team_abbreviation(event["away_team"])
            event_id = str(event["id"])
            commence_time = str(event["commence_time"])
        except (KeyError, OddsApiError) as error:
            warnings.append(f"event skipped due to unmapped required field: {error}")
            continue
        for bookmaker in event.get("bookmakers", []):
            snapshot, reason = _normalize_bookmaker(event_id, commence_time, home, away, bookmaker)
            if snapshot is None:
                warnings.append(f"{event_id}/{bookmaker.get('key', 'unknown')}: {reason}")
            else:
                snapshots.append(snapshot)
    return snapshots, warnings


def append_odds_snapshots(snapshots: list[OddsSnapshot], destination: Path) -> None:
    """Append snapshots without replacing any previously collected observation."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as file:
        for snapshot in snapshots:
            file.write(json.dumps(asdict(snapshot), sort_keys=True) + "\n")


def american_to_implied_probability(odds: int | float) -> float:
    """Convert non-zero American odds into its raw implied probability."""
    value = float(odds)
    if not math.isfinite(value) or value == 0:
        raise ValueError("American odds must be a finite, non-zero number")
    return abs(value) / (abs(value) + 100.0) if value < 0 else 100.0 / (value + 100.0)


def no_vig_probabilities(home_moneyline: int | float, away_moneyline: int | float) -> tuple[float, float]:
    """Normalize a two-sided market into fair probabilities summing to one."""
    home_raw = american_to_implied_probability(home_moneyline)
    away_raw = american_to_implied_probability(away_moneyline)
    total = home_raw + away_raw
    return home_raw / total, away_raw / total


def moneyline_discrepancy_label(edge: float) -> str:
    """Classify absolute moneyline model-vs-market disagreement."""
    magnitude = abs(edge)
    if magnitude < 0.02:
        return "minimal"
    if magnitude < 0.04:
        return "small"
    if magnitude < 0.07:
        return "moderate"
    return "large"


def spread_discrepancy_label(difference: float) -> str:
    """Classify absolute point-spread model-vs-market disagreement."""
    magnitude = abs(difference)
    if magnitude < 1.0:
        return "minimal"
    if magnitude < 2.0:
        return "small"
    if magnitude < 3.0:
        return "moderate"
    return "large"


def compare_model_to_market(
    home_win_probability: float, predicted_home_margin: float, snapshot: OddsSnapshot
) -> dict[str, float | str]:
    """Return no-vig moneyline and home-margin market disagreements.

    The API's home spread uses sportsbook sign convention (e.g. -3.5 means the
    home team is favored by 3.5). It is negated before comparing to the model's
    positive-home-margin convention.
    """
    if not 0.0 <= home_win_probability <= 1.0:
        raise ValueError("home_win_probability must be between 0 and 1")
    market_home_probability, market_away_probability = no_vig_probabilities(
        snapshot.home_moneyline, snapshot.away_moneyline
    )
    market_home_margin = -snapshot.home_spread
    moneyline_edge = home_win_probability - market_home_probability
    spread_difference = predicted_home_margin - market_home_margin
    return {
        "market_home_probability": market_home_probability,
        "market_away_probability": market_away_probability,
        "moneyline_difference": moneyline_edge,
        "moneyline_discrepancy": moneyline_discrepancy_label(moneyline_edge),
        "market_home_margin": market_home_margin,
        "spread_difference": spread_difference,
        "spread_discrepancy": spread_discrepancy_label(spread_difference),
    }


def _team_abbreviation(team_name: str) -> str:
    try:
        return TEAM_ABBREVIATIONS[team_name]
    except KeyError as error:
        raise OddsApiError(f"unmapped NFL team name {team_name!r}") from error


def _normalize_bookmaker(
    event_id: str, commence_time: str, home: str, away: str, bookmaker: dict[str, Any]
) -> tuple[OddsSnapshot | None, str]:
    markets = {market.get("key"): market for market in bookmaker.get("markets", [])}
    h2h, spreads = markets.get("h2h"), markets.get("spreads")
    if h2h is None or spreads is None:
        return None, "missing h2h or spreads market"
    h2h_prices = {outcome.get("name"): outcome.get("price") for outcome in h2h.get("outcomes", [])}
    spread_outcomes = {outcome.get("name"): outcome for outcome in spreads.get("outcomes", [])}
    home_ml, away_ml = h2h_prices.get(_full_team_name(home)), h2h_prices.get(_full_team_name(away))
    home_spread, away_spread = spread_outcomes.get(_full_team_name(home)), spread_outcomes.get(_full_team_name(away))
    if None in (home_ml, away_ml, home_spread, away_spread):
        return None, "missing home or away price"
    if home_spread.get("price") is None or away_spread.get("price") is None:
        return None, "missing spread price"
    try:
        return OddsSnapshot(
            odds_event_id=event_id,
            commence_time=commence_time,
            home_team=home,
            away_team=away,
            bookmaker=str(bookmaker["key"]),
            timestamp=str(bookmaker.get("last_update") or datetime.now(timezone.utc).isoformat()),
            home_moneyline=int(home_ml),
            away_moneyline=int(away_ml),
            home_spread=float(home_spread["point"]),
            home_spread_odds=int(home_spread["price"]),
            away_spread=float(away_spread["point"]),
            away_spread_odds=int(away_spread["price"]),
        ), ""
    except (KeyError, TypeError, ValueError):
        return None, "invalid odds value"


def _full_team_name(abbreviation: str) -> str:
    return next(name for name, code in TEAM_ABBREVIATIONS.items() if code == abbreviation)
