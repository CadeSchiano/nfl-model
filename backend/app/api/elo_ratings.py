"""Current NFL Elo-rating endpoint."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.nfl_elo_ratings_service import current_elo_ratings

router = APIRouter(prefix="/elo-ratings", tags=["elo"])


@router.get("")
def list_elo_ratings(db: Session = Depends(get_db)):
    ratings = current_elo_ratings(db)
    return {"ratings": [{**rating, "rank": index + 1} for index, rating in enumerate(ratings)]}
