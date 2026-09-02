"""Build local 2019–2025 NFL player touchdown history from nflverse PBP."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.nfl_td_data import download_td_player_games  # noqa: E402
if __name__ == "__main__":
    output = Path(__file__).resolve().parents[2] / "data" / "processed" / "nfl_td_player_games_2019_2025.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    data = download_td_player_games(range(2019, 2026))
    data.to_parquet(output, index=False)
    print(f"Saved {len(data)} player-game observations to {output}")
