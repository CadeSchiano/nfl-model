import pandas as pd

from app.ml.cfb_total_model import build_total_features


def test_cfb_features_do_not_use_the_current_game_score() -> None:
    games = pd.DataFrame({"id": ["one", "two"], "season": [2026, 2026], "week": [1, 2], "kickoff": pd.to_datetime(["2026-08-29", "2026-09-05"], utc=True), "home_team": ["A", "A"], "away_team": ["B", "B"], "home_score": [30, None], "away_score": [20, None]})
    features = build_total_features(games)
    assert features.loc[0, "home_points_for"] == 0
    assert features.loc[1, "home_points_for"] == 30
    assert pd.isna(features.loc[1, "final_total"])
