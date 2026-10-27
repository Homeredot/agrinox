# Data directory

This directory contains small, reviewable source-data extracts and audit files used by Agrinox.

- `nisr-audit/` contains NISR Seasonal Agricultural Survey tables used to audit curated district and yield records.

- `disease_dataset.zip.part*` contains the complete plant disease training archive in numbered Git LFS parts.
- Runtime-ready aggregate records are stored in `backend/app/data/` with their source and methodology documented in the application.
- Rwanda administrative locations are stored in `rwanda-locations/locations.json` under that dataset's included MIT license.

After cloning, run `python scripts/restore_disease_dataset.py` to join and extract the LFS parts into `disease_dataset/`. Alternatively, install `requirements-data.txt` and run `python scripts/download_disease_dataset.py` to download and extract the source dataset from Kaggle. The expanded directory remains ignored so the images are not duplicated in ordinary Git history.

No API keys, farmer records, SQLite databases, uploaded photographs, or private sensor observations belong in this directory or in Git.
