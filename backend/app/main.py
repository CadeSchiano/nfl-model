"""FastAPI application entry point."""

from fastapi import FastAPI


app = FastAPI(title="NFL Quantitative Game Model", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Return a simple liveness response."""
    return {"status": "healthy"}
