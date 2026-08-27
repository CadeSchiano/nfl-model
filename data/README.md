# Data

Raw and processed NFL datasets are generated locally and ignored by Git. Use
`python scripts/import_history.py` from `backend/` to reproduce the Phase 1
historical game dataset.

`python scripts/generate_features.py` downloads nflverse play-by-play data one
season at a time and creates the Phase 3 pregame feature table locally.
