from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), index=True)
    odds_id: Mapped[int | None] = mapped_column(ForeignKey("odds.id"), nullable=True)
    model_version: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    home_win_probability: Mapped[float] = mapped_column(Float)
    away_win_probability: Mapped[float] = mapped_column(Float)
    predicted_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_spread: Mapped[float | None] = mapped_column(Float, nullable=True)
    spread_difference: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_home_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    moneyline_difference: Mapped[float | None] = mapped_column(Float, nullable=True)


class Result(Base):
    __tablename__ = "results"

    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.id"), primary_key=True)
    moneyline_result: Mapped[str | None] = mapped_column(String(8), nullable=True)
    spread_result: Mapped[str | None] = mapped_column(String(8), nullable=True)
    actual_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    closing_spread: Mapped[float | None] = mapped_column(Float, nullable=True)


class TouchdownPrediction(Base):
    __tablename__ = "touchdown_predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), index=True)
    player_id: Mapped[str] = mapped_column(String(32), index=True)
    player_name: Mapped[str] = mapped_column(String(120))
    team: Mapped[str] = mapped_column(String(8))
    model_version: Mapped[str] = mapped_column(String(64))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    probability: Mapped[float] = mapped_column(Float)
    td_score: Mapped[int] = mapped_column(Integer)
    two_td_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    two_td_call: Mapped[bool] = mapped_column(default=False)
    result: Mapped[str | None] = mapped_column(String(8), nullable=True)
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FirstTouchdownPrediction(Base):
    __tablename__ = "first_touchdown_predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), index=True)
    player_id: Mapped[str] = mapped_column(String(32), index=True)
    player_name: Mapped[str] = mapped_column(String(120))
    team: Mapped[str] = mapped_column(String(8))
    model_version: Mapped[str] = mapped_column(String(64))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    anytime_probability: Mapped[float] = mapped_column(Float)
    result: Mapped[str | None] = mapped_column(String(8), nullable=True)
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
