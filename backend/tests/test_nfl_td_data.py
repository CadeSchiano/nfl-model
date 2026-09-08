import pandas as pd

from app.services.nfl_td_data import ELIGIBLE_POSITIONS, aggregate_td_player_games
from app.services.nfl_td_prediction_service import _active_player_features


def test_td_candidates_are_limited_to_skill_positions() -> None:
    roster = pd.DataFrame({"position": ["QB", "RB", "WR", "TE", "K", "LB"], "status": ["ACT"] * 6})
    assert roster.loc[roster.position.isin(ELIGIBLE_POSITIONS) & roster.status.eq("ACT"), "position"].tolist() == ["QB", "RB", "WR", "TE"]


def test_aggregates_usage_and_touchdowns_by_player_game() -> None:
    plays = pd.DataFrame({"game_id": ["g", "g"], "season": [2025, 2025], "season_type": ["REG", "REG"], "posteam": ["KC", "KC"], "rush_attempt": [1, 0], "pass_attempt": [0, 1], "touchdown": [1, 0], "rusher_player_id": ["a", None], "rusher_player_name": ["Runner", None], "receiver_player_id": [None, "a"], "receiver_player_name": [None, "Runner"], "td_player_id": ["a", None], "td_player_name": ["Runner", None]})
    row = aggregate_td_player_games(plays).iloc[0]
    assert (row.carries, row.targets, row.touchdowns, row.scored_touchdown) == (1, 1, 1, 1)


def test_active_player_features_use_only_the_last_five_completed_games() -> None:
    roster = pd.DataFrame({"team": ["SEA"], "full_name": ["Player"], "gsis_id": ["p"]})
    history = pd.DataFrame({"player_id": ["p"] * 6, "player_name": ["Player"] * 6, "team": ["SEA"] * 6, "game_id": [str(i) for i in range(6)], "carries": [1, 2, 3, 4, 5, 6], "targets": [0, 1, 2, 3, 4, 5], "touchdowns": [0, 0, 0, 0, 0, 1], "scored_touchdown": [0, 0, 0, 0, 0, 1]})
    row = _active_player_features(roster, history).iloc[0]
    assert (row.prior_games, row.carries_avg, row.targets_avg, row.td_rate) == (5, 4.0, 3.0, 0.2)
