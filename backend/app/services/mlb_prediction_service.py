"""Schedule import and locked, lineup-gated MLB HR prediction publishing."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mlb import MlbGame, MlbHrPrediction, MlbModelVersion, MlbPlayerGame
from app.services.mlb_data import MLB_GAME_TYPES, _dt, _get, get_live_feed
from app.services.mlb_feature_service import ROLLING_WINDOW


def update_schedule(session: Session, game_date: date | None = None) -> int:
    """Upsert the day's regular-season or postseason schedule and pitchers."""
    game_date = game_date or date.today()
    schedule = _get("schedule", {"sportId": 1, "gameType": MLB_GAME_TYPES, "date": game_date.isoformat(), "hydrate": "probablePitcher"})
    updated = 0
    for day in schedule.get("dates", []):
        for item in day.get("games", []):
            game_id = int(item["gamePk"])
            game = session.get(MlbGame, game_id)
            if game is None:
                game = MlbGame(
                    id=game_id,
                    game_date=_dt(item["gameDate"]),
                    official_date=date.fromisoformat(item["officialDate"]),
                    home_team=item["teams"]["home"]["team"]["name"],
                    away_team=item["teams"]["away"]["team"]["name"],
                    home_score=None,
                    away_score=None,
                    # Results are imported only from the detailed game feed,
                    # which guarantees a score before a game becomes final.
                    status="scheduled",
                )
                session.add(game)
            if game.status != "final" or game.home_score is None or game.away_score is None:
                game.status = "scheduled"
                game.probable_home_pitcher = item["teams"]["home"].get("probablePitcher", {}).get("fullName")
                game.probable_away_pitcher = item["teams"]["away"].get("probablePitcher", {}).get("fullName")
            updated += 1
    session.commit()
    return updated


def confirmed_batters(feed: dict) -> list[dict]:
    """Return starters only when both teams have all nine batting slots assigned."""
    teams = feed.get("liveData", {}).get("boxscore", {}).get("teams", {})
    starters: list[dict] = []
    for side in ("away", "home"):
        team = teams.get(side, {})
        side_starters = []
        for player in team.get("players", {}).values():
            order = str(player.get("battingOrder", "0000"))
            if order.isdigit() and int(order) > 0:
                side_starters.append({
                    "player_id": int(player["person"]["id"]),
                    "player_name": player["person"]["fullName"],
                    "team": team.get("team", {}).get("name"),
                    "batting_order": int(order),
                })
        # The MLB feed exposes confirmed starters via their nine batting-order slots.
        if len(side_starters) != 9:
            return []
        starters.extend(sorted(side_starters, key=lambda player: player["batting_order"]))
    return starters


def publish_hr_predictions(session: Session, now: datetime | None = None) -> int:
    """Publish one immutable HR probability per confirmed lineup starter before first pitch."""
    now = now or datetime.now(timezone.utc)
    latest_model = session.scalar(select(MlbModelVersion).order_by(MlbModelVersion.trained_at.desc()))
    if latest_model is None:
        raise ValueError("train an MLB HR model before publishing predictions")
    artifact = Path(latest_model.artifact_path)
    if not artifact.exists():
        raise FileNotFoundError(f"MLB model artifact is missing: {artifact}")
    payload = joblib.load(artifact)
    model, columns = payload["model"], payload["features"]
    games = session.scalars(select(MlbGame).where(MlbGame.status == "scheduled", MlbGame.game_date > now).order_by(MlbGame.game_date)).all()
    created = 0
    for game in games:
        starters = confirmed_batters(get_live_feed(game.id))
        if not starters:
            continue
        for starter in starters:
            # Existing picks are permanent—even a retrained model may not replace them.
            exists = session.scalar(select(MlbHrPrediction.id).where(MlbHrPrediction.game_id == game.id, MlbHrPrediction.player_id == starter["player_id"]))
            if exists is not None:
                continue
            feature = _pregame_batter_features(session, starter["player_id"], game.game_date)
            if feature["prior_games"] == 0:
                continue
            probability = float(model.predict_proba(pd.DataFrame([feature])[columns])[:, 1][0])
            session.add(MlbHrPrediction(
                game_id=game.id,
                player_id=starter["player_id"],
                player_name=starter["player_name"],
                team=starter["team"],
                model_version=latest_model.version,
                timestamp=now,
                first_pitch=game.game_date,
                probability=probability,
            ))
            created += 1
    session.commit()
    return created


def _pregame_batter_features(session: Session, player_id: int, first_pitch: datetime) -> dict[str, float | int]:
    rows = session.execute(
        select(MlbPlayerGame.home_runs, MlbPlayerGame.plate_appearances)
        .join(MlbGame, MlbGame.id == MlbPlayerGame.game_id)
        .where(MlbPlayerGame.player_id == player_id, MlbPlayerGame.plate_appearances.is_not(None), MlbGame.status == "final", MlbGame.game_date < first_pitch)
        .order_by(MlbGame.game_date.desc())
        .limit(ROLLING_WINDOW)
    ).all()
    prior_games = len(rows)
    prior_pa = sum(pa or 0 for _, pa in rows)
    prior_hr = sum(hr for hr, _ in rows)
    return {"prior_games": prior_games, "prior_plate_appearances": prior_pa, "prior_home_runs": prior_hr, "hr_per_plate_appearance": (prior_hr / prior_pa) if prior_pa else 0.0}
