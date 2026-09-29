# Local data and model artifacts

Raw/processed datasets, the SQLite database, odds snapshots, and serialized
model artifacts are generated locally and intentionally ignored by Git. They
can be large, change over time, or require an API key. They are not required
for running the automated test suite or building the frontend.

For the core NFL workflow, run these commands from the repository root after
activating the Python environment:

```bash
python backend/scripts/import_history.py
python backend/scripts/generate_features.py
python backend/scripts/train_models.py
```

The import and feature commands download public nflverse schedule/play-by-play
data. The training command writes model artifacts under
`backend/app/ml/models/` and keeps them local.

The MLB, NFL touchdown, and CFB scripts use their own local tables and model
artifacts. Live NFL/MLB/CFB market imports require `ODDS_API_KEY`; CFB schedule
imports also require `CFBD_API_KEY`. See the root README for the full local
development and operational commands.
