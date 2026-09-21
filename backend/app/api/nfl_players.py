from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.player_stats import NflPlayerSeasonStat

router = APIRouter(prefix="/nfl-players", tags=["nfl players"])


@router.get("")
def search_players(query: str = Query(min_length=2), db: Session = Depends(get_db)):
    rows = db.scalars(select(NflPlayerSeasonStat).where(NflPlayerSeasonStat.player_name.ilike(f"%{query}%")).order_by(NflPlayerSeasonStat.player_name).limit(20)).all()
    return [{"player_id": row.player_id, "player_name": row.player_name, "team": row.team, "season": row.season, "passing_yards": row.passing_yards, "rushing_yards": row.rushing_yards, "receiving_yards": row.receiving_yards, "passing_touchdowns": row.passing_touchdowns, "rushing_touchdowns": row.rushing_touchdowns, "receiving_touchdowns": row.receiving_touchdowns, "total_touchdowns": row.rushing_touchdowns + row.receiving_touchdowns} for row in rows]
