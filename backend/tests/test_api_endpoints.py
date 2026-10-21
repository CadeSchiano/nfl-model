from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.main import app
from app.models.game import Game, Team
from app.models.nba import NbaGame, NbaPlayerPrediction, NbaPlayerPredictionResult


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
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    def override_db():
        with TestSession() as test_session:
            yield test_session

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/games/not-a-real-game")
    finally:
        app.dependency_overrides.clear()
        engine.dispose()

    assert response.status_code == 404
    assert response.json() == {"detail": "game not found"}


def test_nba_prop_history_groups_and_returns_projection_results() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    game = NbaGame(
        id="nba-final",
        season=2026,
        game_date=datetime(2026, 10, 20, 23, tzinfo=timezone.utc),
        away_team="ATL",
        home_team="BOS",
        away_score=102,
        home_score=110,
        status="final",
    )
    prediction = NbaPlayerPrediction(
        game_id="nba-final",
        player_id="player-1",
        player_name="Example Starter",
        team="ATL",
        model_version="test",
        timestamp=datetime.now(timezone.utc),
        projected_points=18.5,
        projected_rebounds=6.2,
        projected_assists=4.1,
        projected_threes=2.3,
    )
    session.add_all([game, prediction])
    session.commit()
    session.add(
        NbaPlayerPredictionResult(
            prediction_id=prediction.id,
            actual_points=21,
            actual_rebounds=7,
            actual_assists=5,
            actual_threes=3,
            graded_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    TestSession = sessionmaker(bind=engine)

    def override_db():
        with TestSession() as test_session:
            yield test_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        summary = client.get("/nba/props/history")
        detail = client.get("/nba/props/history/nba-final")
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()

    assert summary.status_code == 200
    assert summary.json()[0]["prop_count"] == 1
    assert detail.status_code == 200
    assert detail.json()["players"][0]["actual_points"] == 21
