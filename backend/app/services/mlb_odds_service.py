"""Isolated MLB moneyline and run-line snapshots from The Odds API."""

from __future__ import annotations

from datetime import datetime, timezone

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mlb import MlbGame, MlbGameOdds
from app.services.odds_service import OddsApiError, load_odds_api_key, no_vig_probabilities


URL = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"


def update_mlb_game_odds(session: Session) -> int:
    """Fetch and persist one current bookmaker snapshot per matching MLB game."""
    try:
        response = requests.get(URL, params={"apiKey": load_odds_api_key(), "regions": "us", "markets": "h2h,spreads", "oddsFormat": "american"}, timeout=30)
        response.raise_for_status()
        events = response.json()
    except requests.RequestException as error:
        raise OddsApiError("unable to fetch MLB odds") from error
    created = 0
    games = session.scalars(select(MlbGame).where(MlbGame.status == "scheduled")).all()
    for game in games:
        event = next((item for item in events if item.get("home_team") == game.home_team and item.get("away_team") == game.away_team), None)
        if event is None:
            continue
        snapshot = _snapshot(event)
        if snapshot is None:
            continue
        session.add(MlbGameOdds(game_id=game.id, timestamp=snapshot["timestamp"], **snapshot["values"]))
        created += 1
    session.commit()
    return created


def latest_market(session: Session, game_id: int) -> dict[str, float] | None:
    odds = session.scalar(select(MlbGameOdds).where(MlbGameOdds.game_id == game_id).order_by(MlbGameOdds.timestamp.desc()))
    if odds is None:
        return None
    home_probability, _ = no_vig_probabilities(odds.home_moneyline, odds.away_moneyline)
    return {"market_home_probability": home_probability, "market_spread": odds.home_spread}


def _snapshot(event: dict) -> dict | None:
    for bookmaker in event.get("bookmakers", []):
        markets = {market.get("key"): market for market in bookmaker.get("markets", [])}
        h2h, spreads = markets.get("h2h"), markets.get("spreads")
        if not h2h or not spreads:
            continue
        prices = {outcome.get("name"): outcome.get("price") for outcome in h2h.get("outcomes", [])}
        points = {outcome.get("name"): outcome.get("point") for outcome in spreads.get("outcomes", [])}
        home, away = event["home_team"], event["away_team"]
        if None in (prices.get(home), prices.get(away), points.get(home)):
            continue
        try:
            return {"timestamp": datetime.fromisoformat(str(bookmaker.get("last_update") or datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00")), "values": {"bookmaker": str(bookmaker["key"]), "home_moneyline": int(prices[home]), "away_moneyline": int(prices[away]), "home_spread": float(points[home])}}
        except (KeyError, TypeError, ValueError):
            continue
    return None
