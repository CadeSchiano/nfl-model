from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.main import app
from app.models.game import Game, Team


def test_game_endpoint_serializes_a_persisted_game() -> None:
    """Exercise FastAPI routing and its SQLAlchemy dependency without live data."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add_all([
        Team(abbreviation="BUF", name="Buffalo Bills"),
        Team(abbreviation="NYJ", name="New York Jets"),
        Game(
            id="test-game",
            season=2026,
            week=1,
            date=datetime(2026, 9, 10, 20, 20, tzinfo=timezone.utc),
            home_team="BUF",
            away_team="NYJ",
            status="scheduled",
        ),
    ])
    session.commit()

    TestSession = sessionmaker(bind=engine)

    def override_db():
        with TestSession() as test_session:
            yield test_session

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/games/test-game")
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()

    assert response.status_code == 200
    assert response.json()["home_team"] == "BUF"
    assert response.json()["away_team"] == "NYJ"


def test_game_endpoint_returns_a_useful_404_for_an_unknown_game() -> None:
    response = TestClient(app).get("/games/not-a-real-game")

    assert response.status_code == 404
    assert response.json() == {"detail": "game not found"}
