"""Isolated MLB tables; they do not share NFL prediction records."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class MlbGame(Base):
    __tablename__ = "mlb_games"
    id: Mapped[int] = mapped_column(primary_key=True)  # MLB gamePk
    game_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    official_date: Mapped[date] = mapped_column(Date, index=True)
    home_team: Mapped[str] = mapped_column(String(80))
    away_team: Mapped[str] = mapped_column(String(80))
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    probable_home_pitcher: Mapped[str | None] = mapped_column(String(120), nullable=True)
    probable_away_pitcher: Mapped[str | None] = mapped_column(String(120), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MlbPlayerGame(Base):
    __tablename__ = "mlb_player_games"
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("mlb_games.id"), index=True)
    player_id: Mapped[int] = mapped_column(Integer, index=True)
    player_name: Mapped[str] = mapped_column(String(120))
    team: Mapped[str] = mapped_column(String(80))
    appeared: Mapped[bool] = mapped_column(Boolean)
    home_runs: Mapped[int] = mapped_column(Integer, default=0)
    plate_appearances: Mapped[int | None] = mapped_column(Integer, nullable=True)
    at_bats: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    walks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strikeouts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    innings_pitched: Mapped[str | None] = mapped_column(String(12), nullable=True)
    home_runs_allowed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    __table_args__ = (UniqueConstraint("game_id", "player_id", name="uq_mlb_player_game"),)


class MlbBatterFeature(Base):
    """Pregame batter features built only from earlier completed games."""
    __tablename__ = "mlb_batter_features"
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("mlb_games.id"), index=True)
    player_id: Mapped[int] = mapped_column(Integer, index=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    prior_games: Mapped[int] = mapped_column(Integer)
    prior_plate_appearances: Mapped[int] = mapped_column(Integer)
    prior_home_runs: Mapped[int] = mapped_column(Integer)
    hr_per_plate_appearance: Mapped[float] = mapped_column(Float)
    __table_args__ = (UniqueConstraint("game_id", "player_id", name="uq_mlb_batter_feature"),)


class MlbModelVersion(Base):
    __tablename__ = "mlb_model_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(80), unique=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    training_data_through: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    artifact_path: Mapped[str] = mapped_column(String(255))


class MlbHrPrediction(Base):
    __tablename__ = "mlb_hr_predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("mlb_games.id"), index=True)
    player_id: Mapped[int] = mapped_column(Integer, index=True)
    player_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    team: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model_version: Mapped[str] = mapped_column(String(80))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    first_pitch: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    probability: Mapped[float] = mapped_column(Float)
    result: Mapped[str | None] = mapped_column(String(8), nullable=True)  # HIT/MISS
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
