# Licensing & use posture (not legal advice)

| Source | Status | Posture |
|---|---|---|
| ISW / AEI CTP map layers | © ISW & CTP; publicly viewable, no open licence found | Personal/research use. **Ask ISW before publicly redistributing derived layers** (tiles, GeoJSON). Attribute on every view. |
| ISW report text | © ISW | Extract facts; display our own paraphrase + ≤25-word excerpt + deep link. Never mirror report bodies. |
| DeepState | © DeepState; mirror repo GPL-3.0 | Check DeepState's terms before public use; attribute. |
| Telegram posts | © authors; Telegram API ToS | Store text for extraction; display paraphrase + link to the post. |
| GeoNames | CC BY 4.0 | Attribute. |
| Natural Earth | Public domain | — |
| OSM / Protomaps / OpenFreeMap | ODbL | "© OpenStreetMap contributors" visible. |
| AWS Terrain Tiles | Open data (various) | Attribute "Mapzen / AWS". |

Product rules that follow:

1. The attribution footer lists every source currently drawn.
2. Each observation shows its source and links out; excerpts are capped at 25 words.
3. Synthetic fixtures carry `manifest.synthetic = true`; the UI banners it. Never deploy fixtures.
4. A public deployment is gated on written permission from ISW for the map layers
   (or ship with DeepState + own-extracted layers only).
