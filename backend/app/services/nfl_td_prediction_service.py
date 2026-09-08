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
from app.services.nfl_td_data import download_active_roster, download_td_player_games

ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = ROOT / "backend/app/ml/models/td/nfl_td_logistic_v1.joblib"
HISTORY_PATH = ROOT / "data/processed/nfl_td_player_games_2019_2025.parquet"
MODEL_VERSION = "nfl_td_logistic_v1"


def publish_touchdown_predictions(session: Session) -> int:
    """Publish the top two or three active skill players for each next-week game."""
    now = datetime.now(timezone.utc)
    next_game = session.scalar(select(Game).where(Game.status == "scheduled", Game.date >= now).order_by(Game.date))
    if next_game is None:
        return 0
    games = session.scalars(select(Game).where(Game.season == next_game.season, Game.week == next_game.week, Game.status == "scheduled").order_by(Game.date)).all()
    if not MODEL_PATH.exists() or not HISTORY_PATH.exists():
        raise FileNotFoundError("Build TD history and train the TD model before publishing predictions.")
    artifact = joblib.load(MODEL_PATH)
    roster = download_active_roster(next_game.season, next_game.week)
    candidates = _active_player_features(roster, pd.read_parquet(HISTORY_PATH))
    if candidates.empty:
        return 0
    candidates["probability"] = artifact["model"].predict_proba(candidates[FEATURES])[:, 1]
    two_model = artifact.get("two_td_model")
    candidates["two_td_probability"] = two_model.predict_proba(candidates[FEATURES])[:, 1] if two_model else 0.0
    candidates["td_score"] = (candidates.probability.rank(pct=True, method="average") * 100).round().clip(1, 100).astype(int)
    added = 0
    for game in games:
        game_candidates = candidates.loc[candidates.team.isin([game.home_team, game.away_team])].sort_values("probability", ascending=False).head(3).copy()
        if game_candidates.empty:
            continue
        # A 2+ TD call is intentionally rare: at most one per game and only at 8%+.
        two_td_index = game_candidates.two_td_probability.idxmax()
        for index, player in game_candidates.iterrows():
            exists = session.scalar(select(TouchdownPrediction.id).where(TouchdownPrediction.game_id == game.id, TouchdownPrediction.player_id == player.player_id, TouchdownPrediction.model_version == MODEL_VERSION))
            if exists is not None:
                continue
            session.add(TouchdownPrediction(game_id=game.id, player_id=str(player.player_id), player_name=player.player_name, team=player.team, model_version=MODEL_VERSION, timestamp=now, probability=float(player.probability), td_score=int(player.td_score), two_td_probability=float(player.two_td_probability), two_td_call=bool(index == two_td_index and player.two_td_probability >= 0.08)))
            added += 1
    session.commit()
    return added


def grade_touchdown_predictions(session: Session) -> int:
    """Grade immutable TD predictions for games whose final score is available."""
    pending = session.execute(select(TouchdownPrediction, Game).join(Game).where(TouchdownPrediction.result.is_(None), Game.home_score.is_not(None), Game.away_score.is_not(None))).all()
    if not pending:
        return 0
    game_ids = {game.id for _, game in pending}
    seasons = sorted({game.season for _, game in pending})
    completed = download_td_player_games(seasons)
    scored = set(zip(completed.game_id.astype(str), completed.loc[completed.scored_touchdown.eq(1), "player_id"].astype(str)))
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
