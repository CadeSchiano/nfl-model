"""ESPN-backed NBA schedule, final-score, and box-score ingestion."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.nba import NbaGame, NbaPlayerGame

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"


def update_nba_schedule(session: Session, start: date | None = None, end: date | None = None) -> int:
    """Upsert scheduled/final NBA games from ESPN's public daily scoreboard."""
    start, end = start or date.today(), end or date.today() + timedelta(days=7)
    updated = 0
    for day in _days(start, end):
        for event in _get(SCOREBOARD_URL, {"dates": day.strftime("%Y%m%d"), "limit": 100}).get("events", []):
            if _upsert_game(session, event):
                updated += 1
    session.commit()
    return updated


def update_completed_nba_games(session: Session, start: date | None = None, end: date | None = None) -> int:
    """Import final scores and player box scores. Safe to rerun after games end."""
    start, end = start or date.today() - timedelta(days=3), end or date.today()
    imported = 0
    for day in _days(start, end):
        for event in _get(SCOREBOARD_URL, {"dates": day.strftime("%Y%m%d"), "limit": 100}).get("events", []):
            if event.get("status", {}).get("type", {}).get("name") != "STATUS_FINAL":
                continue
            if not _upsert_game(session, event):
                continue
            summary = _summary_or_none(str(event["id"]))
            if summary is not None:
                _upsert_boxscore(session, str(event["id"]), summary)
            imported += 1
    session.commit()
    return imported


def _upsert_game(session: Session, event: dict) -> bool:
    competition = event["competitions"][0]
    teams = {item["homeAway"]: item for item in competition["competitors"]}
    home, away = teams["home"], teams["away"]
    home_code, away_code = _team_code(home), _team_code(away)
    # ESPN occasionally returns placeholder/exhibition events without a usable
    # NBA abbreviation in historical scoreboards. They cannot be modeled safely.
    if not home_code or not away_code:
        return False
    final = event.get("status", {}).get("type", {}).get("name") == "STATUS_FINAL"
    season = int(event.get("season", {}).get("year", datetime.fromisoformat(event["date"].replace("Z", "+00:00")).year)) - 1
    values = {
        "season": season,
        "game_date": datetime.fromisoformat(event["date"].replace("Z", "+00:00")),
        "home_team": home_code, "away_team": away_code,
        "home_score": int(home.get("score", 0)) if final else None,
        "away_score": int(away.get("score", 0)) if final else None,
        "status": "final" if final else "scheduled",
    }
    row = session.get(NbaGame, str(event["id"]))
    if row is None:
        session.add(NbaGame(id=str(event["id"]), **values)); return True
    for field, value in values.items():
        setattr(row, field, value)
    return False


def _upsert_boxscore(session: Session, game_id: str, summary: dict) -> None:
    for team_group in summary.get("boxscore", {}).get("players", []):
        team = team_group.get("team", {}).get("abbreviation")
        for block in team_group.get("statistics", []):
            names = block.get("names", [])
            for athlete in block.get("athletes", []):
                player = athlete.get("athlete", {})
                values = dict(zip(names, athlete.get("stats", [])))
                if not player.get("id") or not team:
                    continue
                data = {
                    "player_name": player.get("displayName", "Unknown"), "team": team,
                    "starter": bool(athlete.get("starter")), "minutes": _minutes(values.get("MIN")),
                    "points": _number(values.get("PTS")), "rebounds": _number(values.get("REB")),
                    "assists": _number(values.get("AST")), "three_pointers_made": _made(values.get("3PT")),
                }
                row = session.scalar(select(NbaPlayerGame).where(NbaPlayerGame.game_id == game_id, NbaPlayerGame.player_id == str(player["id"])))
                if row is None:
                    session.add(NbaPlayerGame(game_id=game_id, player_id=str(player["id"]), **data))
                else:
                    for field, value in data.items(): setattr(row, field, value)


def _get(url: str, params: dict) -> dict:
    response = requests.get(url, params=params, timeout=45)
    response.raise_for_status()
    return response.json()


def _summary_or_none(event_id: str) -> dict | None:
    try:
        return _get(SUMMARY_URL, {"event": event_id})
    except requests.HTTPError as error:
        # ESPN retains some final scoreboard rows but no longer exposes their
        # player-summary endpoint. Keep the score but omit that box score.
        if error.response is not None and error.response.status_code == 404:
            return None
        raise


def _days(start: date, end: date):
    while start <= end:
        yield start
        start += timedelta(days=1)


def _number(value: str | None) -> float:
    try: return float(value or 0)
    except ValueError: return 0.0


def _made(value: str | None) -> float:
    return _number((value or "0-0").split("-")[0])


def _minutes(value: str | None) -> float:
    if not value or value == "--": return 0.0
    parts = value.split(":")
    try: return float(parts[0]) + (float(parts[1]) / 60 if len(parts) > 1 else 0)
    except ValueError: return 0.0


def _team_code(competitor: dict) -> str | None:
    code = competitor.get("team", {}).get("abbreviation")
    return str(code).strip().upper() if code else None
