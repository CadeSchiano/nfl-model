"""Isolated FBS-only college-football totals tables."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class CfbGame(Base):
    __tablename__ = "cfb_games"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    week: Mapped[int] = mapped_column(Integer, index=True)
    kickoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    home_team: Mapped[str] = mapped_column(String(100), index=True)
    away_team: Mapped[str] = mapped_column(String(100), index=True)
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), index=True)


class CfbMarketTotal(Base):
    __tablename__ = "cfb_market_totals"
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("cfb_games.id"), index=True)
    bookmaker: Mapped[str] = mapped_column(String(64))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    total: Mapped[float] = mapped_column(Float)


class CfbTotalPrediction(Base):
    __tablename__ = "cfb_total_predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("cfb_games.id"), unique=True, index=True)
    model_version: Mapped[str] = mapped_column(String(80))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    market_total: Mapped[float] = mapped_column(Float)
    projected_total: Mapped[float] = mapped_column(Float)
    edge: Mapped[float] = mapped_column(Float)
    recommendation: Mapped[str] = mapped_column(String(8))


class CfbTotalResult(Base):
    __tablename__ = "cfb_total_results"
    prediction_id: Mapped[int] = mapped_column(ForeignKey("cfb_total_predictions.id"), primary_key=True)
    result: Mapped[str] = mapped_column(String(8))
    actual_total: Mapped[float] = mapped_column(Float)
    graded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
