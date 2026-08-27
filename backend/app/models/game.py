from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    abbreviation: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    conference: Mapped[str | None] = mapped_column(String(8), nullable=True)
    division: Mapped[str | None] = mapped_column(String(16), nullable=True)


class Game(Base):
    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    week: Mapped[int] = mapped_column(Integer, index=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    home_team: Mapped[str] = mapped_column(ForeignKey("teams.abbreviation"))
    away_team: Mapped[str] = mapped_column(ForeignKey("teams.abbreviation"))
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="scheduled", index=True)
