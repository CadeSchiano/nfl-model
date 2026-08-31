from app.services.mlb_data import _appearance_and_hr


def test_extracts_actual_appearances_and_home_runs() -> None:
    feed = {"liveData": {"plays": {"allPlays": [{"matchup": {"batter": {"id": 10}, "pitcher": {"id": 20}}, "result": {"eventType": "home_run"}}, {"matchup": {"batter": {"id": 10}, "pitcher": {"id": 21}}, "result": {"eventType": "strikeout"}}]}}}
    appeared, homers = _appearance_and_hr(feed)
    assert appeared == {10, 20, 21}
    assert homers == {10: 1}
