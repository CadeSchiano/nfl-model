"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import games, odds, performance, predictions
from app.db.database import initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="NFL Quantitative Game Model", version="0.1.0", lifespan=lifespan)


app.include_router(games.router)
app.include_router(predictions.router)
app.include_router(performance.router)
app.include_router(odds.router)


@app.get("/health")
def health() -> dict[str, str]:
    """Return a simple liveness response."""
    return {"status": "healthy"}
