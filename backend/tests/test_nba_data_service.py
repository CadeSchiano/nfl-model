from app.services.nba_data_service import _made, _minutes, _number, _team_code


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
