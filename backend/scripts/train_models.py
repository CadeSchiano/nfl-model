"""Train and evaluate the Phase 4 chronological NFL models."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.train import train_and_evaluate  # noqa: E402


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Train fixed-split V0.1 NFL models.")
    parser.add_argument("--input", type=Path, default=project_root / "data" / "processed" / "pregame_features_2015_2025.csv")
    parser.add_argument("--models", type=Path, default=project_root / "backend" / "app" / "ml" / "models")
    args = parser.parse_args()

    report = train_and_evaluate(pd.read_csv(args.input), args.models)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
