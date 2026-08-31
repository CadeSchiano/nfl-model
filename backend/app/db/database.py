"""SQLAlchemy setup for the V0.1 SQLite development database."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


def _database_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{Path(__file__).resolve().parents[3] / 'data' / 'nfl_model.db'}",
    )


def make_engine(url: str):
    options = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    return create_engine(url, **options)


engine = make_engine(_database_url())
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """Base class for all V0.1 database tables."""


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def initialize_database() -> None:
    """Create the V0.1 tables when they do not yet exist."""
    from app.models import game, mlb, odds, prediction  # noqa: F401

    Base.metadata.create_all(bind=engine)
    columns = {column["name"] for column in inspect(engine).get_columns("predictions")}
    if "odds_id" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE predictions ADD COLUMN odds_id INTEGER"))
    game_columns = {column["name"] for column in inspect(engine).get_columns("games")}
    with engine.begin() as connection:
        if "home_rest" not in game_columns:
            connection.execute(text("ALTER TABLE games ADD COLUMN home_rest INTEGER"))
        if "away_rest" not in game_columns:
            connection.execute(text("ALTER TABLE games ADD COLUMN away_rest INTEGER"))
        if "division_game" not in game_columns:
            connection.execute(text("ALTER TABLE games ADD COLUMN division_game BOOLEAN DEFAULT 0"))
    mlb_game_columns = {column["name"] for column in inspect(engine).get_columns("mlb_games")}
    mlb_prediction_columns = {column["name"] for column in inspect(engine).get_columns("mlb_hr_predictions")}
    with engine.begin() as connection:
        if "probable_home_pitcher" not in mlb_game_columns:
            connection.execute(text("ALTER TABLE mlb_games ADD COLUMN probable_home_pitcher VARCHAR(120)"))
        if "probable_away_pitcher" not in mlb_game_columns:
            connection.execute(text("ALTER TABLE mlb_games ADD COLUMN probable_away_pitcher VARCHAR(120)"))
        if "player_name" not in mlb_prediction_columns:
            connection.execute(text("ALTER TABLE mlb_hr_predictions ADD COLUMN player_name VARCHAR(120)"))
        if "team" not in mlb_prediction_columns:
            connection.execute(text("ALTER TABLE mlb_hr_predictions ADD COLUMN team VARCHAR(80)"))
