"""Build Phase 3 historical pregame features from nflverse data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.features import build_pregame_features  # noqa: E402
from app.services.nfl_data import DEFAULT_SEASONS, download_team_game_stats  # noqa: E402


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Generate leakage-safe historical NFL features.")
    parser.add_argument("--input", type=Path, default=project_root / "data" / "processed" / "games_2015_2025.csv")
    parser.add_argument("--output", type=Path, default=project_root / "data" / "processed" / "pregame_features_2015_2025.csv")
    args = parser.parse_args()

    games = pd.read_csv(args.input, parse_dates=["date"])
    features = build_pregame_features(games, download_team_game_stats(DEFAULT_SEASONS))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(args.output, index=False)
    print(f"Generated {len(features)} pregame feature rows at {args.output}")


if __name__ == "__main__":
    main()
