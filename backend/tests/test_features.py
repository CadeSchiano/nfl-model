import pandas as pd
import pytest

from app.ml.features import build_pregame_features
from app.services.nfl_data import aggregate_team_game_stats


def games() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game_id": ["one", "two"], "season": [2020, 2020], "week": [1, 2],
            "date": pd.to_datetime(["2020-09-13T17:00:00Z", "2020-09-20T17:00:00Z"]),
            "home": ["BUF", "BUF"], "away": ["NYJ", "MIA"],
            "home_score": [21, 7], "away_score": [14, 10], "home_win": [1, 0],
            "home_rest": [7, 7], "away_rest": [7, 7], "division_game": [True, True],
        }
    )


def team_stats() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game_id": ["one", "one", "two", "two"],
            "team": ["BUF", "NYJ", "BUF", "MIA"],
            "ypp": [5.0, 4.0, 3.0, 6.0],
            "pass_ypp": [6.0, 5.0, 4.0, 7.0],
            "rush_ypp": [4.0, 3.0, 2.0, 5.0],
            "turnovers": [1, 2, 0, 1],
        }
    )


def test_feature_rows_use_only_previous_team_games() -> None:
    features = build_pregame_features(games(), team_stats())

    assert pd.isna(features.loc[0, "home_points_avg"])
    assert features.loc[1, "home_points_avg"] == 21
    assert features.loc[1, "home_points_allowed_avg"] == 14
    assert features.loc[1, "home_ypp"] == 5
    assert features.loc[1, "home_ypp_allowed"] == 4
    assert features.loc[1, "home_turnover_diff"] == 1
    assert features.loc[1, "home_last3_margin"] == 7
    assert features.loc[1, "division_game"]


def test_current_game_result_cannot_change_its_own_feature_row() -> None:
    changed_games = games()
    changed_games.loc[1, ["home_score", "away_score", "home_win"]] = [35, 0, 1]

    original = build_pregame_features(games(), team_stats())
    changed = build_pregame_features(changed_games, team_stats())

    columns = ["home_points_avg", "home_ypp", "home_last3_margin", "home_pre_game_elo"]
    assert original.loc[1, columns].equals(changed.loc[1, columns])


def test_missing_team_game_stats_raise_instead_of_silently_dropping_a_game() -> None:
    with pytest.raises(ValueError, match="missing team statistics"):
        build_pregame_features(games(), team_stats().iloc[:-1])


def test_week_one_uses_previous_season_strength_when_available() -> None:
    source = games()
    next_season_game = pd.DataFrame(
        {
            "game_id": ["three"], "season": [2021], "week": [1],
            "date": pd.to_datetime(["2021-09-12T17:00:00Z"]), "home": ["BUF"], "away": ["NYJ"],
            "home_score": [17], "away_score": [14], "home_win": [1],
            "home_rest": [7], "away_rest": [7], "division_game": [True],
        }
    )
    source = pd.concat([source, next_season_game], ignore_index=True)
    next_stats = pd.DataFrame(
        {
            "game_id": ["three", "three"], "team": ["BUF", "NYJ"],
            "ypp": [5.0, 4.0], "pass_ypp": [6.0, 5.0], "rush_ypp": [4.0, 3.0], "turnovers": [0, 1],
        }
    )
    stats = pd.concat([team_stats(), next_stats], ignore_index=True)

    features = build_pregame_features(source, stats)

    assert features.loc[2, "home_points_avg"] == 14
    assert pd.isna(features.loc[2, "home_last3_margin"])


def test_play_aggregation_calculates_efficiency_and_turnovers() -> None:
    plays = pd.DataFrame(
        {
            "game_id": ["one", "one", "one", "one", "one"],
            "season_type": ["REG", "REG", "REG", "REG", "POST"],
            "posteam": ["BUF", "BUF", "NYJ", "NYJ", "BUF"],
            "pass": [1, 0, 1, 0, 1], "rush": [0, 1, 0, 1, 0],
            "yards_gained": [10, 4, 6, 2, 99],
            "interception": [0, 0, 1, 0, 0], "fumble_lost": [1, 0, 0, 0, 0],
        }
    )

    output = aggregate_team_game_stats(plays).set_index("team")

    assert output.loc["BUF", "ypp"] == 7
    assert output.loc["BUF", "pass_ypp"] == 10
    assert output.loc["BUF", "rush_ypp"] == 4
    assert output.loc["BUF", "turnovers"] == 1
    assert output.loc["NYJ", "turnovers"] == 1
