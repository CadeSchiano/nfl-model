"""Generate reproducible historical pregame Elo predictions and metrics."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.elo_service import evaluate_elo_predictions, generate_elo_predictions  # noqa: E402


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Generate historical pregame Elo predictions.")
    parser.add_argument("--input", type=Path, default=project_root / "data" / "processed" / "games_2015_2025.csv")
    parser.add_argument("--output", type=Path, default=project_root / "data" / "processed" / "elo_predictions_2015_2025.csv")
    args = parser.parse_args()

    predictions = generate_elo_predictions(pd.read_csv(args.input, parse_dates=["date"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(args.output, index=False)
    metrics = evaluate_elo_predictions(predictions)
    print(f"Generated {len(predictions)} Elo predictions at {args.output}")
    print("Elo evaluation: " + ", ".join(f"{key}={value}" for key, value in metrics.items()))


if __name__ == "__main__":
    main()
