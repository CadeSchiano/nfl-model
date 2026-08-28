"""Attach immutable local odds snapshots to pregame predictions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.game import Game
from app.models.odds import Odds
from app.models.prediction import Prediction
from app.services.odds_service import OddsSnapshot, compare_model_to_market


def link_saved_odds(session: Session, snapshots_path: Path) -> int:
    """Link only currently unlinked, pre-kickoff predictions to saved snapshots."""
    if not snapshots_path.exists():
        return 0
    snapshots = [_snapshot(line) for line in snapshots_path.read_text().splitlines() if line.strip()]
    linked = 0
    rows = session.execute(select(Prediction, Game).join(Game).where(Prediction.odds_id.is_(None))).all()
    for prediction, game in rows:
        candidate = _best_snapshot(snapshots, game, prediction.timestamp)
        if candidate is None:
            continue
        odds = Odds(
            game_id=game.id, bookmaker=candidate.bookmaker, timestamp=_parse_datetime(candidate.timestamp),
            home_moneyline=candidate.home_moneyline, away_moneyline=candidate.away_moneyline,
            spread=candidate.home_spread, home_spread_odds=candidate.home_spread_odds, away_spread_odds=candidate.away_spread_odds,
        )
        session.add(odds)
        session.flush()
        comparison = compare_model_to_market(prediction.home_win_probability, prediction.predicted_margin or 0.0, candidate)
        prediction.odds_id = odds.id
        prediction.market_spread = candidate.home_spread
        prediction.spread_difference = float(comparison["spread_difference"])
        prediction.market_home_probability = float(comparison["market_home_probability"])
        prediction.moneyline_difference = float(comparison["moneyline_difference"])
        linked += 1
    session.commit()
    return linked


def _snapshot(line: str) -> OddsSnapshot:
    return OddsSnapshot(**json.loads(line))


def _best_snapshot(snapshots: list[OddsSnapshot], game: Game, prediction_time: datetime) -> OddsSnapshot | None:
    prediction_time = _parse_datetime(prediction_time)
    kickoff = _parse_datetime(game.date)
    eligible = [snapshot for snapshot in snapshots if snapshot.home_team == game.home_team and snapshot.away_team == game.away_team and abs((_parse_datetime(snapshot.commence_time) - kickoff).total_seconds()) <= 900 and _parse_datetime(snapshot.timestamp) <= prediction_time]
    return max(eligible, key=lambda snapshot: _parse_datetime(snapshot.timestamp), default=None)


def _parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
