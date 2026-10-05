from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd

from app.services.live_prediction_service import _build_current_season_features


def _stats(game_id: str, team: str, ypp: float) -> dict:
    return {
        "game_id": game_id,
        "team": team,
        "ypp": ypp,
        "pass_ypp": ypp + 1,
        "rush_ypp": ypp - 1,
        "turnovers": 1,
    }


def test_current_season_features_blend_only_completed_current_games() -> None:
    history = pd.DataFrame(
        [
            {
                "game_id": "2025_game",
                "season": 2025,
                "week": 1,
                "date": datetime(2025, 9, 7, tzinfo=timezone.utc),
                "home": "AAA",
                "away": "BBB",
                "home_score": 10,
                "away_score": 7,
                "home_win": 1,
            }
        ]
    )
    prior_stats = pd.DataFrame(
        [_stats("2025_game", "AAA", 5), _stats("2025_game", "BBB", 4)]
    )
    current = SimpleNamespace(
        id="2026_completed",
        date=datetime(2026, 9, 10, tzinfo=timezone.utc),
        home_team="AAA",
        away_team="BBB",
        home_score=30,
        away_score=14,
    )
    target = SimpleNamespace(
        id="2026_target",
        season=2026,
        week=2,
        date=datetime(2026, 9, 17, tzinfo=timezone.utc),
        home_team="AAA",
        away_team="BBB",
        home_rest=7,
        away_rest=7,
        division_game=False,
    )
    current_stats = pd.DataFrame(
        [_stats("2026_completed", "AAA", 7), _stats("2026_completed", "BBB", 3)]
    )

    features = _build_current_season_features(
        [target], history, prior_stats, [current], current_stats
    )

    # Week 2 uses 75% prior-season strength and 25% completed Week 1 data.
    assert features.loc[0, "home_points_avg"] == 15.0
    assert features.loc[0, "away_points_avg"] == 8.75
    assert features.loc[0, "home_elo"] > features.loc[0, "away_elo"]

