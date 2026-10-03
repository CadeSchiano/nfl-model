"""Manual, idempotent completed-game MLB ingestion via the MLB Stats API."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import requests
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.mlb import MlbGame, MlbPlayerGame


MLB_API = "https://statsapi.mlb.com/api/v1"
# MLB Stats API codes: regular season, Wild Card, Division Series, League
# Championship Series, and World Series.  Keeping this list explicit avoids
# silently dropping postseason games after the regular season ends.
MLB_GAME_TYPES = "R,F,D,L,W"


def update_completed_games(session: Session, start: date | None = None, end: date | None = None) -> int:
    """Fetch and persist scored regular-season and postseason MLB games."""
    # Future scheduled games must never advance the completed-results cursor.
    end = end or date.today()
    # Recheck a small overlap every day.  It is idempotent and avoids skipped
    # finals when schedules are imported before a game's final status arrives.
    start = start or (end - timedelta(days=3))
    schedule = _get("schedule", {"sportId": 1, "gameType": MLB_GAME_TYPES, "startDate": start.isoformat(), "endDate": end.isoformat()})
    imported = 0
    for day in schedule.get("dates", []):
        for game in day.get("games", []):
            if game.get("status", {}).get("abstractGameState") != "Final":
                continue
            imported_game = ingest_completed_game(session, get_live_feed(int(game["gamePk"])))
            # Persist each game so a long historical backfill can safely resume.
            session.commit()
            imported += int(imported_game)
    return imported


def ingest_completed_game(session: Session, feed: dict) -> bool:
    """Upsert one scored final feed and the players who actually appeared.

    A schedule can briefly report ``Final`` before its detailed feed has a
    linescore. Such a record is retained for a later retry but is never made a
    completed training/prediction input without both final scores.
    """
    data, live = feed["gameData"], feed["liveData"]
    game_pk = int(feed["gamePk"])
    teams = data["teams"]
    game = session.get(MlbGame, game_pk)
    if game is None:
        game = MlbGame(id=game_pk, game_date=_dt(data["datetime"]["dateTime"]), official_date=date.fromisoformat(data["datetime"]["officialDate"]), home_team=teams["home"]["name"], away_team=teams["away"]["name"], home_score=None, away_score=None, status="final")
        session.add(game)
    linescore = live.get("linescore", {}).get("teams", {})
    home_score = linescore.get("home", {}).get("runs")
    away_score = linescore.get("away", {}).get("runs")
    if home_score is None or away_score is None:
        game.status, game.completed_at = "incomplete", None
        return False
    game.home_score = int(home_score)
    game.away_score = int(away_score)
    game.status, game.completed_at = "final", datetime.now(timezone.utc)

    appeared, homers = _appearance_and_hr(feed)
    box_teams = live.get("boxscore", {}).get("teams", {})
    for side in ("home", "away"):
        for key, player in box_teams.get(side, {}).get("players", {}).items():
            player_id = int(player["person"]["id"])
            if player_id not in appeared:
                continue
            batting, pitching = player.get("stats", {}).get("batting", {}), player.get("stats", {}).get("pitching", {})
            record = session.scalar(select(MlbPlayerGame).where(MlbPlayerGame.game_id == game_pk, MlbPlayerGame.player_id == player_id))
            values = dict(player_name=player["person"]["fullName"], team=box_teams[side].get("team", {}).get("name", teams[side]["name"]), appeared=True, home_runs=homers.get(player_id, 0), plate_appearances=batting.get("plateAppearances"), at_bats=batting.get("atBats"), hits=batting.get("hits"), walks=batting.get("baseOnBalls"), strikeouts=batting.get("strikeOuts"), innings_pitched=str(pitching["inningsPitched"]) if pitching.get("inningsPitched") is not None else None, home_runs_allowed=pitching.get("homeRuns"))
            if record is None:
                session.add(MlbPlayerGame(game_id=game_pk, player_id=player_id, **values))
            else:
                for field, value in values.items(): setattr(record, field, value)
    return True


def _appearance_and_hr(feed: dict) -> tuple[set[int], dict[int, int]]:
    appeared, homers = set(), {}
    for play in feed.get("liveData", {}).get("plays", {}).get("allPlays", []):
        matchup = play.get("matchup", {})
        for role in ("batter", "pitcher"):
            if matchup.get(role, {}).get("id") is not None: appeared.add(int(matchup[role]["id"]))
        if play.get("result", {}).get("eventType") == "home_run":
            batter = matchup.get("batter", {}).get("id")
            if batter is not None: homers[int(batter)] = homers.get(int(batter), 0) + 1
    return appeared, homers


def _get(path: str, params: dict | None = None) -> dict:
    response = requests.get(f"{MLB_API}/{path}", params=params, timeout=45)
    response.raise_for_status()
    return response.json()


def get_live_feed(game_pk: int) -> dict:
    """The schedule API is v1; detailed live feeds are served on v1.1."""
    response = requests.get(f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live", timeout=45)
    response.raise_for_status()
    return response.json()


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
