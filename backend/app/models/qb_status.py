"""Manual, timestamped quarterback availability overrides for current previews."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class NflQbStatus(Base):
    __tablename__ = "nfl_qb_statuses"
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), index=True)
    team: Mapped[str] = mapped_column(String(8))
    player_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(16))
    adjustment_points: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    __table_args__ = (UniqueConstraint("game_id", "team", name="uq_nfl_qb_status_game_team"),)
