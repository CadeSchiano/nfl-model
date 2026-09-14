import pandas as pd

from app.services.nfl_elo_ratings_service import calculate_elo_ratings


def test_current_elo_ratings_reflect_completed_results() -> None:
    games = pd.DataFrame({"game_id": ["one", "two"], "season": [2026, 2026], "week": [1, 2], "date": pd.to_datetime(["2026-09-10", "2026-09-17"], utc=True), "home": ["AAA", "BBB"], "away": ["BBB", "AAA"], "home_score": [21, 10], "away_score": [10, 20]})
    ratings = {row["team"]: row for row in calculate_elo_ratings(games)}
    assert ratings["AAA"]["rating"] > ratings["BBB"]["rating"]
    assert (ratings["AAA"]["wins"], ratings["AAA"]["losses"]) == (2, 0)
