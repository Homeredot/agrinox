<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/readme-banner-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="docs/readme-banner-light.svg">
  <img alt="A Rwanda-inspired Imigongo line pattern" src="docs/readme-banner-light.svg" width="100%">
</picture>

<h1 align="center">Agrinox</h1>
<p align="center"><strong>Connected farm management and decision support built for Rwanda.</strong></p>
<p align="center">English + Kinyarwanda · Mobile friendly · Field-level records · Explainable advice</p>

## What Agrinox does

Agrinox brings farm records, monitoring, planning and practical guidance into one bilingual workspace. Farmers register farms and fields once, then reuse that information across weather, soil, irrigation, crop planning, finance and calendar tools.

### Key features

- **Farm and field management** — searchable Rwanda locations, mapped boundaries, water sources and reusable field profiles.
- **Weather and irrigation** — farm-based forecasts, soil-moisture and tank evidence, safety checks, pump commands and audit logs.
- **Devices and soil** — ESP32 discovery and flashing, field assignment, online status, sensor history and evidence-based soil advice.
- **Planning and finance** — transparent yield ranges from supported NISR data, linked calendar tasks, RWF budgets, expenses and profit scenarios.
- **Plant health** — live camera or gallery input, conservative potato and tomato screening, uncertainty reporting and sourced next-step guidance.
- **Knowledge and monitoring** — bilingual verified articles, retrieval-assisted answers, district statistics and field-level satellite integration status.
- **Farmer experience** — responsive mobile navigation, four visual themes, profiles, notifications, email reminders and optional two-step verification.

## Run locally

Requirements: Python 3.11+, Node.js 20+ and Git LFS.

```powershell
git lfs install
git lfs pull
Copy-Item .env.example .env

python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt
Push-Location backend
..\.venv\Scripts\python -m alembic upgrade head
..\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

In another terminal:

```powershell
Set-Location frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

## Disease dataset

The complete training archive is stored as `data/disease_dataset.zip.part*` using Git LFS. Restore it after cloning:

```powershell
.\.venv\Scripts\python scripts\restore_disease_dataset.py
```

Or download the source automatically from Kaggle:

```powershell
.\.venv\Scripts\python -m pip install -r requirements-data.txt
.\.venv\Scripts\python scripts\download_disease_dataset.py
```

The downloader uses `emmarex/plantdisease`; Kaggle may require authentication or acceptance of its terms.

## Project layout

```text
backend/            FastAPI API, SQLite models, migrations and tests
frontend/           Next.js responsive web application
data/               Reviewable source data and Git LFS dataset archive
disease_dataset/    Local extracted training images (ignored by normal Git)
firmware/           ESP32 sensor and irrigation firmware
rwanda-locations/   Province-to-village administrative data
scripts/            Data download, restore and import utilities
```

## Verify

```powershell
.\.venv\Scripts\python -m pytest backend\tests -q
Push-Location frontend
npm run typecheck
npm run build
```

Agrinox identifies simulated or incomplete evidence, does not invent sensor or official statistics, and presents image screening as decision support—not a definitive diagnosis.
