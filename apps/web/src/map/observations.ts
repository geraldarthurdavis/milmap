// deck.gl layers for textual observations "around the front":
//   leader line (event point -> nearest point on that day's front),
//   status-coded marker, collision-aware text callout.
import { CollisionFilterExtension } from "@deck.gl/extensions";
import { LineLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import type { Layer, PickingInfo } from "@deck.gl/core";
import type { Observation } from "@milmap/schema";
import { C, rgba, type Rgba } from "./palette";

type Pos = [number, number];
const COLLISION = import.meta.env.VITE_LABEL_COLLISION === "1";
const pos = (o: Observation) => o.geometry!.coordinates as Pos;

function actorColor(o: Observation, a = 255): Rgba {
  return o.actor === "UA" ? rgba(C.ua, a) : o.actor === "RU" ? rgba(C.ru, a) : rgba(C.neutral, a);
}

export interface ObsLayerOpts {
  selectedId: string | null;
  hoveredId: string | null;
  showLeaders: boolean;
  onClick: (o: Observation | null) => void;
  onHover: (o: Observation | null) => void;
}

export function observationLayers(all: Observation[], opts: ObsLayerOpts): Layer[] {
  const data = all.filter((o) => o.geometry);
  const isHot = (o: Observation) => o.id === opts.selectedId || o.id === opts.hoveredId;
  const triggers = [opts.selectedId, opts.hoveredId];

  return [
    new LineLayer<Observation>({
      id: "obs-leaders",
      data: data.filter((o) => o.front_anchor && (opts.showLeaders || isHot(o))),
      getSourcePosition: pos,
      getTargetPosition: (o) => o.front_anchor!.coordinates as Pos,
      getColor: (o) => actorColor(o, isHot(o) ? 230 : 120),
      getWidth: (o) => (isHot(o) ? 2 : 1),
      widthUnits: "pixels",
      updateTriggers: { getColor: triggers, getWidth: triggers },
    }),
    new ScatterplotLayer<Observation>({
      id: "obs-markers",
      data,
      pickable: true,
      getPosition: pos,
      radiusUnits: "pixels",
      getRadius: (o) => (isHot(o) ? 8 : 5.5),
      stroked: true,
      filled: true,
      // assessed/geolocated: solid; claimed: hollow amber; reported: hollow grey; denied: faint
      getFillColor: (o) =>
        o.status === "assessed" || o.status === "geolocated" ? actorColor(o) : [11, 15, 20, 180],
      getLineColor: (o) =>
        o.status === "claimed" ? rgba(C.claim)
        : o.status === "reported" ? rgba(C.neutral)
        : o.status === "denied" ? rgba(C.neutral, 90)
        : o.status === "geolocated" ? [255, 255, 255, 255]
        : actorColor(o),
      lineWidthUnits: "pixels",
      getLineWidth: (o) => (o.status === "geolocated" ? 2 : 1.6),
      onClick: (info: PickingInfo<Observation>) => {
        opts.onClick(info.object ?? null);
        return true;
      },
      onHover: (info: PickingInfo<Observation>) => opts.onHover(info.object ?? null),
      updateTriggers: { getRadius: triggers },
    }),
    new TextLayer<Observation>({
      id: "obs-labels",
      data,
      getPosition: pos,
      getText: (o) => `${o.place.canonical_name ?? o.place.name}${o.corroboration > 1 ? ` ×${o.corroboration}` : ""}`,
      getPixelOffset: [10, 0],
      getTextAnchor: "start",
      getAlignmentBaseline: "center",
      getSize: 12,
      sizeUnits: "pixels",
      fontFamily: "IBM Plex Sans Condensed, system-ui, sans-serif",
      fontWeight: 500,
      getColor: (o) => (o.status === "claimed" ? rgba(C.claim) : [230, 234, 240, 255]),
      background: true,
      backgroundPadding: [4, 2],
      getBackgroundColor: [11, 15, 20, 210],
      // Collision: better-sourced observations win label space. CollisionFilterExtension
      // rendered NO labels in headless SwiftShader (luma.gl "collisionUniforms" reflection
      // warning) on deck 9.4 + MapLibre 6.13 — verify on a real GPU before enabling.
      extensions: COLLISION ? [new CollisionFilterExtension()] : [],
      collisionGroup: "obs",
      getCollisionPriority: (o: Observation) => (isHot(o) ? 100 : 7 - o.credibility + o.corroboration),
      updateTriggers: { getCollisionPriority: triggers },
    } as ConstructorParameters<typeof TextLayer<Observation>>[0]),
  ];
}

export function tooltip(info: PickingInfo): { html: string } | null {
  const o = info.object as Observation | undefined;
  if (!o || info.layer?.id !== "obs-markers") return null;
  const esc = (s: string) => s.replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`);
  return {
    html: `<div class="tt"><b>${esc(o.place.canonical_name ?? o.place.name)}</b> · ${o.kind} · <i>${o.status}</i><br/>${esc(o.summary)}</div>`,
  };
}
