// MapLibre overlay layers — the ISW-style "rich front" stack (see docs/CARTOGRAPHY.md).
//
// Bottom -> top:  area fills -> change (diff) -> secondary limit lines -> ghost fronts
//                 -> comparison front -> front casing -> front -> teeth
// All inserted beneath the basemap's first label layer.
//
// Source switching uses MapLibre global state (`["global-state", "primary"]`), so
// changing ISW <-> DeepState is a state flip, not a layer rebuild. In temporal
// PMTiles mode the same specs add a `vf <= day < vt` filter on `["global-state","day"]`.
import type {
  ExpressionSpecification,
  FilterSpecification,
  LayerSpecification,
} from "maplibre-gl";
import { C } from "./palette";
import { PATTERN } from "./patterns";

export const SRC = {
  areas: "mm-areas",
  lines: "mm-lines",
  diff: "mm-diff",
  ghosts: "mm-ghosts",
} as const;

const primary: ExpressionSpecification = ["global-state", "primary"];
const compare: ExpressionSpecification = ["global-state", "compare"];
const isPrimary: ExpressionSpecification = ["==", ["get", "source"], primary];
const cat = (c: string): ExpressionSpecification => ["==", ["get", "category"], c];
const kind = (k: string): ExpressionSpecification => ["==", ["get", "kind"], k];

/** Logical layer groups the UI toggles; each maps to one or more style layer ids. */
export const GROUPS = {
  pre2022: ["a-pre2022"],
  control: ["a-control"],
  advance: ["a-advance", "l-advance"],
  infiltration: ["a-infiltration", "l-infiltration"],
  claimed: ["a-claimed", "l-claimed"],
  uaCounter: ["a-ua-counter"],
  diff: ["diff-gain", "diff-loss", "diff-gain-line", "diff-loss-line"],
  ghosts: ["ghost"],
  compare: ["compare-front"],
  front: ["front-casing", "front", "front-teeth"],
} as const;
export type GroupKey = keyof typeof GROUPS;

const widthByZoom = (lo: number, hi: number): ExpressionSpecification => [
  "interpolate", ["exponential", 1.4], ["zoom"], 5, lo, 12, hi,
];

export function overlayLayers(opts: { temporal?: boolean } = {}): LayerSpecification[] {
  const t = (f: ExpressionSpecification): FilterSpecification =>
    (opts.temporal
      ? ["all", f, ["<=", ["get", "vf"], ["global-state", "day"]], ["<", ["global-state", "day"], ["get", "vt"]]]
      : f) as FilterSpecification;
  const all = (...e: ExpressionSpecification[]): ExpressionSpecification => ["all", ...e];
  // Temporal pieces are grid-clipped: antialiasing would draw the cell seams.
  const aa = !opts.temporal;

  return [
    { id: "a-pre2022", type: "fill", source: SRC.areas, filter: t(all(isPrimary, cat("pre_2022"))),
      paint: { "fill-color": C.ruDeep, "fill-opacity": 0.55, "fill-antialias": aa } },
    { id: "a-control", type: "fill", source: SRC.areas, filter: t(all(isPrimary, cat("assessed_control"))),
      paint: { "fill-color": C.ru, "fill-opacity": 0.3, "fill-antialias": aa } },
    { id: "a-advance", type: "fill", source: SRC.areas, filter: t(all(isPrimary, cat("assessed_advance"))),
      paint: { "fill-pattern": PATTERN.advance, "fill-opacity": 0.9, "fill-antialias": aa } },
    { id: "a-infiltration", type: "fill", source: SRC.areas,
      filter: t(all(isPrimary, cat("assessed_infiltration"))),
      paint: { "fill-pattern": PATTERN.infiltration, "fill-opacity": 0.95, "fill-antialias": aa } },
    { id: "a-claimed", type: "fill", source: SRC.areas, filter: t(all(isPrimary, cat("claimed_control"))),
      paint: { "fill-pattern": PATTERN.claimed, "fill-opacity": 0.8, "fill-antialias": aa } },
    { id: "a-ua-counter", type: "fill", source: SRC.areas,
      filter: t(all(isPrimary, cat("claimed_ua_counter"))),
      paint: { "fill-pattern": PATTERN.uaCounter, "fill-opacity": 0.9, "fill-antialias": aa } },

    // Day-over-day change. Opacity is pulsed by MilMap on each day change.
    { id: "diff-gain", type: "fill", source: SRC.diff, filter: all(isPrimary, ["==", ["get", "change"], "ru_gain"]),
      paint: { "fill-color": C.ru, "fill-opacity": 0.6 } },
    { id: "diff-loss", type: "fill", source: SRC.diff, filter: all(isPrimary, ["==", ["get", "change"], "ua_gain"]),
      paint: { "fill-color": C.ua, "fill-opacity": 0.6 } },
    { id: "diff-gain-line", type: "line", source: SRC.diff,
      filter: all(isPrimary, ["==", ["get", "change"], "ru_gain"]),
      paint: { "line-color": "#ffd0cc", "line-width": 1 } },
    { id: "diff-loss-line", type: "line", source: SRC.diff,
      filter: all(isPrimary, ["==", ["get", "change"], "ua_gain"]),
      paint: { "line-color": "#cfe0ff", "line-width": 1 } },

    // Secondary limits — drawn only where they diverge from the front (pipeline clips them).
    { id: "l-claimed", type: "line", source: SRC.lines, filter: t(all(isPrimary, kind("claimed_limit"))),
      layout: { "line-cap": "butt", "line-join": "round" },
      paint: { "line-color": C.claim, "line-width": widthByZoom(1, 2.2), "line-dasharray": [3, 2] } },
    { id: "l-advance", type: "line", source: SRC.lines, filter: t(all(isPrimary, kind("advance_limit"))),
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": C.ruAdvance, "line-width": widthByZoom(0.8, 1.8) } },
    { id: "l-infiltration", type: "line", source: SRC.lines,
      filter: t(all(isPrimary, kind("infiltration_limit"))),
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": C.ruInfiltration, "line-width": widthByZoom(1.2, 2.4), "line-dasharray": [0.1, 2] } },

    // Ghost fronts: where the line was 1 / 7 / 30 days ago ("tree rings").
    { id: "ghost", type: "line", source: SRC.ghosts,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": C.ghost,
        "line-width": widthByZoom(0.8, 1.6),
        "line-dasharray": [2, 2],
        "line-opacity": ["interpolate", ["linear"], ["get", "age"], 1, 0.75, 7, 0.45, 30, 0.2],
      } },

    // A second source's front for comparison (e.g. DeepState vs ISW).
    { id: "compare-front", type: "line", source: SRC.lines,
      filter: t(all(["==", ["get", "source"], compare], kind("front"))),
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": C.compare, "line-width": widthByZoom(1, 2.2), "line-dasharray": [4, 2] } },

    { id: "front-casing", type: "line", source: SRC.lines, filter: t(all(isPrimary, kind("front"))),
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": C.casing, "line-width": widthByZoom(4, 7), "line-opacity": 0.85 } },
    { id: "front", type: "line", source: SRC.lines, filter: t(all(isPrimary, kind("front"))),
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": C.ru, "line-width": widthByZoom(1.6, 3.4) } },
    { id: "front-teeth", type: "symbol", source: SRC.lines, minzoom: 8,
      filter: t(all(isPrimary, kind("front"))),
      layout: {
        "symbol-placement": "line",
        "symbol-spacing": 28,
        "icon-image": PATTERN.tooth,
        "icon-rotation-alignment": "map",
        "icon-allow-overlap": true,
        "icon-ignore-placement": true,
        "icon-offset": [0, -5], // left of travel direction = controller side
        "icon-size": ["interpolate", ["linear"], ["zoom"], 8, 0.7, 12, 1.1],
      } },
  ];
}
