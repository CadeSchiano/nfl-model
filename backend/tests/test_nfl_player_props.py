from app.services.nfl_player_props_service import _projection


def test_projection_uses_player_average_when_matchup_is_league_average() -> None:
    assert _projection(80.0, 300.0, 300.0) == 80.0


def test_projection_bounds_extreme_matchup_effects() -> None:
    assert _projection(80.0, 900.0, 300.0) == 86.0
    assert _projection(80.0, 0.0, 300.0) == 74.0


def test_projection_rejects_invalid_player_average() -> None:
    try:
        _projection(-1.0, 300.0, 300.0)
    except ValueError as error:
        assert str(error) == "player average cannot be negative"
    else:
        raise AssertionError("a negative player average must fail")
