"""Completed-game NFL player season statistics for the searchable player page."""
from __future__ import annotations

from io import BytesIO, StringIO

import pandas as pd
import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.game import Game
from app.models.player_stats import NflPlayerSeasonStat
from app.services.nfl_td_data import PBP_URL, ROSTER_URL


def refresh_player_season_stats(session: Session, season: int) -> int:
    completed_ids = {game.id for game in session.scalars(select(Game).where(Game.season == season, Game.home_score.is_not(None), Game.away_score.is_not(None))).all()}
    if not completed_ids:
        return 0
    columns = ["game_id", "season_type", "posteam", "rush_attempt", "pass_attempt", "rusher_player_id", "rusher_player_name", "receiver_player_id", "receiver_player_name", "passer_player_id", "passer_player_name", "rushing_yards", "receiving_yards", "passing_yards", "rush_touchdown", "pass_touchdown"]
    response = requests.get(PBP_URL.format(season=season), timeout=180)
    response.raise_for_status()
    plays = pd.read_parquet(BytesIO(response.content), columns=columns)
    plays = plays.loc[plays.season_type.eq("REG") & plays.game_id.astype(str).isin(completed_ids)].copy()
    stats = _aggregate_player_stats(plays)
    roster_response = requests.get(ROSTER_URL.format(season=season), timeout=60)
    roster_response.raise_for_status()
    roster = pd.read_csv(StringIO(roster_response.text), low_memory=False).dropna(subset=["gsis_id", "full_name"])
    latest_names = roster.sort_values("week").drop_duplicates("gsis_id", keep="last").set_index("gsis_id")["full_name"]
    stats["player_name"] = stats.player_id.map(latest_names).fillna(stats.player_name)
    existing = {row.player_id: row for row in session.scalars(select(NflPlayerSeasonStat).where(NflPlayerSeasonStat.season == season)).all()}
    for row in stats.itertuples(index=False):
        target = existing.get(str(row.player_id))
        values = {field: getattr(row, field) for field in ("player_name", "team", "passing_yards", "rushing_yards", "receiving_yards", "passing_touchdowns", "rushing_touchdowns", "receiving_touchdowns")}
        if target is None:
            session.add(NflPlayerSeasonStat(player_id=str(row.player_id), season=season, **values))
        else:
            for field, value in values.items():
                setattr(target, field, value)
    session.commit()
    return len(stats)


def _aggregate_player_stats(plays: pd.DataFrame) -> pd.DataFrame:
    def group(mask, ident, name, yards, touchdowns, td_name):
        rows = plays.loc[mask & plays[ident].notna(), ["posteam", ident, name, yards, touchdowns]].rename(columns={"posteam": "team", ident: "player_id", name: "player_name", yards: "yards", touchdowns: td_name})
        return rows.groupby(["player_id", "player_name", "team"], as_index=False).agg(**{yards: ("yards", "sum"), td_name: (td_name, "sum")})
    rush = group(plays.rush_attempt.fillna(0).eq(1), "rusher_player_id", "rusher_player_name", "rushing_yards", "rush_touchdown", "rushing_touchdowns")
    receive = group(plays.pass_attempt.fillna(0).eq(1), "receiver_player_id", "receiver_player_name", "receiving_yards", "pass_touchdown", "receiving_touchdowns")
    passing = group(plays.pass_attempt.fillna(0).eq(1), "passer_player_id", "passer_player_name", "passing_yards", "pass_touchdown", "passing_touchdowns")
    combined = pd.concat([rush, receive, passing], ignore_index=True).fillna(0)
    numeric = ["passing_yards", "rushing_yards", "receiving_yards", "passing_touchdowns", "rushing_touchdowns", "receiving_touchdowns"]
    for column in numeric:
        if column not in combined:
            combined[column] = 0
    return combined.groupby(["player_id", "player_name", "team"], as_index=False)[numeric].sum()
