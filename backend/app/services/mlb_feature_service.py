"""Leakage-safe historical feature refresh for MLB batter games."""

from __future__ import annotations

from collections import defaultdict, deque

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mlb import MlbBatterFeature, MlbGame, MlbPlayerGame


ROLLING_WINDOW = 30


def refresh_batter_features(session: Session) -> int:
    """Rebuild each completed batter-game's pregame rolling history.

    Every feature row is calculated before that game's result is added to the
    player's history.  Rebuilding is safe because these source results are
    immutable completed-game records.
    """
    rows = session.execute(
        select(MlbPlayerGame, MlbGame.game_date)
        .join(MlbGame, MlbGame.id == MlbPlayerGame.game_id)
        .where(MlbGame.status == "final", MlbPlayerGame.plate_appearances.is_not(None))
        .order_by(MlbPlayerGame.player_id, MlbGame.game_date, MlbPlayerGame.game_id)
    ).all()
    histories: dict[int, deque[tuple[int, int]]] = defaultdict(lambda: deque(maxlen=ROLLING_WINDOW))
    updated = 0
    for player_game, game_date in rows:
        history = histories[player_game.player_id]
        prior_games = len(history)
        prior_pa = sum(pa for _, pa in history)
        prior_hr = sum(hr for hr, _ in history)
        feature = session.scalar(
            select(MlbBatterFeature).where(
                MlbBatterFeature.game_id == player_game.game_id,
                MlbBatterFeature.player_id == player_game.player_id,
            )
        )
        values = dict(
            as_of=game_date,
            prior_games=prior_games,
            prior_plate_appearances=prior_pa,
            prior_home_runs=prior_hr,
            hr_per_plate_appearance=(prior_hr / prior_pa) if prior_pa else 0.0,
        )
        if feature is None:
            session.add(MlbBatterFeature(game_id=player_game.game_id, player_id=player_game.player_id, **values))
        else:
            for field, value in values.items():
                setattr(feature, field, value)
        history.append((player_game.home_runs, player_game.plate_appearances or 0))
        updated += 1
    session.commit()
    return updated
