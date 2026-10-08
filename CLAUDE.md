# Working in this repo

Monorepo: `pipeline/` (Python 3.13, uv) produces static data; `apps/web/` (Vite 8, React 19,
MapLibre 6, deck.gl 9.4) renders it; `packages/schema/` is the contract between them.

## Commands
- Demo data (no keys needed): `pnpm fixtures` → `data/build/` (SYNTHETIC; never deploy)
- Web dev: `pnpm dev` (serves `data/build` at `/data`), `pnpm typecheck`, `pnpm test`, `pnpm build`
- Pipeline: `cd pipeline && uv run pytest -q && uv run ruff check . ../scripts`
- Contract: edit `pipeline/milmap/models.py` → `pnpm schema:gen` → commit schema + generated.ts

## Invariants (tests guard most of these)
- Day index: 2022-02-24 = 0, identical in `timeutil.py` and `packages/schema/src/time.ts`.
- ISW day = America/New_York date; Telegram day = Europe/Kyiv date.
- Front lines are oriented controller-on-LEFT; secondary limits are clipped off the front.
- Never merge sources' polygons; primary/compare only.
- Never hand-edit `packages/schema/src/generated.ts`.
- Extraction schema stays all-required (structured-output grammar limits).
- Raw fetches go to `data/raw/` before parsing; be polite (≤1 req/s, contact UA).
- UI shows ≤25-word excerpts + links, never full source text.
- MapLibre: keep `optimizeDeps.exclude` + explicit `setWorkerUrl`; use `@deck.gl/maplibre`.

## Docs
`docs/ARCHITECTURE.md` (system + contract), `docs/CARTOGRAPHY.md` (visual spec),
`docs/DATA_SOURCES.md`, `docs/LICENSING.md`, `docs/DECISIONS.md`, `PROMPT.md` (build plan).
