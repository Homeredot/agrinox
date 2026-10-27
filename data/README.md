# Data directory

This directory contains small, reviewable source-data extracts and audit files used by Agrinox.

- `nisr-audit/` contains NISR Seasonal Agricultural Survey tables used to audit curated district and yield records.
- Runtime-ready aggregate records are stored in `backend/app/data/` with their source and methodology documented in the application.
- Rwanda administrative locations are stored in `rwanda-locations/locations.json` under that dataset's included MIT license.

The PlantVillage image dataset is intentionally excluded from Git because it is a large third-party training dataset. Download it from its original source and place it in `PlantVillage/` only when retraining Plant Lens. Trained binary exports are also excluded; their metadata files and training script remain reviewable.

No API keys, farmer records, SQLite databases, uploaded photographs, or private sensor observations belong in this directory or in Git.
