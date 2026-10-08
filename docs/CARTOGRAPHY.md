# Cartography spec — "rich fronts like ISW, but alive"

The map should read like an ISW static map at a glance and reward zooming like a GIS.
Colour encodes *who*; texture encodes *how sure*; line style encodes *which boundary*.

## Encoding rules

| Meaning | Encoding |
|---|---|
| Russian control (assessed) | solid red fill, 30% (`#e0352b`) |
| Occupied before 24 Feb 2022 | deep red fill, 55% (`#7f1610`) |
| Assessed Russian advances | red diagonal hatch (`pat-advance`) |
| Assessed infiltration areas | crimson stipple (`pat-infiltration`) — distinct from advances: presence, not control |
| Claimed Russian control | amber counter-hatch (`pat-claimed`) + dashed amber limit line |
| Claimed UA counteroffensives | blue hatch (`pat-ua-counter`) |
| Day-over-day change | red (RU gain) / blue (UA gain) fill that **pulses** 0.9→0.4 over 1.4 s on each day change |
| Front (assessed) | red line on a dark casing; teeth on the controller's side at z ≥ 8 |
| Advance / claimed / infiltration limits | thinner parallel lines, drawn **only where they diverge from the front** |
| Ghost fronts | dashed, fading: D-1 75%, D-7 45%, D-30 20% — "tree rings" of movement |
| Comparison source front | teal dashed (`#2ec4b6`) |
| Uncertainty (status) | solid = assessed/geolocated; hollow = reported; amber dashed ring = claimed; strikethrough = denied |

Never use colour alone for status (colour-blind safe): hatching, dashes and marker hollowness
carry it redundantly. Patterns are generated at runtime on canvas (`map/patterns.ts`) at 2× and
re-registered after any style swap.

## Layer stack (bottom → top)

basemap fills → hillshade → **area fills** → **diff** → **secondary limits** → **ghost fronts** →
**comparison front** → **front casing** → **front** → **teeth** → basemap labels → deck.gl
observations (leaders → markers → callouts).

All overlays insert before the basemap's first `symbol` layer so settlement names stay readable
over red fills. Place labels should use ISW's Ukrainian transliteration (basemap `name:en`
mostly matches; the gazetteer stores ISW-style canonical names for observations).

## Front derivation (pipeline)

`front = boundary(control ∪ pre_2022) − buffer(international border ∪ coastline, ~200 m)`, line-merged,
segments < 500 m dropped, oriented controller-on-left by majority vote of left-offset probes.
Rivers inside Ukraine (the Dnipro) stay fronts. Chaikin smoothing for z < 8 only.

## Text "around the front"

v1 (scaffold): each observation is a marker at its resolved place with a callout label and a
leader line to the **nearest point on that day's front** (`front_anchor`, computed in the
pipeline). Labels are prioritised by credibility + corroboration.

v2 (target): **front gutters.** Project every observation onto the front (`along`, `offset`
signed by side), sort by `along`, and lay callout boxes in two lanes parallel to the front —
RU-side lane for RU actions, UA-side lane for UA actions — with leader lines, like ISW's
annotated static maps. Lanes re-flow on zoom; collisions resolved by priority, then by
sliding along the lane (1-D packing), never by overlap. Axis headings (“Pokrovsk direction”)
are placed as curved line labels on the front segment nearest the axis' observations.

## Motion

* Scrubbing: no tweening of polygons (it lies about intermediate states). Swap instantly; the
  diff pulse shows what changed.
* Playback: 1/2/4/8 days per second; ghost lines make direction of travel obvious.
* Selecting an observation: fly to it (zoom ≥ 9.5), highlight leader + marker, list item scrolls.

## Accessibility

Slider is a real `role="slider"` with `aria-valuetext` = date; keyboard ←/→ (±1 day),
Shift (±7), Home/End, Space (play), Esc (clear selection). Respect `prefers-reduced-motion`
(disable pulse + flyTo animation).
