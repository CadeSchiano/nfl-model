"""Pregame NFL yardage projections from completed player and opponent data."""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

import pandas as pd
import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.game import Game
from app.models.player_availability import NflPlayerAvailability
from app.models.qb_starter import NflExpectedQbStarter
from app.services.elo_service import canonical_team_code
from app.services.nfl_td_data import PBP_URL, download_active_roster

PROP_BY_POSITION = {"QB": ("passing", "passing_yards"), "RB": ("rushing", "rushing_yards"), "WR": ("receiving", "receiving_yards"), "TE": ("receiving", "receiving_yards")}


def current_week_player_props(session: Session) -> list[dict]:
    """Return usage- and matchup-adjusted yardage projections for active players."""
    now = datetime.now(timezone.utc)
    next_game = session.scalar(
        select(Game).where(Game.status == "scheduled", Game.date >= now).order_by(Game.date)
    )
    if next_game is None:
        return []
    games = session.scalars(
        select(Game).where(Game.season == next_game.season, Game.week == next_game.week)
    ).all()
    completed = session.scalars(
        select(Game).where(
            Game.season == next_game.season,
            Game.home_score.is_not(None),
            Game.away_score.is_not(None),
            Game.date < next_game.date,
        )
    ).all()
    if not completed:
        return []
    completed_ids = {game.id for game in completed}
    roster = download_active_roster(next_game.season, next_game.week)
    plays = _season_plays(next_game.season, completed_ids)
    player_games = _player_game_yards(plays)
    defense_allowed = _defense_yards_allowed(plays)
    dates = {game.id: game.date for game in completed}
    matchups = {
        game.home_team: (game, game.away_team)
        for game in games
    } | {
        game.away_team: (game, game.home_team)
        for game in games
    }
    unavailable = set(session.scalars(select(NflPlayerAvailability.player_id).where(NflPlayerAvailability.status == "OUT")).all())
    starters = {
        row.game_id: row.player_id
        for row in session.scalars(select(NflExpectedQbStarter).where(NflExpectedQbStarter.game_id.in_([game.id for game in games]))).all()
    }
    return _project(roster, player_games, defense_allowed, dates, matchups, unavailable, starters)


def _season_plays(season: int, completed_ids: set[str]) -> pd.DataFrame:
    columns = [
        "game_id", "season_type", "posteam", "defteam", "rush_attempt", "pass_attempt",
        "rusher_player_id", "rusher_player_name", "receiver_player_id",
        "receiver_player_name", "passer_player_id", "passer_player_name",
        "rushing_yards", "receiving_yards", "passing_yards",
    ]
    response = requests.get(PBP_URL.format(season=season), timeout=180)
    response.raise_for_status()
    plays = pd.read_parquet(BytesIO(response.content), columns=columns)
    return plays.loc[
        plays.season_type.eq("REG") & plays.game_id.astype(str).isin(completed_ids)
    ].copy()


def _player_game_yards(plays: pd.DataFrame) -> pd.DataFrame:
    groups = []
    definitions = [
        ("passing", "pass_attempt", "passer_player_id", "passer_player_name", "passing_yards"),
        ("rushing", "rush_attempt", "rusher_player_id", "rusher_player_name", "rushing_yards"),
        ("receiving", "pass_attempt", "receiver_player_id", "receiver_player_name", "receiving_yards"),
    ]
    for prop, attempt, identifier, name, yards in definitions:
        rows = plays.loc[
            plays[attempt].fillna(0).eq(1) & plays[identifier].notna(),
            ["game_id", "posteam", identifier, name, yards],
        ].rename(columns={"posteam": "team", identifier: "player_id", name: "player_name", yards: "yards"})
        rows["prop"] = prop
        groups.append(rows)
    data = pd.concat(groups, ignore_index=True)
    data["team"] = data.team.map(canonical_team_code)
    data["player_id"] = data.player_id.astype(str)
    return data.groupby(["game_id", "team", "player_id", "player_name", "prop"], as_index=False).yards.sum()


def _defense_yards_allowed(plays: pd.DataFrame) -> pd.DataFrame:
    groups = []
    definitions = [
        ("passing", "pass_attempt", "passing_yards"),
        ("rushing", "rush_attempt", "rushing_yards"),
        ("receiving", "pass_attempt", "receiving_yards"),
    ]
    for prop, attempt, yards in definitions:
        rows = plays.loc[
            plays[attempt].fillna(0).eq(1) & plays.defteam.notna(),
            ["game_id", "defteam", yards],
        ].rename(columns={"defteam": "team", yards: "yards"})
        rows["prop"] = prop
        groups.append(rows)
    data = pd.concat(groups, ignore_index=True)
    data["team"] = data.team.map(canonical_team_code)
    return data.groupby(["game_id", "team", "prop"], as_index=False).yards.sum()


def _project(
    roster: pd.DataFrame,
    player_games: pd.DataFrame,
    defense_allowed: pd.DataFrame,
    game_dates: dict[str, object],
    matchups: dict[str, tuple[Game, str]],
    unavailable: set[str] | None = None,
    expected_starters: dict[str, str] | None = None,
) -> list[dict]:
    player_games = player_games.copy()
    player_games["date"] = player_games.game_id.map(game_dates)
    player_games = player_games.dropna(subset=["date"])
    defense_per_game = defense_allowed.groupby(["team", "prop"], as_index=False).yards.mean()
    league_average = defense_per_game.groupby("prop").yards.mean().to_dict()
    allowed = defense_per_game.set_index(["team", "prop"]).yards.to_dict()
    rows = []
    unavailable = unavailable or set()
    expected_starters = expected_starters or {}
    for player in roster.itertuples(index=False):
        if player.position not in PROP_BY_POSITION or player.team not in matchups or str(player.gsis_id) in unavailable:
            continue
        prop, label = PROP_BY_POSITION[player.position]
        game, opponent = matchups[player.team]
        starter_override = player.position == "QB" and expected_starters.get(game.id) == str(player.gsis_id)
        history = player_games.loc[
            (player_games.player_id == str(player.gsis_id))
            & (player_games.prop == prop)
        ].sort_values("date").tail(5)
        if starter_override:
            history = player_games.loc[
                (player_games.team == player.team) & (player_games.prop == "passing")
            ].groupby(["game_id", "date"], as_index=False).yards.sum().sort_values("date").tail(5)
        if history.empty:
            continue
        # A small sample can be negative (for example, a back stopped behind the
        # line on each carry). A negative yardage projection is not useful here.
        player_average = max(0.0, float(history.yards.mean()))
        opponent_average = float(allowed.get((opponent, prop), league_average.get(prop, 0.0)))
        league = float(league_average.get(prop, opponent_average or 1.0))
        projected = _projection(player_average, opponent_average, league)
        rows.append({
            "game_id": game.id,
            "away_team": game.away_team,
            "home_team": game.home_team,
            "date": game.date,
            "player_id": str(player.gsis_id),
            "player_name": player.full_name,
            "team": player.team,
            "position": player.position,
            "prop": label,
            "projected_yards": projected,
            "recent_average_yards": player_average,
            "opponent_allowed_yards": opponent_average,
            "games_used": int(len(history)),
            "starter_override": starter_override,
        })
    return sorted(rows, key=lambda item: (item["date"], item["prop"], -item["projected_yards"]))


def _projection(player_average: float, opponent_allowed: float, league_allowed: float) -> float:
    """Weight recent player production most, with a bounded matchup adjustment."""
    if player_average < 0:
        raise ValueError("player average cannot be negative")
    matchup_ratio = opponent_allowed / league_allowed if league_allowed else 1.0
    matchup_ratio = min(max(matchup_ratio, 0.70), 1.30)
    return round(player_average * (0.75 + 0.25 * matchup_ratio), 1)
