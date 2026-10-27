# Progress checklist

## Complete

- [x] Monorepo foundation (Next.js + FastAPI + SQLite)
- [x] JWT registration, login and current-user endpoint
- [x] Owner-scoped farm and field APIs
- [x] Province/district/sector/cell/village capture
- [x] OpenStreetMap map picker with polygon drawing
- [x] Rwanda-only map place search with result selection and recentering
- [x] Complete Rwanda administrative hierarchy imported into normalized SQLite tables
- [x] Reusable searchable Province → District → Sector → Cell → Village picker
- [x] Automatic map focus after Cell selection, with cell boundary or administrative fallback
- [x] Backend validation of every submitted administrative code chain
- [x] Nominatim reverse geocoding with SQLite cache
- [x] Four-side dimensions with km/m/cm conversion
- [x] Server-side area validation and calculation
- [x] English/Kinyarwanda language switcher
- [x] Responsive dark productivity-dashboard interface with global field search
- [x] My Farm portfolio with statistics, map and farm list, separated from each farm's private field workspace
- [x] Module-based sidebar with My Farm, Weather Intelligence and Device Management
- [x] Alembic initial migration
- [x] Backend API tests and frontend type/build checks

- [x] Module 1 — Weather Intelligence with current, hourly, daily and seven-day forecasts
- [x] Twelve-month historical reanalysis summaries clearly separated from forecasts
- [x] Farm-aware weather locations, Rwanda hierarchy fallback and manual coordinates
- [x] SQLite weather response cache and evidence-based agricultural guidance
- [x] Monitoring-device USB discovery and Agrinox serial-protocol verification
- [x] Field-only device assignment with persistent device and sensor inventory
- [x] Live sensor reads with timestamped SQLite history and no simulated readings
- [x] Device overview with registration, statistics, assignment/unassignment, editing and deletion
- [x] Separate per-device sensor page with connection status, technical details, pin, unit and latest reading
- [x] Module 2 — Soil Quality dashboard with N, P, K, moisture, temperature and pH
- [x] Manual and laboratory soil entries with calibration, reliability, source and timestamp
- [x] Automatic field-device soil readings and per-measurement trends
- [x] Crop-stage and cached-weather-aware advisory with prominent evidence and uncertainty
- [x] No precise fertilizer prescriptions from uncalibrated low-cost nutrient readings

## Pending by request

- [ ] Remaining requested modules and NISR/ML phases

# Module 4 — Crop Planning and Yield Prediction

- Interactive field plan builder is available from the main sidebar without a module-specific navbar.
- Farm location, field area, crop note, soil context, and latest soil readings are reused from My Farm / Soil Quality.
- Plans persist in SQLite and retain their prediction evidence snapshot.
- Curated NISR SAS observations support transparent seasonal baselines with source links.
- Time-ordered expanding-window validation reports MAE and RMSE without future-data leakage.
- Random Forest and Gradient Boosting are listed as candidates but are not trained while compatible observations remain below the defensible threshold.
- District observations are used as anchors where curated; otherwise the UI labels the Rwanda-wide fallback.

