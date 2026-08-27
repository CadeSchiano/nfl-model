import pandas as pd
import pytest

from app.services.elo_service import (
    EloConfig,
    canonical_team_code,
    evaluate_elo_predictions,
    expected_home_win_probability,
    generate_elo_predictions,
)


def games() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game_id": ["one", "two"], "season": [2020, 2020], "week": [1, 2],
            "date": pd.to_datetime(["2020-09-13T17:00:00Z", "2020-09-20T17:00:00Z"]),
            "home": ["BUF", "NYJ"], "away": ["NYJ", "BUF"],
            "home_score": [24, 14], "away_score": [14, 21], "home_win": [1, 0],
        }
    )


def test_expected_probability_is_even_without_home_field_advantage() -> None:
    assert expected_home_win_probability(1500, 1500, 0) == 0.5


def test_predictions_record_pregame_values_before_rating_updates() -> None:
    output = generate_elo_predictions(games(), EloConfig(home_field_advantage=0, k_factor=20))

    assert output.loc[0, "home_pre_game_elo"] == 1500
    assert output.loc[0, "away_pre_game_elo"] == 1500
    assert output.loc[0, "home_win_probability"] == 0.5
    assert output.loc[1, "home_pre_game_elo"] == 1490
    assert output.loc[1, "away_pre_game_elo"] == 1510
    assert output.loc[1, "home_win_probability"] < 0.5


def test_a_game_result_cannot_change_its_own_pregame_prediction() -> None:
    source = games()
    changed_result = source.copy()
    changed_result.loc[1, ["home_score", "away_score", "home_win"]] = [35, 7, 1]

    original = generate_elo_predictions(source)
    changed = generate_elo_predictions(changed_result)

    assert original.loc[1, "home_win_probability"] == changed.loc[1, "home_win_probability"]


def test_offseason_regression_is_applied_before_first_new_season_game() -> None:
    source = games().iloc[[0]].copy()
    next_season = source.copy()
    next_season.loc[:, ["game_id", "season", "week", "date", "home", "away"]] = [
        "two", 2021, 1, pd.Timestamp("2021-09-12", tz="UTC"), "NYJ", "BUF"
    ]
    source = pd.concat([source, next_season], ignore_index=True)

    output = generate_elo_predictions(source, EloConfig(home_field_advantage=0, offseason_regression=0.70))

    assert output.loc[1, "home_pre_game_elo"] == pytest.approx(1493.0)
    assert output.loc[1, "away_pre_game_elo"] == pytest.approx(1507.0)


def test_evaluation_excludes_ties_from_binary_metrics() -> None:
    predictions = pd.DataFrame(
        {
            "home_win_probability": [0.75, 0.25, 0.50], "home_win": [1, 0, 0],
            "home_score": [21, 10, 14], "away_score": [14, 7, 14],
        }
    )

    metrics = evaluate_elo_predictions(predictions)

    assert metrics == {"games": 3, "evaluated_games": 2, "ties_excluded": 1, "accuracy": 1.0, "brier_score": 0.0625}


def test_historical_franchise_aliases_preserve_rating_history() -> None:
    assert canonical_team_code("OAK") == "LV"
    assert canonical_team_code("LA") == "LAR"
