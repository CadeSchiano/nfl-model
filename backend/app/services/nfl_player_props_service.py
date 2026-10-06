"""Pregame NFL yardage projections from completed player and opponent data."""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

import pandas as pd
import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.game import Game
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
    return _project(roster, player_games, defense_allowed, dates, matchups)


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
) -> list[dict]:
    player_games = player_games.copy()
    player_games["date"] = player_games.game_id.map(game_dates)
    player_games = player_games.dropna(subset=["date"])
    defense_per_game = defense_allowed.groupby(["team", "prop"], as_index=False).yards.mean()
    league_average = defense_per_game.groupby("prop").yards.mean().to_dict()
    allowed = defense_per_game.set_index(["team", "prop"]).yards.to_dict()
    rows = []
    for player in roster.itertuples(index=False):
        if player.position not in PROP_BY_POSITION or player.team not in matchups:
            continue
        prop, label = PROP_BY_POSITION[player.position]
        history = player_games.loc[
            (player_games.player_id == str(player.gsis_id))
            & (player_games.prop == prop)
        ].sort_values("date").tail(5)
        if history.empty:
            continue
        # A small sample can be negative (for example, a back stopped behind the
        # line on each carry). A negative yardage projection is not useful here.
        player_average = max(0.0, float(history.yards.mean()))
        game, opponent = matchups[player.team]
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
        })
    return sorted(rows, key=lambda item: (item["date"], item["prop"], -item["projected_yards"]))


def _projection(player_average: float, opponent_allowed: float, league_allowed: float) -> float:
    """Weight recent player production most, with a bounded matchup adjustment."""
    if player_average < 0:
        raise ValueError("player average cannot be negative")
    matchup_ratio = opponent_allowed / league_allowed if league_allowed else 1.0
    matchup_ratio = min(max(matchup_ratio, 0.70), 1.30)
    return round(player_average * (0.75 + 0.25 * matchup_ratio), 1)
