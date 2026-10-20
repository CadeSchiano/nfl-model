"""Isolated NBA schedule, lineup, prediction, and grading records."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class NbaGame(Base):
    __tablename__ = "nba_games"
    id: Mapped[str] = mapped_column(String(24), primary_key=True)  # ESPN event ID
    season: Mapped[int] = mapped_column(Integer, index=True)
    game_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    home_team: Mapped[str] = mapped_column(String(8), index=True)
    away_team: Mapped[str] = mapped_column(String(8), index=True)
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), index=True)


class NbaPlayerGame(Base):
    __tablename__ = "nba_player_games"
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("nba_games.id"), index=True)
    player_id: Mapped[str] = mapped_column(String(24), index=True)
    player_name: Mapped[str] = mapped_column(String(120), index=True)
    team: Mapped[str] = mapped_column(String(8), index=True)
    starter: Mapped[bool] = mapped_column(Boolean, default=False)
    minutes: Mapped[float] = mapped_column(Float, default=0)
    points: Mapped[float] = mapped_column(Float, default=0)
    rebounds: Mapped[float] = mapped_column(Float, default=0)
    assists: Mapped[float] = mapped_column(Float, default=0)
    three_pointers_made: Mapped[float] = mapped_column(Float, default=0)
    __table_args__ = (UniqueConstraint("game_id", "player_id", name="uq_nba_player_game"),)


class NbaGamePrediction(Base):
    __tablename__ = "nba_game_predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("nba_games.id"), unique=True, index=True)
    model_version: Mapped[str] = mapped_column(String(80))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    home_win_probability: Mapped[float] = mapped_column(Float)
    away_win_probability: Mapped[float] = mapped_column(Float)
    predicted_home_margin: Mapped[float] = mapped_column(Float)
    result: Mapped[str | None] = mapped_column(String(8), nullable=True)
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NbaStartingLineup(Base):
    __tablename__ = "nba_starting_lineups"
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("nba_games.id"), index=True)
    player_id: Mapped[str] = mapped_column(String(24), index=True)
    player_name: Mapped[str] = mapped_column(String(120))
    team: Mapped[str] = mapped_column(String(8))
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    __table_args__ = (UniqueConstraint("game_id", "player_id", name="uq_nba_starting_lineup"),)


class NbaPlayerPrediction(Base):
    __tablename__ = "nba_player_predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("nba_games.id"), index=True)
    player_id: Mapped[str] = mapped_column(String(24), index=True)
    player_name: Mapped[str] = mapped_column(String(120))
    team: Mapped[str] = mapped_column(String(8))
    model_version: Mapped[str] = mapped_column(String(80))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    projected_points: Mapped[float] = mapped_column(Float)
    projected_rebounds: Mapped[float] = mapped_column(Float)
    projected_assists: Mapped[float] = mapped_column(Float)
    projected_threes: Mapped[float] = mapped_column(Float)
    __table_args__ = (UniqueConstraint("game_id", "player_id", name="uq_nba_player_prediction"),)


class NbaPlayerPredictionResult(Base):
    __tablename__ = "nba_player_prediction_results"
    prediction_id: Mapped[int] = mapped_column(ForeignKey("nba_player_predictions.id"), primary_key=True)
    actual_points: Mapped[float] = mapped_column(Float)
    actual_rebounds: Mapped[float] = mapped_column(Float)
    actual_assists: Mapped[float] = mapped_column(Float)
    actual_threes: Mapped[float] = mapped_column(Float)
    graded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
