"""Manual expected-starting-QB selections for player-prop context."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class NflExpectedQbStarter(Base):
    __tablename__ = "nfl_expected_qb_starters"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), index=True)
    team: Mapped[str] = mapped_column(String(8))
    player_id: Mapped[str] = mapped_column(String(32), index=True)
    player_name: Mapped[str] = mapped_column(String(120))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    __table_args__ = (UniqueConstraint("game_id", "team", name="uq_expected_qb_starter_game_team"),)
