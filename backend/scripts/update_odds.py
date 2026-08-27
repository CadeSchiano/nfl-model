"""Fetch and append current NFL sportsbook odds snapshots."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.odds_service import append_odds_snapshots, fetch_current_odds, load_odds_api_key  # noqa: E402


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Append current NFL odds snapshots.")
    parser.add_argument("--output", type=Path, default=project_root / "data" / "processed" / "odds_snapshots.jsonl")
    args = parser.parse_args()

    snapshots, warnings, quota = fetch_current_odds(load_odds_api_key())
    append_odds_snapshots(snapshots, args.output)
    print(f"Appended {len(snapshots)} odds snapshots to {args.output}")
    warning_counts = Counter(warning.rsplit(": ", maxsplit=1)[-1] for warning in warnings)
    for reason, count in sorted(warning_counts.items()):
        print(f"ODDS DATA WARNING: {count} incomplete bookmaker observations ({reason})")
    if quota:
        print("API quota: " + ", ".join(f"{key}={value}" for key, value in quota.items()))


if __name__ == "__main__":
    main()
