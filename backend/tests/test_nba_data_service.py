from datetime import date, datetime, timezone

import requests

from app.services import nba_data_service
from app.services.nba_data_service import _made, _minutes, _number, _team_code, nba_team_roster, update_completed_nba_games
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


def test_missing_espn_summary_is_skipped(monkeypatch) -> None:
    response = requests.Response(); response.status_code = 404
    def missing_summary(*_args, **_kwargs):
        raise requests.HTTPError(response=response)
    monkeypatch.setattr(nba_data_service, "_get", missing_summary)
    assert nba_data_service._summary_or_none("missing") is None


def test_current_roster_maps_espn_players(monkeypatch) -> None:
    monkeypatch.setattr(nba_data_service, "_nba_team_ids", lambda: {"ATL": "1"})
    monkeypatch.setattr(
        nba_data_service,
        "_get",
        lambda *_args, **_kwargs: {
            "athletes": [
                {
                    "id": "42",
                    "displayName": "Example Player",
                    "position": {"abbreviation": "G"},
                }
            ]
        },
    )

    assert nba_team_roster("atl") == [
        {
            "player_id": "42",
            "player_name": "Example Player",
            "team": "ATL",
            "position": "G",
        }
    ]


def test_existing_scheduled_game_still_fetches_final_box_score(monkeypatch) -> None:
    event = {
        "id": "final-game",
        "status": {"type": {"name": "STATUS_FINAL"}},
    }
    fetched = []

    class FakeSession:
        def get(self, _model, game_id):
            return object() if game_id == "final-game" else None

        def commit(self):
            return None

    monkeypatch.setattr(nba_data_service, "_get", lambda *_args, **_kwargs: {"events": [event]})
    monkeypatch.setattr(nba_data_service, "_upsert_game", lambda *_args: False)
    monkeypatch.setattr(nba_data_service, "_summary_or_none", lambda game_id: fetched.append(game_id) or {})
    monkeypatch.setattr(nba_data_service, "_upsert_boxscore", lambda *_args: None)

    assert update_completed_nba_games(FakeSession(), date(2026, 10, 21), date(2026, 10, 21)) == 1
    assert fetched == ["final-game"]
