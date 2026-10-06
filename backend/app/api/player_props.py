"""Read-only current-week NFL yardage projection endpoint."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.nfl_player_props_service import current_week_player_props

router = APIRouter(prefix="/player-props", tags=["player props"])


@router.get("/current-week")
def current_week(db: Session = Depends(get_db)):
    return current_week_player_props(db)

