"""Import the Phase 1 nflverse historical game dataset."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.nfl_data import (  # noqa: E402
    DEFAULT_SEASONS,
    build_historical_games,
    download_nflverse_games,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import validated nflverse regular-season games.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "data" / "processed" / "games_2015_2025.csv",
    )
    args = parser.parse_args()

    games, report = build_historical_games(download_nflverse_games(), DEFAULT_SEASONS)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    games.to_csv(args.output, index=False)
    print(f"Imported {len(games)} games to {args.output}")
    for warning in report.warnings:
        print(f"DATA QUALITY WARNING: {warning}")


if __name__ == "__main__":
    main()
