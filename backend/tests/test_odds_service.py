import json

import pytest

from app.services.odds_service import (
    OddsSnapshot,
    american_to_implied_probability,
    append_odds_snapshots,
    compare_model_to_market,
    no_vig_probabilities,
    normalize_odds_events,
)


def sample_event() -> dict:
    return {
        "id": "event-1", "commence_time": "2026-09-10T00:20:00Z",
        "home_team": "Buffalo Bills", "away_team": "New York Jets",
        "bookmakers": [{
            "key": "draftkings", "last_update": "2026-09-01T12:00:00Z",
            "markets": [
                {"key": "h2h", "outcomes": [
                    {"name": "Buffalo Bills", "price": -150}, {"name": "New York Jets", "price": 130},
                ]},
                {"key": "spreads", "outcomes": [
                    {"name": "Buffalo Bills", "point": -3.5, "price": -110},
                    {"name": "New York Jets", "point": 3.5, "price": -110},
                ]},
            ],
        }],
    }


def test_american_odds_conversion() -> None:
    assert american_to_implied_probability(-150) == pytest.approx(0.6)
    assert american_to_implied_probability(200) == pytest.approx(1 / 3)
    with pytest.raises(ValueError):
        american_to_implied_probability(0)


def test_vig_removal_normalizes_to_fair_two_way_market() -> None:
    home, away = no_vig_probabilities(-150, 130)

    assert home + away == pytest.approx(1.0)
    assert home == pytest.approx(0.5798, abs=0.0001)


def test_normalization_preserves_complete_bookmaker_snapshot() -> None:
    snapshots, warnings = normalize_odds_events([sample_event()])

    assert warnings == []
    assert snapshots == [
        OddsSnapshot("event-1", "2026-09-10T00:20:00Z", "BUF", "NYJ", "draftkings", "2026-09-01T12:00:00Z", -150, 130, -3.5, -110, 3.5, -110)
    ]


def test_append_never_overwrites_prior_snapshot(tmp_path) -> None:
    snapshots, _ = normalize_odds_events([sample_event()])
    destination = tmp_path / "odds.jsonl"

    append_odds_snapshots(snapshots, destination)
    append_odds_snapshots(snapshots, destination)

    assert len(destination.read_text().splitlines()) == 2
    assert json.loads(destination.read_text().splitlines()[0])["bookmaker"] == "draftkings"


def test_market_comparison_uses_home_margin_sign_and_discrepancy_labels() -> None:
    snapshot, _ = normalize_odds_events([sample_event()])

    comparison = compare_model_to_market(0.64, 6.1, snapshot[0])

    assert comparison["market_home_margin"] == 3.5
    assert comparison["spread_difference"] == pytest.approx(2.6)
    assert comparison["spread_discrepancy"] == "moderate"
    assert comparison["moneyline_discrepancy"] == "moderate"
