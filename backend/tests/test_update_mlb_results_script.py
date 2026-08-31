import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "update_mlb_results.py"
SPEC = importlib.util.spec_from_file_location("update_mlb_results_script", SCRIPT_PATH)
script = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(script)


def test_backfill_dates_are_parsed() -> None:
    args = script.parse_args(["--start", "2026-03-26", "--end", "2026-08-30"])
    assert args.start.isoformat() == "2026-03-26"
    assert args.end.isoformat() == "2026-08-30"


def test_backfill_range_must_be_complete_and_chronological() -> None:
    with pytest.raises(SystemExit):
        script.parse_args(["--start", "2026-03-26"])
    with pytest.raises(SystemExit):
        script.parse_args(["--start", "2026-08-30", "--end", "2026-03-26"])
