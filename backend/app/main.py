"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import elo_ratings, games, mlb, nfl_history, odds, performance, predictions, touchdowns
from app.db.database import initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="NFL Quantitative Game Model", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"], allow_methods=["GET"], allow_headers=["*"])


app.include_router(games.router)
app.include_router(nfl_history.router)
app.include_router(touchdowns.router)
app.include_router(elo_ratings.router)
app.include_router(predictions.router)
app.include_router(performance.router)
app.include_router(odds.router)
app.include_router(mlb.router)


@app.get("/health")
def health() -> dict[str, str]:
    """Return a simple liveness response."""
    return {"status": "healthy"}
