"""Current-roster support for the isolated NFL anytime-touchdown model."""
from __future__ import annotations

from io import StringIO
from io import BytesIO
from typing import Iterable

import pandas as pd
import requests

ROSTER_URL = "https://github.com/nflverse/nflverse-data/releases/download/rosters/roster_{season}.csv"
PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet"
ELIGIBLE_POSITIONS = {"QB", "RB", "WR", "TE"}


def download_active_roster(season: int, week: int) -> pd.DataFrame:
    """Return the current eligible active players for a regular-season week."""
    response = requests.get(ROSTER_URL.format(season=season), timeout=60)
    response.raise_for_status()
    roster = pd.read_csv(StringIO(response.text), low_memory=False)
    rows = roster.loc[(roster["week"] == week) & roster["game_type"].eq("REG") & roster["position"].isin(ELIGIBLE_POSITIONS) & roster["status"].eq("ACT")].copy()
    # nflverse roster feeds use LA while the game table uses the established LAR code.
    rows["team"] = rows["team"].replace({"LA": "LAR"})
    return rows[["team", "position", "full_name", "gsis_id", "week"]].dropna(subset=["gsis_id"])


def download_td_player_games(seasons: Iterable[int]) -> pd.DataFrame:
    """Build compact offensive player-game observations without retaining raw PBP."""
    observations = []
    columns = ["game_id", "season", "season_type", "posteam", "rush_attempt", "pass_attempt", "touchdown", "rusher_player_id", "rusher_player_name", "receiver_player_id", "receiver_player_name", "td_player_id", "td_player_name"]
    for season in seasons:
        response = requests.get(PBP_URL.format(season=season), timeout=180)
        response.raise_for_status()
        plays = pd.read_parquet(BytesIO(response.content), columns=columns)
        observations.append(aggregate_td_player_games(plays))
    return pd.concat(observations, ignore_index=True)


def aggregate_td_player_games(plays: pd.DataFrame) -> pd.DataFrame:
    """Aggregate carries, targets, and offensive TD outcomes by player/game."""
    regular = plays.loc[plays.season_type.eq("REG") & plays.posteam.notna()].copy()
    rush = regular.loc[regular.rush_attempt.fillna(0).eq(1) & regular.rusher_player_id.notna(), ["game_id", "season", "posteam", "rusher_player_id", "rusher_player_name"]].rename(columns={"posteam": "team", "rusher_player_id": "player_id", "rusher_player_name": "player_name"})
    rush["carries"], rush["targets"] = 1, 0
    receive = regular.loc[regular.pass_attempt.fillna(0).eq(1) & regular.receiver_player_id.notna(), ["game_id", "season", "posteam", "receiver_player_id", "receiver_player_name"]].rename(columns={"posteam": "team", "receiver_player_id": "player_id", "receiver_player_name": "player_name"})
    receive["carries"], receive["targets"] = 0, 1
    usage = pd.concat([rush, receive], ignore_index=True)
    td = regular.loc[regular.touchdown.fillna(0).eq(1) & regular.td_player_id.notna(), ["game_id", "td_player_id"]].rename(columns={"td_player_id": "player_id"})
    td["touchdowns"] = 1
    result = usage.groupby(["game_id", "season", "team", "player_id", "player_name"], as_index=False)[["carries", "targets"]].sum()
    scores = td.groupby(["game_id", "player_id"], as_index=False).touchdowns.sum()
    result = result.merge(scores, how="left", on=["game_id", "player_id"])
    result["touchdowns"] = result.touchdowns.fillna(0).astype(int)
    result["scored_touchdown"] = (result.touchdowns > 0).astype(int)
    return result
