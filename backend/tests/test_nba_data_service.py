from datetime import datetime, timezone

from app.services.nba_data_service import _made, _minutes, _number, _team_code
from app.services.nba_prediction_service import _starter_prediction_cutoff


def test_parses_espn_box_score_values() -> None:
    assert _minutes("31:30") == 31.5
    assert _minutes("--") == 0.0
    assert _made("4-11") == 4.0
    assert _number("18") == 18.0


def test_bad_box_score_values_fall_back_to_zero() -> None:
    assert _minutes("not-a-minute") == 0.0
    assert _number("—") == 0.0


def test_missing_espn_team_abbreviation_is_skipped() -> None:
    assert _team_code({"team": {"displayName": "Unknown"}}) is None


def test_starter_props_cutoff_includes_today_and_tomorrow_eastern() -> None:
    now = datetime(2026, 10, 20, 20, tzinfo=timezone.utc)
    assert _starter_prediction_cutoff(now) == datetime(2026, 10, 22, 4, tzinfo=timezone.utc)
