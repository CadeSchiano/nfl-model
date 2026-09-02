import pandas as pd

from app.services.nfl_td_data import ELIGIBLE_POSITIONS


def test_td_candidates_are_limited_to_skill_positions() -> None:
    roster = pd.DataFrame({"position": ["QB", "RB", "WR", "TE", "K", "LB"], "status": ["ACT"] * 6})
    assert roster.loc[roster.position.isin(ELIGIBLE_POSITIONS) & roster.status.eq("ACT"), "position"].tolist() == ["QB", "RB", "WR", "TE"]
