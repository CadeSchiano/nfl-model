from datetime import datetime, timezone

import pandas as pd

from app.models.game import Game
from app.services.nfl_player_props_service import _project, _projection


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


def test_unavailable_player_is_excluded_from_projection_rows() -> None:
    roster = pd.DataFrame([{"gsis_id": "out-player", "full_name": "Out Player", "team": "TB", "position": "QB"}])
    player_games = pd.DataFrame(columns=["game_id", "team", "player_id", "player_name", "prop", "yards"])
    defense_allowed = pd.DataFrame(columns=["game_id", "team", "prop", "yards"])
    game = Game(id="g", season=2026, week=6, date=datetime(2026, 10, 11, tzinfo=timezone.utc), home_team="TB", away_team="ATL", status="scheduled")

    assert _project(roster, player_games, defense_allowed, {}, {"TB": (game, "ATL")}, {"out-player"}) == []
