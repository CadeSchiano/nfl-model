"""Publishing and grading for the isolated NFL anytime-touchdown model."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.nfl_td_model import FEATURES
from app.models.game import Game
from app.models.prediction import TouchdownPrediction
from app.models.player_availability import NflPlayerAvailability
from app.models.td_availability import NflTdAvailability
from app.services.nfl_td_data import download_active_roster, download_td_player_games

ROOT = Path(__file__).resolve().parents[3]
MODEL_DIRECTORY = ROOT / "backend/app/ml/models/td"
HISTORY_PATH = ROOT / "data/processed/nfl_td_player_games_2019_current.parquet"
BASE_HISTORY_PATH = ROOT / "data/processed/nfl_td_player_games_2019_2025.parquet"


def publish_touchdown_predictions(session: Session) -> int:
    """Publish three core TD picks plus an eligible usage-backed longshot."""
    now = datetime.now(timezone.utc)
    next_game = session.scalar(select(Game).where(Game.status == "scheduled", Game.date >= now).order_by(Game.date))
    if next_game is None:
        return 0
    games = session.scalars(select(Game).where(Game.season == next_game.season, Game.week == next_game.week, Game.status == "scheduled").order_by(Game.date)).all()
    model_path = _latest_model_path()
    history_path = HISTORY_PATH if HISTORY_PATH.exists() else BASE_HISTORY_PATH
    if model_path is None or not history_path.exists():
        raise FileNotFoundError("Build TD history and train the TD model before publishing predictions.")
    artifact = joblib.load(model_path)
    model_version = artifact.get("model_version", model_path.stem)
    roster = download_active_roster(next_game.season, next_game.week)
    candidates = _active_player_features(roster, pd.read_parquet(history_path))
    if candidates.empty:
        return 0
    candidates["probability"] = artifact["model"].predict_proba(candidates[FEATURES])[:, 1]
    two_model = artifact.get("two_td_model")
    candidates["two_td_probability"] = two_model.predict_proba(candidates[FEATURES])[:, 1] if two_model else 0.0
    candidates["td_score"] = (candidates.probability.rank(pct=True, method="average") * 100).round().clip(1, 100).astype(int)
    added = 0
    for game in games:
        _void_unavailable_predictions(session, game.id)
        unavailable = set(session.scalars(select(NflTdAvailability.player_id).where(NflTdAvailability.game_id == game.id, NflTdAvailability.status == "OUT")).all())
        unavailable.update(session.scalars(select(NflPlayerAvailability.player_id).where(NflPlayerAvailability.status == "OUT")).all())
        game_candidates = candidates.loc[candidates.team.isin([game.home_team, game.away_team]) & ~candidates.player_id.isin(unavailable)].sort_values("probability", ascending=False).copy()
        if game_candidates.empty:
            continue
        regular_ids = set(session.scalars(select(TouchdownPrediction.player_id).where(TouchdownPrediction.game_id == game.id, TouchdownPrediction.publication_status == "ACTIVE", TouchdownPrediction.is_longshot.is_(False))).all())
        missing = max(0, 3 - len(regular_ids))
        if missing:
            # A 2+ TD call is intentionally rare: at most one per game and only at 8%+.
            two_td_index = game_candidates.two_td_probability.idxmax()
            for index, player in game_candidates.iterrows():
                if str(player.player_id) in regular_ids:
                    continue
                # Do not resurrect a manually voided player in the same game.
                exists = session.scalar(select(TouchdownPrediction.id).where(TouchdownPrediction.game_id == game.id, TouchdownPrediction.player_id == str(player.player_id)))
                if exists is not None:
                    continue
                session.add(TouchdownPrediction(game_id=game.id, player_id=str(player.player_id), player_name=player.player_name, team=player.team, model_version=model_version, timestamp=now, probability=float(player.probability), td_score=int(player.td_score), two_td_probability=float(player.two_td_probability), two_td_call=bool(index == two_td_index and player.two_td_probability >= 0.08), is_longshot=False, publication_status="ACTIVE"))
                added += 1
                regular_ids.add(str(player.player_id))
                missing -= 1
                if missing == 0:
                    break
        existing_longshot = session.scalar(select(TouchdownPrediction.id).where(TouchdownPrediction.game_id == game.id, TouchdownPrediction.publication_status == "ACTIVE", TouchdownPrediction.is_longshot.is_(True)))
        if existing_longshot is None:
            longshots = game_candidates.loc[
                ~game_candidates.player_id.astype(str).isin(regular_ids)
                & (game_candidates.probability >= 0.10)
                & (game_candidates.probability <= 0.30)
                & ((game_candidates.carries_avg + game_candidates.targets_avg) >= 3)
            ]
            if not longshots.empty:
                player = longshots.iloc[0]
                exists = session.scalar(select(TouchdownPrediction.id).where(TouchdownPrediction.game_id == game.id, TouchdownPrediction.player_id == str(player.player_id)))
                if exists is None:
                    session.add(TouchdownPrediction(game_id=game.id, player_id=str(player.player_id), player_name=player.player_name, team=player.team, model_version=model_version, timestamp=now, probability=float(player.probability), td_score=int(player.td_score), two_td_probability=float(player.two_td_probability), two_td_call=False, is_longshot=True, publication_status="ACTIVE"))
                    added += 1
    session.commit()
    return added


def grade_touchdown_predictions(session: Session, regrade: bool = False) -> int:
    """Grade immutable TD predictions for games whose final score is available."""
    statement = select(TouchdownPrediction, Game).join(Game).where(Game.home_score.is_not(None), Game.away_score.is_not(None), TouchdownPrediction.publication_status == "ACTIVE")
    if not regrade:
        statement = statement.where(TouchdownPrediction.result.is_(None))
    pending = session.execute(statement).all()
    if not pending:
        return 0
    game_ids = {game.id for _, game in pending}
    seasons = sorted({game.season for _, game in pending})
    completed = download_td_player_games(seasons)
    touchdown_rows = completed.loc[completed.scored_touchdown.eq(1), ["game_id", "player_id"]]
    scored = set(zip(touchdown_rows.game_id.astype(str), touchdown_rows.player_id.astype(str)))
    graded = 0
    now = datetime.now(timezone.utc)
    for prediction, game in pending:
        if game.id not in game_ids:
            continue
        prediction.result = "HIT" if (str(game.id), str(prediction.player_id)) in scored else "MISS"
        prediction.graded_at = now
        graded += 1
    session.commit()
    return graded


def _active_player_features(roster: pd.DataFrame, history: pd.DataFrame) -> pd.DataFrame:
    """Calculate only trailing pregame values from completed 2019–25 player games."""
    data = history.copy()
    data["player_id"] = data.player_id.astype(str)
    roster = roster.rename(columns={"full_name": "player_name", "gsis_id": "player_id"}).copy()
    roster["player_id"] = roster.player_id.astype(str)
    trailing = data.sort_values(["player_id", "game_id"]).groupby("player_id", as_index=False).tail(5)
    summary = trailing.groupby("player_id", as_index=False).agg(prior_games=("game_id", "size"), carries_avg=("carries", "mean"), targets_avg=("targets", "mean"), td_rate=("scored_touchdown", "mean"))
    return roster.merge(summary, on="player_id", how="inner")[["player_id", "player_name", "team", *FEATURES]]


def _latest_model_path() -> Path | None:
    models = sorted(MODEL_DIRECTORY.glob("nfl_td_*.joblib"), key=lambda path: path.stat().st_mtime, reverse=True)
    return models[0] if models else None


def _void_unavailable_predictions(session: Session, game_id: str) -> int:
    unavailable = set(session.scalars(select(NflTdAvailability.player_id).where(NflTdAvailability.game_id == game_id, NflTdAvailability.status == "OUT")).all())
    if not unavailable:
        return 0
    predictions = session.scalars(select(TouchdownPrediction).where(TouchdownPrediction.game_id == game_id, TouchdownPrediction.publication_status == "ACTIVE")).all()
    now = datetime.now(timezone.utc); voided = 0
    for prediction in predictions:
        if prediction.player_id in unavailable:
            prediction.publication_status, prediction.voided_at = "VOID", now
            voided += 1
    return voided
