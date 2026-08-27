# NFL Quantitative Game Model

A web-based NFL pregame forecasting and market-analysis platform. Beta V0.1
forecasts regular-season moneyline win probability and expected point
differential, then compares those projections with sportsbook markets. It does
not promise betting outcomes or returns.

## Beta V0.1 scope

- NFL regular-season pregame moneyline and spread projections
- Historical prediction records, automatic grading, and performance tracking
- Sportsbook/model disagreement using no-vig moneyline probabilities

Player props, totals, live betting, accounts, payments, injury and weather
models, and other sports are intentionally outside this beta.

## Stack

- Python, FastAPI, pandas, NumPy, scikit-learn, SQLAlchemy, pytest
- SQLite for local development; PostgreSQL for beta deployment
- React/Vite only after the forecasting pipeline and APIs are working

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/health`; it returns `{"status":"healthy"}`.

Run the test suite from `backend/` with `pytest tests -q`.

## Current phase

Phase 6 provides SQLite development tables and public FastAPI routes for games,
predictions, odds, and performance. Prediction creation is locked after kickoff.
