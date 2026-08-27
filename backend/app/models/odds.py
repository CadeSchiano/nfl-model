from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Odds(Base):
    __tablename__ = "odds"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), index=True)
    bookmaker: Mapped[str] = mapped_column(String(64))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    home_moneyline: Mapped[int] = mapped_column(Integer)
    away_moneyline: Mapped[int] = mapped_column(Integer)
    spread: Mapped[float] = mapped_column(Float)
    home_spread_odds: Mapped[int] = mapped_column(Integer)
    away_spread_odds: Mapped[int] = mapped_column(Integer)
