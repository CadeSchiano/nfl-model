"""Week-one live prediction generation using final prior-season strength."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.features import STRENGTH_METRICS, _mean_metrics, _team_game_record
from app.ml.predict import predict_home_margin, predict_home_win_probability
from app.ml.train import MODEL_FEATURE_COLUMNS
from app.models.game import Game
from app.models.prediction import Prediction
from app.services.elo_service import EloConfig, canonical_team_code, generate_elo_predictions
from app.services.nfl_data import download_team_game_stats


ROOT = Path(__file__).resolve().parents[3]


def generate_current_week_predictions(session: Session) -> int:
    game = session.scalar(select(Game).where(Game.status == "scheduled", Game.date >= datetime.now(timezone.utc)).order_by(Game.date))
    if game is None:
        return 0
    games = session.scalars(select(Game).where(Game.season == game.season, Game.week == game.week)).all()
    games = [game for game in games if session.scalar(select(Prediction.id).where(Prediction.game_id == game.id, Prediction.model_version == "logistic_v1")) is None]
    if not games:
        return 0
    features = _week_one_features(games)
    models = ROOT / "backend" / "app" / "ml" / "models"
    moneyline, spread = joblib.load(models / "logistic_v1.joblib"), joblib.load(models / "spread_ridge_v1.joblib")
    probabilities, margins = predict_home_win_probability(moneyline, features), predict_home_margin(spread, features)
    added = 0
    for game, probability, margin in zip(games, probabilities, margins):
        session.add(Prediction(game_id=game.id, model_version="logistic_v1", timestamp=datetime.now(timezone.utc), home_win_probability=float(probability), away_win_probability=float(1 - probability), predicted_margin=float(margin)))
        added += 1
    session.commit()
    return added


def _week_one_features(live_games: list[Game]) -> pd.DataFrame:
    history = pd.read_csv(ROOT / "data" / "processed" / "games_2015_2025.csv", parse_dates=["date"])
    season = history[history.season == 2025].sort_values("date")
    stats = download_team_game_stats([2025]).set_index(["game_id", "team"])
    state: dict[str, list[dict]] = {}
    for row in season.itertuples(index=False):
        home, away = canonical_team_code(row.home), canonical_team_code(row.away)
        own = stats.loc[(row.game_id, row.home)].to_dict(); opponent = stats.loc[(row.game_id, row.away)].to_dict()
        state.setdefault(home, []).append(_team_game_record(row, own, opponent, True))
        state.setdefault(away, []).append(_team_game_record(row, opponent, own, False))
    strength = {team: _mean_metrics(records) for team, records in state.items()}
    elo = generate_elo_predictions(history)
    ratings: dict[str, float] = {}
    for row in elo.itertuples(index=False):
        result = 1.0 if row.home_score > row.away_score else 0.5 if row.home_score == row.away_score else 0.0
        delta = EloConfig().k_factor * (result - row.home_win_probability)
        ratings[canonical_team_code(row.home)] = row.home_pre_game_elo + delta
        ratings[canonical_team_code(row.away)] = row.away_pre_game_elo - delta
    ratings = {team: 1500 + (rating - 1500) * EloConfig().offseason_regression for team, rating in ratings.items()}
    rows = []
    for game in live_games:
        home, away = strength[game.home_team], strength[game.away_team]
        row = {f"home_{name}": home[name] for name in STRENGTH_METRICS} | {f"away_{name}": away[name] for name in STRENGTH_METRICS}
        row.update({"home_last3_margin": sum(x["point_diff"] for x in state[game.home_team][-3:]) / min(3, len(state[game.home_team])), "away_last3_margin": sum(x["point_diff"] for x in state[game.away_team][-3:]) / min(3, len(state[game.away_team])), "home_last5_margin": sum(x["point_diff"] for x in state[game.home_team][-5:]) / min(5, len(state[game.home_team])), "away_last5_margin": sum(x["point_diff"] for x in state[game.away_team][-5:]) / min(5, len(state[game.away_team]))})
        row.update({"home_elo": ratings[game.home_team], "away_elo": ratings[game.away_team], "elo_diff": ratings[game.home_team] - ratings[game.away_team], "rest_diff": (game.home_rest or 0) - (game.away_rest or 0), "division_game": game.division_game})
        rows.append(row)
    return pd.DataFrame(rows)[MODEL_FEATURE_COLUMNS]
