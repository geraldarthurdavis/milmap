# AGENTS.md — milmap

Milmap turns war reporting ("mildata": ISW map layers and daily assessments, DeepState,
Telegram, RSS) into a day-by-day, multi-source map. `pipeline/` (Python) writes static files;
`apps/web/` (React + MapLibre + deck.gl) renders them; `packages/schema/` is the contract.
Deeper context: `docs/ARCHITECTURE.md`, `docs/CARTOGRAPHY.md`, `docs/DATA_SOURCES.md`,
`docs/LICENSING.md`, `docs/DECISIONS.md`. Build plan and milestones: `PROMPT.md`.

## Prerequisites

Node ≥ 22 with pnpm 10 (`corepack enable`), Python 3.13 via uv. Optional: tippecanoe (temporal
tiles, M6), Playwright Chromium (screenshots). No API keys are needed for local UI work.

## First run

```bash
pnpm install
(cd pipeline && uv sync)
cp .env.example .env              # optional; empty is fine for fixtures
pnpm fixtures                     # SYNTHETIC demo data -> data/build (~30 s)
pnpm dev                          # http://localhost:5173  (serves data/build at /data)
```

Expect a "SYNTHETIC DEMO DATA" banner. A deep link to try:
`http://localhost:5173/#d=2026-09-01&m=9.2/48.45/37.45&p=isw&c=deepstate`

## Commands

| Task | Command (from repo root unless noted) |
|---|---|
| Web dev server / prod preview | `pnpm dev` / `pnpm build && pnpm --filter @milmap/web preview` |
| Typecheck, unit tests, build (all JS) | `pnpm typecheck`, `pnpm test`, `pnpm build` |
| Python tests / lint / format | `cd pipeline && uv run pytest -q`, `uv run ruff check . ../scripts`, `uv run ruff format .` |
| Regenerate the contract | `pnpm schema:gen` (Pydantic → JSON Schema → `packages/schema/src/generated.ts`) |
| Demo data | `pnpm fixtures` |
| Headless screenshot | `pnpm --filter @milmap/web shot "<url>" /abs/path/out.png [waitMs]` (exits 1 on page errors) |
| ISW layer discovery (network) | `cd pipeline && uv run milmap isw-discover` |

Pipeline CLI status: `schema` and `isw-discover` are implemented. `ingest`, `extract`, `fuse`,
`export`, `tiles`, `daily` are planned (PROMPT.md M1–M6); the library code they wrap exists in
`pipeline/milmap/` and is unit-tested. Don't document a command until it runs.

## Repo map

```
pipeline/milmap/
  models.py            contract (single source of truth for exported JSON)
  timeutil.py          day index + per-source day assignment
  paths.py             repo-anchored paths, loads repo-root .env
  sources/             adapters: isw_arcgis, isw_reports, deepstate, telegram (+ base.py contract)
  extract/             LLM schema/prompt/call, gazetteer (place → coordinates)
  geo/                 frontline, diff, temporal (grid interval encoding)
  fuse.py, export.py, db.py (DuckDB), cli.py (typer)
pipeline/config/       isw_layer_map.yaml, sources.yaml, telegram_channels.yaml
packages/schema/       schema/*.json (generated), src/generated.ts (generated), src/time.ts
apps/web/src/
  map/                 milmap.ts (imperative map controller), layers.ts (style layers),
                       patterns.ts, palette.ts, observations.ts (deck.gl), basemap.ts
  data/                BundleCache + hooks;  state/ zustand store + URL hash sync
  ui/                  MapView, TimeSlider, LayerPanel, FeedPanel, usePlayback
scripts/make_fixtures.py   synthetic data generator
data/fixtures/         committed reference geometry (Natural Earth, Ukraine POV)
```

## Local data and state (all under repo-root `data/`, gitignored except `fixtures/`)

| Path | What | Reset |
|---|---|---|
| `data/build/` | static output the web app reads | `rm -rf data/build && pnpm fixtures` |
| `data/raw/<source>/` | every fetched response, saved before parsing | delete a source dir to force refetch |
| `data/milmap.duckdb` | warehouse | delete it; stages are idempotent |
| `data/milmap.session` | Telegram session — a credential, never commit or share | |

Paths resolve from the repo root regardless of where you run commands (`milmap/paths.py`).

## Environment

One `.env` at the repo root serves both sides: the pipeline loads it via `milmap/paths.py`
(real env vars win), Vite loads it via `envDir`. Only `VITE_*` vars reach the browser — never
prefix a secret with `VITE_`.

| Var | Used by | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | extraction | not needed for fixtures or UI work |
| `MILMAP_EXTRACT_MODEL` | extraction | default `claude-sonnet-5-5` |
| `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION` | Telegram adapter | user session, public channels only |
| `MILMAP_CONTACT` | all HTTP | goes in the User-Agent; set it before any live fetch |
| `MILMAP_DB`, `MILMAP_RAW_DIR` | pipeline | override warehouse / raw cache location |
| `VITE_DATA_BASE_URL` | web | default `/data` |
| `VITE_PMTILES_URL`, `VITE_BASEMAP_FLAVOR` | web | self-hosted Protomaps basemap; unset → OpenFreeMap, then an offline background |
| `VITE_LABEL_COLLISION` | web | `1` enables deck.gl label collision (unverified, see gotchas) |

## Recipes

**Change the contract.** Edit `pipeline/milmap/models.py` → `pnpm schema:gen` → fix TS errors
→ `pnpm fixtures` → commit models, `schema/*.json` and `generated.ts` together. CI fails if
generated files are stale. Never hand-edit generated files.

**Add a source.** New module in `pipeline/milmap/sources/` implementing `ControlSource` and/or
`DocumentSource` (`sources/base.py`); `save_raw()` before parsing; register it in
`config/sources.yaml` with an Admiralty reliability grade and a licence note; add parser tests
on a small recorded fixture (no live network in tests). Read `docs/LICENSING.md` first.

**Add a map category or line kind.** Enum in `models.py` → produce it in `export.py` → style
layer in `apps/web/src/map/layers.ts` + group in `GROUPS` → legend row in `ui/LayerPanel.tsx`
→ follow the encoding table in `docs/CARTOGRAPHY.md`. The test in `apps/web/src/data/source.test.ts` checks
every group references a real layer.

**Change extraction.** Prompt in `extract/prompts.py`, schema in `extract/schema.py`. Bump
`PROMPT_VERSION` in `extract/llm.py` (it keys the cache). Keep every schema field required.

**Check visually.** Run `pnpm dev`, then `pnpm --filter @milmap/web shot` on a deep link, and
look at the image. Do this after any change under `apps/web/src/map/`; typecheck can't see a
missing front line.

**Live fetches.** Polite by default: ≤ 1 req/s per host, `MILMAP_CONTACT` set, prefer replaying
`data/raw/` over refetching. Use small day ranges while developing.

## Invariants — don't break these

- Day index: 2022-02-24 = 0 in both `timeutil.py` and `packages/schema/src/time.ts`.
  ISW day = America/New_York date; Telegram day = Europe/Kyiv date; DeepState = file date.
- Front lines are oriented with the controlling side on the LEFT (map teeth rely on it).
  Secondary limit lines are clipped where they coincide with the front.
- Never merge polygons from different sources; the UI compares primary vs. compare.
- Never tween polygons between days.
- The LLM never produces coordinates; the gazetteer does. Unresolved places stay off the map.
- The UI shows our paraphrase + ≤ 25-word excerpt + link — never full source text.
- `manifest.synthetic` is true for fixtures and false for real data; never deploy fixtures.
- Per-day map updates are `setData` / `setGlobalStateProperty`, never a style rebuild.

## Known gotchas (verified)

- MapLibre 6 is ESM-only and locates its worker via `import.meta.url`. Keep
  `optimizeDeps.exclude: ["maplibre-gl"]`, `worker.format: "es"` and the explicit
  `setWorkerUrl(...?worker&url)` in `map/milmap.ts`, or you get "Worker failed to load".
- Use `@deck.gl/maplibre` (`MapLibreOverlay`). `@deck.gl/mapbox` crashes on MapLibre 6
  (`map.transform` undefined).
- deck.gl `CollisionFilterExtension` drew no labels under headless SwiftShader; it's behind
  `VITE_LABEL_COLLISION=1` until checked on a real GPU.
- `selectolax` ≥ 1.0: import from `selectolax.lexbor`.
- Structured outputs count optional/nullable fields toward grammar limits — sentinels, not `None`.
- Natural Earth's default Ukraine polygon excludes Crimea; use `data/fixtures/ukraine_adm0.geojson`.
- Library versions are newer than most training data. Read installed types in `node_modules`
  or `.venv` instead of guessing; add new findings here.
- `pkill -f vite` from a shell whose command line contains "vite" kills that shell too.

## Code style

- TypeScript strict with `noUncheckedIndexedAccess`; no `any` in app code. React holds state;
  `MilMap` owns GL objects. Colours only from `map/palette.ts`.
- Python: ruff (line length 110), type hints, pure functions in `geo/` with unit tests.
- Comments explain why, not what. Keep modules small; follow the existing file layout.

## Before you finish

1. `cd pipeline && uv run ruff check . ../scripts && uv run pytest -q`
2. `pnpm typecheck && pnpm test && pnpm build`
3. If the contract changed: `pnpm schema:gen` and commit the generated files.
4. If map code changed: a screenshot from `pnpm --filter @milmap/web shot` looks right.
5. Update `docs/` when behaviour, a decision or a gotcha changed.

Don't commit `data/build`, `data/raw`, `.env`, `*.session` or DuckDB files.

## Ask the human first

Publishing data or deploying anything public (see `docs/LICENSING.md`), adding a source with
unclear terms, changing Telegram channel grades, or anything that spends real money beyond a
small eval (LLM backfills, paid tiles).
