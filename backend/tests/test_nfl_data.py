import pandas as pd
import pytest

from app.services.nfl_data import DataValidationError, build_historical_games


def raw_games() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game_id": ["2020_01_BUF_NYJ", "2020_01_ARI_SF"],
            "season": [2020, 2020], "week": [1, 1], "game_type": ["REG", "REG"],
            "gameday": ["2020-09-13", "2020-09-13"], "gametime": ["17:00", "17:00"],
            "home_team": ["NYJ", "SF"], "away_team": ["BUF", "ARI"],
            "home_score": [17, 20], "away_score": [27, 24], "spread_line": [-6.5, 3.0],
            "home_moneyline": [250, 130], "away_moneyline": [-300, -150],
            "home_rest": [7, 7], "away_rest": [7, 7],
        }
    )


def test_build_historical_games_adds_labels_and_orders_games() -> None:
    games, report = build_historical_games(raw_games(), seasons=[2020])

    assert list(games["game_id"]) == ["2020_01_ARI_SF", "2020_01_BUF_NYJ"]
    assert list(games["home_win"]) == [0, 0]
    assert list(games["margin"]) == [-4, -10]
    assert list(games["rest"]) == [0, 0]
    assert report.warnings == ()


def test_build_historical_games_rejects_unknown_team_mapping() -> None:
    source = raw_games()
    source.loc[0, "home_team"] = "XXX"

    with pytest.raises(DataValidationError, match="unmapped historical team"):
        build_historical_games(source, seasons=[2020])


def test_build_historical_games_reports_missing_market_data() -> None:
    source = raw_games()
    source.loc[0, "spread_line"] = None

    _, report = build_historical_games(source, seasons=[2020])

    assert "spread: 1 missing values retained as null" in report.warnings
