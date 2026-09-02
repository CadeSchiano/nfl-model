"""Current-roster support for the isolated NFL anytime-touchdown model."""
from __future__ import annotations

from io import StringIO

import pandas as pd
import requests

ROSTER_URL = "https://github.com/nflverse/nflverse-data/releases/download/rosters/roster_{season}.csv"
ELIGIBLE_POSITIONS = {"QB", "RB", "WR", "TE"}


def download_active_roster(season: int, week: int) -> pd.DataFrame:
    """Return the current eligible active players for a regular-season week."""
    response = requests.get(ROSTER_URL.format(season=season), timeout=60)
    response.raise_for_status()
    roster = pd.read_csv(StringIO(response.text), low_memory=False)
    rows = roster.loc[(roster["week"] == week) & roster["game_type"].eq("REG") & roster["position"].isin(ELIGIBLE_POSITIONS) & roster["status"].eq("ACT")].copy()
    return rows[["team", "position", "full_name", "gsis_id", "week"]].dropna(subset=["gsis_id"])
