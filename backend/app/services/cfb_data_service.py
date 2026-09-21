"""CFBD FBS-only game import and The Odds API total-market import."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cfb import CfbGame, CfbMarketTotal
from app.services.odds_service import load_odds_api_key

CFBD_URL = "https://api.collegefootballdata.com"
ODDS_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_ncaaf/odds"


def _cfbd_key() -> str:
    key = os.environ.get("CFBD_API_KEY")
    if key:
        return key
    path = Path(__file__).resolve().parents[3] / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "CFBD_API_KEY" and value.strip():
                return value.strip().strip("\"'")
    raise RuntimeError("CFBD_API_KEY is not configured")


def import_fbs_games(session: Session, seasons: range) -> int:
    """Import only games whose CFBD classifications say both teams are FBS."""
    added = 0
    headers = {"Authorization": f"Bearer {_cfbd_key()}"}
    for season in seasons:
        response = requests.get(f"{CFBD_URL}/games", params={"year": season, "seasonType": "regular"}, headers=headers, timeout=90)
        response.raise_for_status()
        for item in response.json():
            if item.get("homeClassification") != "fbs" or item.get("awayClassification") != "fbs":
                continue
            game_id = str(item["id"])
            home_score, away_score = item.get("homePoints"), item.get("awayPoints")
            final = bool(item.get("completed")) and home_score is not None and away_score is not None
            game = session.get(CfbGame, game_id)
            values = {"season": int(item["season"]), "week": int(item["week"]), "kickoff": datetime.fromisoformat(item["startDate"].replace("Z", "+00:00")), "home_team": item["homeTeam"], "away_team": item["awayTeam"], "home_score": int(home_score) if final else None, "away_score": int(away_score) if final else None, "status": "final" if final else "scheduled"}
            if game is None:
                session.add(CfbGame(id=game_id, **values)); added += 1
            else:
                for key, value in values.items():
                    setattr(game, key, value)
    session.commit()
    return added


def import_cfb_market_totals(session: Session) -> int:
    response = requests.get(ODDS_URL, params={"apiKey": load_odds_api_key(), "regions": "us", "markets": "totals", "oddsFormat": "american"}, timeout=30)
    response.raise_for_status()
    games = session.scalars(select(CfbGame).where(CfbGame.status == "scheduled", CfbGame.kickoff > datetime.now(timezone.utc))).all()
    lookup = {_name_key(game.away_team) + "|" + _name_key(game.home_team): game for game in games}
    added = 0
    for event in response.json():
        game = lookup.get(_name_key(event["away_team"]) + "|" + _name_key(event["home_team"]))
        if game is None:
            continue
        for bookmaker in event.get("bookmakers", []):
            market = next((market for market in bookmaker.get("markets", []) if market.get("key") == "totals"), None)
            if not market or not market.get("outcomes") or market["outcomes"][0].get("point") is None:
                continue
            session.add(CfbMarketTotal(game_id=game.id, bookmaker=str(bookmaker.get("key", "unknown")), timestamp=datetime.now(timezone.utc), total=float(market["outcomes"][0]["point"])))
            added += 1
    session.commit()
    return added


def _name_key(name: str) -> str:
    mascots = {"flames", "chanticleers", "black knights", "owls", "midshipmen", "blazers", "crimson tide", "buckeyes", "tigers", "bulldogs", "wildcats", "horned frogs", "mountaineers", "cardinals", "hurricanes", "seminoles", "golden eagles", "gamecocks", "wolfpack", "yellow jackets", "blue devils", "tar heels", "bearcats", "cougars", "knights", "boilermakers", "wolverines", "spartans", "badgers", "hawkeyes", "cyclones", "jayhawks", "longhorns", "aggies", "razorbacks", "rebels", "commodores", "gators", "volunteers", "crimson", "trojans", "bruins", "sun devils", "utes", "beavers", "ducks", "huskies", "golden bears", "broncos", "falcons", "lobos", "rams", "rebels", "aztecs", "bobcats", "red raiders", "mean green", "roadrunners", "miners", "thundering herd", "panthers", "eagles", "jaguars", "warhawks", "raging cajuns", "bobcats", "red wolves"}
    text = name.lower().replace("&", "and")
    for mascot in sorted(mascots, key=len, reverse=True):
        if text.endswith(" " + mascot):
            text = text[: -len(mascot) - 1]
            break
    return "".join(character for character in text if character.isalnum())
