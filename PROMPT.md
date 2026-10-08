# One-shot build prompt — Milmap (Mildata → Milmap)

> Paste everything below the line into a coding agent (Claude Code recommended) opened at the
> root of this repository. It is written to be executed end-to-end without follow-up questions.

---

You are a principal engineer and cartographer building **Milmap**: a web application that turns
heterogeneous Russia–Ukraine war reporting ("mildata": ISW control-of-terrain layers and daily
assessments, DeepState maps, milblogger and official Telegram channels, RSS) into a **day-by-day,
multi-source, provenance-preserving interactive map** ("milmap"). Work autonomously through the
milestones below, verifying each against its acceptance criteria before moving on.

## 0. Ground truth: read before writing code

This repo is a **working scaffold**, not a blank slate. Read in this order: `CLAUDE.md`,
`docs/ARCHITECTURE.md`, `docs/CARTOGRAPHY.md`, `docs/DATA_SOURCES.md`, `docs/LICENSING.md`,
`docs/DECISIONS.md`. Then run:

```bash
pnpm install && (cd pipeline && uv sync)
pnpm fixtures            # synthetic demo data -> data/build (manifest.synthetic = true)
(cd pipeline && uv run pytest -q) && pnpm typecheck && pnpm test && pnpm build
pnpm dev                 # http://localhost:5173
```

Everything above passes today. What already works (do not rebuild; extend):

- **Contract**: Pydantic models (`pipeline/milmap/models.py`) → JSON Schema → TS types
  (`packages/schema`). `Manifest` + per-day `DayBundle` files.
- **Geometry**: front derivation (boundary − borders/coast, controller-on-left orientation),
  day-over-day diff with sliver removal, grid-clipped temporal interval encoding — all tested.
- **Sources (code, not yet run against live data)**: ISW ArcGIS discovery/classification/paged
  query, ISW report HTML parser, DeepState mirror, Telegram (Telethon) fetcher.
- **Extraction**: all-required Pydantic schema, prompt, `messages.parse` call, Batch request
  builder, gazetteer with transliteration normaliser + front-distance prior, fusion/corroboration.
- **Web**: MapLibre 6 + deck.gl 9.4 interleaved; ISW-style fills with runtime hatch/stipple
  patterns; front with casing + teeth; secondary limit lines; ghost fronts (D-1/7/30);
  comparison-source front; diff pulse; observation markers/leaders/callouts; day slider with
  gain/loss histogram, playback that never outruns the network, keyboard control; URL state;
  synthetic-data banner. Verified rendering in a production build.

Library versions are newer than most training data (MapLibre GL JS **6.13**, ESM-only,
WebGL2-only; deck.gl **9.4**; Vite **8**; TypeScript **7**; anthropic **1.12**; selectolax **1.0**).
**When unsure about an API, read the installed type definitions in `node_modules`/`.venv`
instead of guessing.** Known traps are listed in `docs/ARCHITECTURE.md § Known integration
gotchas` — keep those fixes intact.

## 1. Product requirements (acceptance-level)

1. **Time sliding by day.** A slider spanning the full data range (target: 2022-02-24 → today)
   with a diverging histogram (km² RU gain up / UA gain down) and claim markers. Drag, click,
   ←/→ (±1), Shift+←/→ (±7), Home/End, Space play at 1/2/4/8 days/s. Scrubbing a cached day
   updates the map in **≤ 50 ms**; playback at 8 d/s has no visible stalls on a mid-range laptop.
   Optional **compare mode**: pick two days, show the diff between them (not just vs. yesterday).
2. **Rich map.** Dark ops-room basemap (Protomaps extract in production; OpenFreeMap fallback in
   dev; offline background fallback), hillshade, English labels with ISW transliterations,
   oblast boundaries, scale, compact attribution. Works at 380 px wide (panels collapse to drawers).
3. **Textual data overlaid around the front.** Each extracted observation appears as a
   status-coded marker with a callout and a leader to the nearest point on that day's front.
   Implement the **v2 "front gutter" layout** from `docs/CARTOGRAPHY.md` (1-D packed callouts in
   RU-side and UA-side lanes along the front) and curved **axis labels** ("Pokrovsk direction").
   A side feed lists the day's reports grouped by axis; hover/selection is linked both ways;
   a detail drawer shows summary, status, Admiralty grade, corroboration, conflicts, ≤25-word
   excerpt and links to every citation.
4. **Rich, ISW-like multi-line fronts.** Exactly the encoding table in `docs/CARTOGRAPHY.md`:
   assessed control, pre-2022 occupation, assessed advances (hatch), infiltration (stipple),
   claimed control (amber hatch + dashed limit), claimed UA counteroffensives, front with teeth,
   secondary limits only where they diverge, ghost fronts, comparison front, diff pulse.
5. **Multiple sources.** ISW map + text, DeepState map, Telegram channels, RSS. Primary/compare
   source selection for areas; observations from all sources with per-source toggles and status
   filters. Claims are never promoted to control; disagreement is shown, not resolved.

## 2. Non-negotiable invariants

- Day index epoch 2022-02-24 = 0 everywhere. ISW day = ET calendar date of the assessment;
  Telegram day = Kyiv date. Tests already pin this — keep them green.
- The **model never produces coordinates**. Places are resolved by the gazetteer; unresolved
  observations are kept (listed in the feed) but not drawn.
- Never merge polygons from different sources. Never tween polygons between days.
- Raw responses are saved under `data/raw/` before parsing; HTTP ≤ 1 req/s per host with a
  contact User-Agent; respect robots/ToS; no auth-walled or private sources.
- Copyright: UI shows our paraphrase + ≤ 25-word excerpt + link; never full report text.
  Do not vectorise ISW's static PNG maps. Follow `docs/LICENSING.md`; anything public-facing is
  gated on the permissions noted there.
- Contract changes go through `models.py` → `pnpm schema:gen`; never hand-edit `generated.ts`.
- Keep `manifest.synthetic` honest; the banner must show for fixtures and never for real data.

## 3. Milestones (do them in order; each ends green: tests, typecheck, build)

### M1 — Real ISW map history into the warehouse
- Implement `milmap ingest isw-map --from --to` → `control_snapshot` (DuckDB, WKB, area_km2),
  `milmap fronts` → `front_line`, and `milmap export --out data/build [--temporal]` that builds
  from the warehouse (reuse `export.build`; add a DB→`BuildInput` loader).
- Load reference geography: Natural Earth **Ukraine point-of-view** admin-0 (includes Crimea) as
  the front mask; HDX COD-AB oblasts as a basemap overlay layer.
- Run `milmap isw-discover`; extend `config/isw_layer_map.yaml` until no Ukraine timelapse layer
  from 2025–2026 is unclassified. Backfill at least **2026-01-01 → latest available**.
- Acceptance: per-day ISW `assessed_control` area within 2 % of the sum of the layer's `Area_KM`
  (where present); a golden test pins front geometry for one real day (Hausdorff < 50 m after
  re-run); exported bundles ≤ 600 KB gzipped/day (simplify per zoom if not).

### M2 — DeepState + comparison
- `milmap ingest deepstate`; `deepstate.*` layers in bundles; manifest lists both sources.
- Add a per-day "disagreement" stat (km² in symmetric difference ISW vs DeepState) to `DayStat`
  and an optional slider track for it.
- Acceptance: primary/compare switch is a global-state flip (no layer rebuild), verified by a
  test that layer count is unchanged after switching.

### M3 — ISW text → observations
- `milmap ingest isw-text`, `milmap extract` (online + `--batch` using the Message Batches API;
  poll, then ingest results), extraction cache keyed by sha1(model, prompt version, text).
- Gazetteer build step: download GeoNames `UA.zip` (+ `RU.zip` filtered to Kursk, Belgorod,
  Bryansk, Voronezh, Rostov), build index; `relation` + `distance_km` offsets; `front_anchor` =
  nearest point on that day's front; `axis` from section heading.
- Fusion with `in_assessed_control` wired to the day's ISW polygon.
- Create `pipeline/tests/eval/` with **3 hand-labelled ISW report sections** (store only the
  minimal text needed, ≤ fair-use excerpts, plus labels). Eval script reports precision/recall on
  (place, kind, status). Acceptance: precision ≥ 0.85, recall ≥ 0.75; ≥ 90 % of labelled places
  resolved within 3 km. Log tokens and $ per report day.
- Default model `claude-sonnet-5-5` (env `MILMAP_EXTRACT_MODEL`); compare against
  `claude-haiku-5-5` on the eval and record the cost/quality trade-off in `docs/DECISIONS.md`.

### M4 — Telegram + RSS
- `milmap ingest telegram` (cursor per channel, text only, ≥ 40 chars), RSS adapter
  (feedparser) for ISW/CTP and one news source. Translation happens inside extraction.
- Tests use **recorded fixtures** (no live credentials in CI). Add a source-management view in the
  layer panel: per-source toggle, reliability badge, side.
- Acceptance: a recorded RU milblogger claim of a settlement seizure outside the assessed
  polygon renders as an amber dashed marker with "≠ assessed" and links to the post.

### M5 — Web: the experience
- Front-gutter callouts + curved axis labels (CARTOGRAPHY v2). Re-enable deck.gl
  `CollisionFilterExtension` (`VITE_LABEL_COLLISION=1`) only after verifying it on a real GPU;
  otherwise implement collision in the gutter packer.
- Compare-two-days mode; observation detail drawer; selection in URL; oblast overlay;
  mobile drawers; `prefers-reduced-motion`; i18n-ready strings (EN first).
- Code-split deck.gl and the feed so first paint ships ≤ 450 KB gzipped JS.
- Playwright: e2e on fixtures (deep link, scrub, play, select, source switch) + visual snapshots
  of 3 canonical views (run Chromium with `--use-angle=swiftshader --enable-unsafe-swiftshader`).

### M6 — Scale + ship
- Temporal PMTiles spike (ARCHITECTURE § Scale path): tippecanoe the `temporal/*.geojsonl`,
  render with `vf ≤ global-state day < vt`, measure scrub FPS vs bundles on the 2022→today range.
  Adopt if ≥ 2× better at equal visual fidelity; record the result in `docs/DECISIONS.md`.
- Backfill 2022-02-24 → today (Batch API for text).
- `milmap daily` + `.github/workflows/daily.yml`: last 3 days reprocessed each run; publish
  changed bundles, then the manifest last. Data on Cloudflare R2 (range requests, long cache on
  `days/*`, `no-cache` on manifest); web on Vercel (preview deployment until LICENSING gates clear).

## 4. Performance & quality budgets

| Metric | Budget |
|---|---|
| First meaningful map (manifest + 1 bundle, 4G-ish) | ≤ 2.5 s |
| Cached-day scrub → pixels | ≤ 50 ms |
| Day bundle | ≤ 600 KB gzipped |
| Initial JS | ≤ 450 KB gzipped (deck/feed lazy) |
| Pipeline daily run | ≤ 15 min, ≤ $2 LLM spend on a normal day |
| Python | ruff clean, pytest green; geometry functions have unit tests |
| TS | strict, `noUncheckedIndexedAccess`, no `any` in app code |

## 5. Inputs from the human (and what to do without them)

`ANTHROPIC_API_KEY`, `TELEGRAM_API_ID/HASH` + a session, a vetted Telegram channel list,
R2/Vercel credentials, ISW permission status. **If any is missing, do not block:** build and test
the stage against recorded fixtures, mark the live step `TODO(human): …` in
`docs/DECISIONS.md`, and continue to the next milestone.

## 6. How to work

- Keep a running `docs/PROGRESS.md`: milestone, what changed, acceptance evidence (test names,
  numbers, screenshots in `docs/img/`), open issues.
- Prefer small, verified steps: write the test, implement, run, look at the map.
- When a library behaves differently than expected, check its installed source/types, fix,
  and add the finding to `docs/ARCHITECTURE.md § Known integration gotchas`.
- Stop and ask only for decisions that are irreversible or legally sensitive (publishing data
  publicly, adding a new source with unclear terms). Everything else: decide, document in
  `docs/DECISIONS.md`, proceed.

## 7. Definition of done

`pnpm build` and `uv run pytest` green in CI; `milmap daily` produces a real (non-synthetic)
build covering 2022-02-24 → today; the web app on that build meets every requirement in §1 and
budget in §4; Playwright suite green; docs updated; licensing gates documented with their status.
