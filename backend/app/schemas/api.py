from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class GameRead(ORMModel):
    id: str
    season: int
    week: int
    date: datetime
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None
    status: str


class OddsRead(ORMModel):
    id: int
    game_id: str
    bookmaker: str
    timestamp: datetime
    home_moneyline: int
    away_moneyline: int
    spread: float
    home_spread_odds: int
    away_spread_odds: int


class PredictionRead(ORMModel):
    id: int
    game_id: str
    model_version: str
    timestamp: datetime
    home_win_probability: float
    away_win_probability: float
    predicted_margin: float | None
    market_spread: float | None
    spread_difference: float | None
    market_home_probability: float | None
    moneyline_difference: float | None
