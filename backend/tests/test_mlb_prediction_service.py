from app.services.mlb_prediction_service import confirmed_batters


def test_confirmed_batters_requires_nine_batting_slots_per_team() -> None:
    def team(name, offset):
        return {"team": {"name": name}, "players": {str(offset + number): {"person": {"id": offset + number, "fullName": f"{name} {number}"}, "battingOrder": str(number * 100)} for number in range(1, 10)}}

    feed = {"liveData": {"boxscore": {"teams": {"away": team("Away", 100), "home": team("Home", 200)}}}}
    lineup = confirmed_batters(feed)
    assert len(lineup) == 18
    assert lineup[0]["player_name"] == "Away 1"
    del feed["liveData"]["boxscore"]["teams"]["home"]["players"]["209"]
    assert confirmed_batters(feed) == []
