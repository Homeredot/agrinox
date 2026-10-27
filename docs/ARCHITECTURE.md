# Agrinox architecture

## Module 0 boundary

Module 0 establishes identity, farm ownership, location capture, and field geometry. These records become the shared foundation for weather, soil, irrigation, crop planning, satellite and finance modules.

```text
Next.js browser
  -> typed REST client
  -> FastAPI /api/v1
  -> services (auth, farms, geocoding)
  -> SQLAlchemy
  -> SQLite agrinox.db (WAL + foreign keys)

OpenStreetMap tiles are rendered by Leaflet.
Nominatim reverse geocoding is called only through FastAPI and cached in SQLite.
```

## Module 0 schema

- `users`: identity, password hash, preferred language, UTC timestamps.
- `farms`: user-owned farm profile and hierarchical location labels.
- `provinces`, `districts`, `sectors`, `cells`, `villages`: normalized Rwanda hierarchy imported from the supplied MIT-licensed dataset; stable codes are retained and parent-child foreign keys prevent invalid combinations.
- `farm_fields`: named field, optional crop note, four normalized side lengths, estimated or map-derived area, and GeoJSON polygon.
- `geocode_cache`: cached provider payload keyed by rounded coordinates.
- `audit_logs`: security-relevant actions with UTC timestamps.

Ownership filters are applied in API queries; a user cannot retrieve or mutate another user's farm or field by changing an ID.

## Future modules

The proposed full schema in the concept is intentionally introduced by module-specific migrations, not as unused tables. This keeps constraints reviewable and avoids pretending that later modules exist.

