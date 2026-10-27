# Agrinox

This repository contains **Module 0 — My Farm / Yield Management**, **Module 1 — Weather Intelligence**, **Module 2 — Soil Quality & Advisory**, **Module 3 — Rwanda Agricultural Knowledge Base**, **Module 9 — Smart Farming Calendar**, **Module 10 — Farm Profit & Expense Calculator**, and the platform's other connected intelligence modules. My Farm opens on a portfolio dashboard, while field details appear only inside a specific farm workspace. Weather Intelligence automatically uses registered farm locations and provides current, hourly, daily and seven-day Open-Meteo forecasts plus twelve completed months of historical reanalysis. Soil Quality combines compatible field-device readings with manual or laboratory measurements, makes missing and unreliable evidence visible, and produces prioritized advice with evidence and uncertainty. It never turns uncalibrated low-cost NPK readings into a precise fertilizer prescription. The bilingual knowledge base searches reviewed, source-linked records and offers a retrieval-grounded agricultural assistant with saved conversations. The Smart Farming Calendar stores field-specific work in SQLite, supports recurring tasks and in-app reminders, and turns transparent Rwanda-focused planning guidance into editable tasks. Farm Finance stores RWF budgets separately from actual expenses and sales, and can reuse supported field and harvest estimates from Crop Planning without inventing selling prices. Device Management discovers compatible monitoring devices over USB, assigns each device to a field (never directly to a farm), supports later assignment changes or unassignment, inventories its sensors, and stores timestamped readings on a separate device-detail screen.

After sign-in, the system Dashboard provides a bilingual command center built from the farmer's real records. It summarizes farms, fields, mapped land, devices, calendar attention, crop plans and financial estimates, reports partial-data failures honestly, and links directly to each working module. My Farm remains a separate focused portfolio and field-management workspace.

## Structure

```text
agrinox/
├── README.md           Project overview, setup and verification guide
├── app.py              Reviewer-friendly FastAPI entry point
├── requirements.txt    Root Python dependency entry point
├── backend/            FastAPI API, SQLAlchemy models, tests and Alembic
├── frontend/           Next.js App Router user interface
├── data/               Reviewable source-data extracts and audit notes
├── demo/               Demonstration recording instructions/location
├── firmware/           ESP32 NPK and irrigation firmware
├── rwanda-locations/   Province-to-village administrative dataset
├── docs/               Architecture, protocol and progress documentation
├── database/           Database design and operational notes
├── iot/                Additional hardware examples
├── ml/                 Machine-learning workspace
└── scripts/            Data import utilities
```

Large third-party training images, trained model binaries, runtime databases,
uploads, logs, build output and credentials are excluded from Git. This keeps
the repository suitable for review while preserving reproducible training and
setup instructions.

## Run locally

Requirements: Python 3.11+ and Node.js 20+.

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt
Push-Location backend
..\.venv\Scripts\python -m alembic upgrade head
..\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

In another terminal:

```powershell
Push-Location frontend
npm install
npm run dev
```

Open http://localhost:3000. API documentation is at http://localhost:8000/docs.

For reviewers who prefer a root-level backend command, `app.py` launches the
same FastAPI application:

```powershell
.\.venv\Scripts\python app.py
```

## English and Kinyarwanda

- The language can be changed from the sign-in screen or main navigation without logging out. The choice is kept on the device.
- Shared, feature-grouped dictionaries in `frontend/lib/i18n.ts` cover navigation, forms, validation/API errors, weather, soil and irrigation advice, notifications, dashboard labels and help text. New or dynamically loaded interface text is translated by the shared provider.
- Translation dictionaries ship inside the frontend build; switching language does not download another bundle and works well on slower connections.
- Specialized agricultural terms are isolated in `agriculturalGlossary` with an explicit `human_review_required` status. A qualified Kinyarwanda language reviewer or Rwandan agronomist must approve those terms before they are marked reviewed.
- Mobile controls use readable input text, 44-pixel tap targets, reduced motion support and reduced-data styling for affordable smartphones.

## Data and map behavior

- Farm and field records are persisted in `backend/agrinox.db`.
- SQLite foreign keys and WAL mode are enabled on every connection.
- A drawn polygon is the preferred area source. Manual four-side area is explicitly an estimate, calculated as average opposing side A/C multiplied by average opposing side B/D.
- Reverse geocoding is proxied through the backend to OpenStreetMap Nominatim and cached. Users must review returned administrative labels because OpenStreetMap coverage varies.
- Map text search is restricted to Rwanda, proxied through the authenticated backend, and cached in SQLite.
- Administrative locations come from the MIT-licensed `rwanda-locations/locations.json` dataset and are stored in normalized SQLite tables. Farm creation requires a valid Province → District → Sector → Cell → Village code chain.
- Selecting a Cell automatically focuses the map. When OpenStreetMap has the cell boundary it is drawn directly; otherwise the map clearly shows the nearest available sector or district boundary as a navigation reference. The user must still click the map to save the farm's exact coordinates.
- Weather responses are cached in `weather_cache` for 30 minutes. Registered farms use saved coordinates automatically; farms without an exact point use their cell/sector map reference. Manual weather coordinates are restricted to Rwanda.
- USB discovery uses PySerial on the computer running the backend. Device Management can flash the bundled, verified NPK firmware directly from the dashboard using `esptool`; farmers enter only the Wi-Fi name and password, and Agrinox creates the device identity, security key, and display name automatically. The API must listen on `0.0.0.0:8000` so the ESP32 can submit readings over the local network. Unknown ports and sensors are never fabricated. See `docs/ESP32_PROTOCOL.md`.
- Soil readings are field-scoped and persisted with their source, unit, calibration status, reliability, timestamp and optional note. Soil advice uses the crop profile, available measurements and cached Weather Intelligence evidence; insufficient evidence triggers laboratory or agronomist review rather than a guessed prescription.
- Knowledge articles store English and Kinyarwanda content, review metadata, and source references. Assistant retrieval and conversations are stored in SQLite. Set `GEMINI_API_KEY` only in the backend environment to enable Gemini-grounded responses and Google Search grounding; without a key, the assistant safely uses verified retrieval and states when its records are insufficient. `GEMINI_MODEL` defaults to `gemini-3.8-flash`; transient failures retry and then use `GEMINI_FALLBACK_MODEL` (`gemini-3.6-flash`).
- Crop Planning & Yield reuses each saved farm's province/district and each field's recorded area, crop note, soil context, and latest soil readings. Numerical outlooks use curated NISR Seasonal Agricultural Survey observations from `backend/app/data/nisr_yield_observations.json`. The baseline reports an observed yield range, total-harvest range, time-ordered MAE/RMSE, geographic coverage, uncertainty, model version, sources, and limitations. Regression ML remains disabled until at least 20 compatible independent observations are available for honest held-out comparison.
- Smart Farming Calendar tasks belong to fields and support due dates, completion, editing, recurring rollover, reminders, and source-linked crop-stage suggestions. A saved Crop Planning record can create its calendar schedule with one click; generated tasks retain their crop-plan link and duplicate schedules are prevented. Suggestions are planning estimates based on the farmer's planting date, not prescriptions; the interface tells the farmer to confirm timing against current weather and local agronomic advice. In-app reminders require no extra configuration.
- Central email notifications use the `EMAIL_*` environment settings and an audited delivery history. Farmers control calendar, irrigation, device, soil, Plant Lens, planning, finance and security categories from the bell in the application header. Calendar emails are checked automatically, while action emails are event-driven and idempotent. Email failure never reverses a completed farm action. Gmail accounts must use a revocable app password rather than the normal account password.
- Farm Profit & Expense Calculator performs server-side RWF calculations from farmer-entered prices and itemized costs. It reports revenue, profit, break-even price, cost per kilogram, margin, profit per hectare, and ±10%/±20% price scenarios. Saved budgets and actual transactions use separate records. When a supported Crop Planning result is selected, only its field area and harvest range are reused; no market price is supplied or inferred.

Refresh the location hierarchy after applying migrations:

```powershell
.\.venv\Scripts\python scripts\import_rwanda_locations.py --replace
```
- No agricultural yield, weather, sensor, or NISR statistics are fabricated or seeded.

## Tests

```powershell
.\.venv\Scripts\python -m pytest backend\tests -q
Push-Location frontend
npm run typecheck
npm run build
```

