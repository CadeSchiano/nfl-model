"""Manual multi-week NFL player availability overrides."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class NflPlayerAvailability(Base):
    """An explicit user override that suppresses a player until reactivated."""

    __tablename__ = "nfl_player_availability"

    player_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    player_name: Mapped[str] = mapped_column(String(120))
    team: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(8), default="OUT", index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
