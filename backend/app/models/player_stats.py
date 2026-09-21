from __future__ import annotations

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class NflPlayerSeasonStat(Base):
    __tablename__ = "nfl_player_season_stats"
    player_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_name: Mapped[str] = mapped_column(String(120), index=True)
    team: Mapped[str] = mapped_column(String(8))
    passing_yards: Mapped[float] = mapped_column(Float, default=0)
    rushing_yards: Mapped[float] = mapped_column(Float, default=0)
    receiving_yards: Mapped[float] = mapped_column(Float, default=0)
    passing_touchdowns: Mapped[int] = mapped_column(Integer, default=0)
    rushing_touchdowns: Mapped[int] = mapped_column(Integer, default=0)
    receiving_touchdowns: Mapped[int] = mapped_column(Integer, default=0)
