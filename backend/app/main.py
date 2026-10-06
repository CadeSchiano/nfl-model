"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import cfb, elo_ratings, first_touchdowns, games, mlb, nfl_history, nfl_players, odds, performance, player_props, predictions, qb_status, td_availability, touchdowns
from app.db.database import initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="NFL Quantitative Game Model", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"], allow_methods=["GET", "POST"], allow_headers=["*"])


app.include_router(games.router)
app.include_router(nfl_history.router)
app.include_router(touchdowns.router)
app.include_router(elo_ratings.router)
app.include_router(first_touchdowns.router)
app.include_router(nfl_players.router)
app.include_router(player_props.router)
app.include_router(cfb.router)
app.include_router(qb_status.router)
app.include_router(td_availability.router)
app.include_router(predictions.router)
app.include_router(performance.router)
app.include_router(odds.router)
app.include_router(mlb.router)


@app.get("/health")
def health() -> dict[str, str]:
    """Return a simple liveness response."""
    return {"status": "healthy"}
