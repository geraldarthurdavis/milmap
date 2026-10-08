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
8. **M1 ISW glue (`ingest isw-map` → warehouse → `export`).** `milmap ingest isw-map` upserts
   `IswArcgisSource.snapshots()` into `control_snapshot` (WKB + area_km2); `milmap export` loads it
   back via `db.load_control_areas` / `export.build_input_from_db` and calls the existing
   `export.build`. Fronts are derived in `build` from the control polygons (no separate `fronts`
   command / `front_line` table yet). The front mask is `data/fixtures/ukraine_adm0.geojson`
   (Natural Earth UA point-of-view, real geography) — the same file fixtures use; a dedicated
   Natural Earth download step is deferred. All pipeline I/O is anchored at repo-root `data/`
   regardless of CWD (`cli.REPO_ROOT`).

## Findings (2026-10-07, first real ISW run)

* **ISW ArcGIS lags ~6 months.** Latest monthly timelapse service is `Ukraine_Timelapse_April_2026`
  (control layer spans 2026-04-01..04-30); `Full_Length_view` stops at 2024-12-31. There is no
  May–Oct 2026 service yet. Verified a real week (2026-04-01..07): assessed control ≈ 112,996 km².
* **`make_valid` → GeometryCollection.** Real control unions carry stray lines/points after
  `make_valid`; shapely returns `None` for `.boundary` on a collection. `frontline._polygonal`
  now drops non-areal parts before the front derivation. (Synthetic fixtures never hit this.)
* **Bundle size over budget.** Real ISW polygons are dense: ~1.1 MB gzip/day vs. the ≤600 KB M1
  budget. Levers: coarser per-zoom simplify (`export.AREA_SIMPLIFY_DEG`) or the temporal-PMTiles
  path. Deferred — tune before any public backfill.
* **Layer-map gaps closed:** `INFIL_FEB_Merge` → infiltration (`infil_`), camelCase
  `...AssessedCoTinUkraine` / `Repair...CoT...` → control (`cot`). `CO_FEB_Merge` left unclassified
  (ambiguous vs. the sibling `CoT_FEB_Merge`); partisan layers stay `null` (future observations).
* **Overlapping services, same day.** `snapshots()` unions every classified layer across all
  services for a date; where coverage overlaps (e.g. a full-length + a monthly), a day's polygon
  can be contributed by more than one layer. Harmless when they agree; a "prefer most specific
  service per day" rule is a correctness follow-up.
* Real ISW data is **not committed** (licensing — see LICENSING.md). `TODO(human): ISW permission`
  before publishing derived layers. Deployed parity (manifest 404) needs the bundle published to a
  `VITE_DATA_BASE_URL` origin, which is gated on that permission.

## Open (workshop these)

* **ISW permission** for public redistribution — determines whether v1 is public.
* **"Today" for ISW**: timelapse services lag; acceptable lag vs. adding a PNG-only "latest" view?
* **Telegram channel list & grades** — who curates, how often reviewed.
* **Temporal PMTiles vs bundles** — run the scrub-FPS spike (ARCHITECTURE.md) before backfilling 2022–2026.
* **Hosting**: Vercel (app) + Cloudflare R2 (data, range requests) is the default assumption.
* **Languages**: English UI first; Ukrainian toggle (labels exist in OSM `name:uk`).
* **Front gutters (v2 text layout)** — custom 1-D packing vs. a label-placement library.
