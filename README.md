# Milmap — Mildata → Milmap

Day-by-day, multi-source, provenance-preserving map of the Russia–Ukraine war: ISW
control-of-terrain + daily assessments, DeepState, Telegram milblogs/officials and RSS, fused
into ISW-style fronts with textual reports anchored to the line.

```bash
pnpm install && (cd pipeline && uv sync)
pnpm fixtures   # SYNTHETIC demo data (no keys, no network to sources)
pnpm dev        # http://localhost:5173
```

| Path | What |
|---|---|
| `pipeline/` | Python: sources → DuckDB → extraction (Claude) → geometry → static export |
| `packages/schema/` | The contract: JSON Schema generated from Pydantic + TS types + day-index helpers |
| `apps/web/` | Vite + React + MapLibre GL 6 + deck.gl 9.4 |
| `docs/` | Architecture, cartography spec, sources, licensing, decisions |
| `PROMPT.md` | The one-shot development prompt that takes this scaffold to done |

Start with `CLAUDE.md` and `docs/ARCHITECTURE.md`. Read `docs/LICENSING.md` before deploying anything.
