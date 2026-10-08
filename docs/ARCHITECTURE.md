# Milmap architecture

**Mildata → Milmap.** Many heterogeneous war sources in; one day-indexed, multi-source,
provenance-preserving map out.

```
 ┌──────────── SOURCES ────────────┐   ┌──────────── PIPELINE (Python, uv) ─────────────────────────┐   ┌──── STATIC BUILD ────┐   ┌──── WEB (Vite/React) ─────┐
 │ ISW ArcGIS FeatureServers (map) │──▶│ sources/*  fetch + normalise, raw cached in data/raw/     │   │ manifest.json        │   │ MapLibre GL 6 (basemap,   │
 │ ISW daily reports (text)        │──▶│ db.py      DuckDB warehouse (idempotent per day range)     │──▶│ days/YYYY-MM-DD.json │──▶│   areas, lines, patterns) │
 │ DeepState history (map)         │──▶│ extract/   Claude structured outputs → events; gazetteer   │   │ tiles/*.pmtiles      │   │ deck.gl 9.4 (observations,│
 │ Telegram channels (text)        │──▶│ geo/       fronts, diffs, temporal interval encoding       │   │  (temporal, v2)      │   │   callouts, leaders)      │
 │ RSS / news (text)               │──▶│ fuse.py    clustering, corroboration, conflicts            │   └──────────────────────┘   │ zustand + react-query     │
 └─────────────────────────────────┘   │ export.py  manifest + day bundles (+ temporal GeoJSONL)    │       R2/S3 + CDN           └───────────────────────────┘
                                       └────────────────────────────────────────────────────────────┘
```

## Principles

1. **Day is the primary key.** Everything is keyed by an integer *day index* (2022-02-24 = 0).
   Pipeline (`timeutil.py`) and web (`packages/schema/src/time.ts`) share the epoch.
   Day assignment is per-source and explicit: ISW → US Eastern date of the assessment;
   Telegram → Kyiv date of the post; DeepState → file date.
2. **Never merge opinions; compare them.** ISW and DeepState control areas are separate layers
   (`isw.assessed_control`, `deepstate.assessed_control`). The UI picks a *primary* source and
   can overlay a *comparison* front. Claims are never promoted to control.
3. **Provenance on every pixel.** Every observation carries source, Admiralty grade
   (source reliability A–F × information credibility 1–6), citations and a ≤25-word excerpt.
4. **Static-first.** The pipeline emits files; the web app is a static site. No API server in v1.
   Day bundles are immutable once a day is "closed" (cache forever; manifest is `no-cache`).
5. **Raw first, parse second.** Every fetched byte is stored under `data/raw/` before parsing,
   so parser fixes replay without refetching (and without hammering sources).

## Data contract (pipeline → web)

Source of truth: `pipeline/milmap/models.py` → `milmap schema` → JSON Schema →
`packages/schema/src/generated.ts`. Never hand-edit generated types.

* `manifest.json` — `Manifest`: day range, sources (with reliability + license note),
  layer descriptors (`id = "<source>.<category>"`, geom kind, day ranges), and one `DayStat`
  per day (km² gained/lost, observation & claim counts) which drives the slider histogram.
* `days/<date>.json` — `DayBundle`: `layers: {layerId: FeatureCollection}` plus
  `observations: Observation[]`. Area categories mirror ISW's legend
  (`assessed_control, pre_2022, assessed_advance, assessed_infiltration, claimed_control,
  claimed_ua_counter, ua_in_russia, contested`). Line kinds:
  `front, advance_limit, claimed_limit, infiltration_limit`. `<source>.diff` holds
  `ru_gain` / `ua_gain` polygons vs the previous day.
* Line geometry is **oriented with the controlling side on the left** (the web's "teeth"
  depend on it). Secondary limit lines are clipped where they coincide with the front.

### Scale path: temporal PMTiles

Per-day bundles cost one fetch per day. For instant scrubbing across 4+ years the pipeline also
writes `temporal/<layer>.geojsonl`: geometries clipped to a 0.25° grid, consecutive identical
pieces collapsed into `[vf, vt)` validity intervals (`geo/temporal.py`; ~90 days of pre-2022
area compress to the size of one day). Tile with tippecanoe into one PMTiles per layer:

```bash
tippecanoe -o tiles/isw.assessed_control.pmtiles -l areas -Z4 -z12 \
  --no-feature-limit --no-tile-size-limit --no-tiny-polygon-reduction \
  --detect-shared-borders temporal/isw.assessed_control.geojsonl
```

The client uses the same layer specs with `filter: vf <= ["global-state","day"] < vt` and
`fill-antialias: false` (grid seams). Spike before committing: measure scrub FPS for
`setGlobalStateProperty("day")` vs per-day `setData` on a mid-range laptop.

## Web runtime

* `MilMap` (imperative) owns MapLibre + the deck.gl `MapLibreOverlay` (interleaved). React owns
  state (zustand) and pushes deltas: `setBundle`, `setGhosts`, `setSources`, `setGroups`,
  `setObservations`. A day change is `GeoJSONSource.setData` + `setGlobalStateProperty`, never a
  style rebuild. Source switching (ISW ↔ DeepState) is a global-state flip.
* `BundleCache`: LRU (90 days), in-flight dedupe, directional prefetch (8 ahead / 3 behind).
  Playback only advances when the next day is cached — it never outruns the network.
* URL hash holds day, camera, primary/compare source → every view is a shareable link.

### Known integration gotchas (verified 2026-10-07)

* **MapLibre 6 is ESM-only and finds its worker via `import.meta.url`.** Vite pre-bundling and
  production bundling both break it ("Worker failed to load"). Fix in place:
  `optimizeDeps.exclude: ["maplibre-gl"]` + `setWorkerUrl(import "…/maplibre-gl-worker.mjs?worker&url")`
  + `worker.format: "es"`.
* **Use `@deck.gl/maplibre` (`MapLibreOverlay`), not `@deck.gl/mapbox`** — the mapbox adapter reads
  `map.transform`, which MapLibre 6 no longer exposes (crash in `getViewport`).
* `CollisionFilterExtension` rendered no labels under headless SwiftShader; gated behind
  `VITE_LABEL_COLLISION=1` until verified on a real GPU.
* `selectolax` ≥1.0 removed the Modest backend: use `selectolax.lexbor`.
* Structured outputs: optional/nullable fields count against grammar limits (≤24 optional,
  ≤16 unions per request). The extraction schema is all-required with sentinels.

## Pipeline stages

| Stage | Module | Idempotent key | Notes |
|---|---|---|---|
| ingest map | `sources/isw_arcgis.py`, `sources/deepstate.py` | (source, category, day) | ISW: discover timelapse services, classify layers by regex (`config/isw_layer_map.yaml`), page `f=geojson` |
| ingest text | `sources/isw_reports.py`, `sources/telegram.py`, RSS | document id | sections by direction heading; endnotes → URLs |
| extract | `extract/llm.py` | sha1(model, prompt version, text) | Sonnet 5.5 online; Batch API for backfill |
| geocode | `extract/gazetteer.py` | — | GeoNames + transliteration normaliser + front-distance prior |
| fuse | `fuse.py` | cluster id | ±1 day, same place, compatible kind |
| geometry | `geo/frontline.py`, `geo/diff.py` | (source, kind, day) | front = boundary − (borders ∪ coast) |
| export | `export.py` | file per day | bundles + manifest (+ temporal GeoJSONL) |

Daily schedule (GitHub Actions, `.github/workflows/daily.yml`): 03:30 and 06:30 UTC (ISW publishes
late evening ET; DeepState mirror updates ~03:00 UTC). Each run reprocesses the last 3 days
(sources revise), uploads changed bundles, then the manifest last (atomic-ish publish).
