from datetime import datetime, timezone

from app.models.game import Game
from app.models.prediction import Prediction
from app.services.odds_linking_service import _best_snapshot
from app.services.odds_service import OddsSnapshot


def test_linking_uses_latest_snapshot_before_prediction_time() -> None:
    game = Game(id="game", season=2026, week=1, date=datetime(2026, 9, 10, tzinfo=timezone.utc), home_team="BUF", away_team="NYJ", status="scheduled")
    prediction = Prediction(game_id="game", model_version="logistic_v1", timestamp=datetime(2026, 8, 28, tzinfo=timezone.utc), home_win_probability=.6, away_win_probability=.4)
    old = OddsSnapshot("event", "2026-09-10T00:00:00Z", "BUF", "NYJ", "book", "2026-08-26T00:00:00Z", -120, 100, -2.5, -110, 2.5, -110)
    newer = OddsSnapshot("event", "2026-09-10T00:00:00Z", "BUF", "NYJ", "book", "2026-08-27T00:00:00Z", -130, 110, -3.0, -110, 3.0, -110)

    assert _best_snapshot([old, newer], game, prediction.timestamp) == newer
