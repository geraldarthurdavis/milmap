# Decisions (ADR-lite) and open questions

## Decided

1. **MapLibre GL JS 6 + deck.gl 9.4 (`@deck.gl/maplibre`, interleaved).** MapLibre for vector
   basemap, fills, patterns, line symbology (teeth) and global-state filters; deck.gl for
   picking-heavy, data-driven observation layers and text with collision. Not Mapbox (licence,
   token), not Leaflet (no GPU patterns/global state at this scale), not CesiumJS (3D not needed v1).
2. **Static build, no API server.** Day bundles on object storage + CDN. Revisit when we need
   per-user features or live push.
3. **Python pipeline with DuckDB** (single file, SQL, spatial extension on demand) instead of
   PostGIS. Shapely 2 for geometry. Revisit at multi-writer or > ~50 GB.
4. **Claude structured outputs for extraction** (`messages.parse` + Pydantic), Batch API for
   backfills, cache by content hash. The model names places; the gazetteer places them.
5. **Admiralty grading** (reliability A–F × credibility 1–6) as the trust vocabulary.
6. **Primary + comparison source**, never merged polygons.
7. **Day index epoch 2022-02-24 = 0.** UI shows "Day N" (N = index + 1) next to the date.

## Open (workshop these)

* **ISW permission** for public redistribution — determines whether v1 is public.
* **"Today" for ISW**: timelapse services lag; acceptable lag vs. adding a PNG-only "latest" view?
* **Telegram channel list & grades** — who curates, how often reviewed.
* **Temporal PMTiles vs bundles** — run the scrub-FPS spike (ARCHITECTURE.md) before backfilling 2022–2026.
* **Hosting**: Vercel (app) + Cloudflare R2 (data, range requests) is the default assumption.
* **Languages**: English UI first; Ukrainian toggle (labels exist in OSM `name:uk`).
* **Front gutters (v2 text layout)** — custom 1-D packing vs. a label-placement library.
