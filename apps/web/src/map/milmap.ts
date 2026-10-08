// Imperative map controller. React owns *state*; MilMap owns the GL objects.
// Every per-day update is setData/setGlobalStateProperty — never a style rebuild.
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
// MapLibre v6 finds its module worker via import.meta.url, which bundling breaks.
// Let Vite bundle the worker (+ its shared chunk) into one file and hand MapLibre the URL.
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { MapLibreOverlay } from "@deck.gl/maplibre";
import { Protocol } from "pmtiles";
import type { DayBundle, Observation } from "@milmap/schema";
import { splitLayerId } from "@milmap/schema";
import { basemapStyle, firstLabelLayerId } from "./basemap";
import { GROUPS, SRC, overlayLayers, type GroupKey } from "./layers";
import { observationLayers, tooltip, type ObsLayerOpts } from "./observations";
import { registerPatterns } from "./patterns";

const LINE_KINDS = new Set(["front", "advance_limit", "claimed_limit", "infiltration_limit"]);
const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

let protocolInstalled = false;
const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export class MilMap {
  readonly map: maplibregl.Map;
  private overlay: MapLibreOverlay;
  private pulseRaf = 0;

  private constructor(map: maplibregl.Map, overlay: MapLibreOverlay) {
    this.map = map;
    this.overlay = overlay;
  }

  static async create(
    container: HTMLElement,
    camera: { center: [number, number]; zoom: number },
  ): Promise<MilMap> {
    if (!protocolInstalled) {
      maplibregl.setWorkerUrl(workerUrl);
      maplibregl.addProtocol("pmtiles", new Protocol().tile);
      protocolInstalled = true;
    }
    const style = await basemapStyle();
    const map = new maplibregl.Map({
      container,
      style,
      center: camera.center,
      zoom: camera.zoom,
      minZoom: 4,
      maxZoom: 15,
      maxBounds: [
        [14, 40],
        [50, 58],
      ],
      attributionControl: { compact: true },
      hash: false,
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
    await map.once("load");

    registerPatterns(map);
    map.setGlobalStateProperty("primary", "isw");
    map.setGlobalStateProperty("compare", "");
    map.setGlobalStateProperty("day", 0);
    for (const id of Object.values(SRC)) map.addSource(id, { type: "geojson", data: EMPTY, tolerance: 0.2 });
    const before = firstLabelLayerId(map.getStyle());
    for (const layer of overlayLayers()) map.addLayer(layer, before);

    const overlay = new MapLibreOverlay({ interleaved: true, layers: [], getTooltip: tooltip });
    map.addControl(overlay);
    return new MilMap(map, overlay);
  }

  setBundle(b: DayBundle | null) {
    const areas: GeoJSON.Feature[] = [];
    const lines: GeoJSON.Feature[] = [];
    const diff: GeoJSON.Feature[] = [];
    for (const [id, fc] of Object.entries(b?.layers ?? {})) {
      const { category } = splitLayerId(id);
      const target = category === "diff" ? diff : LINE_KINDS.has(category) ? lines : areas;
      for (const f of fc.features) target.push(f as unknown as GeoJSON.Feature);
    }
    this.src(SRC.areas).setData({ type: "FeatureCollection", features: areas });
    this.src(SRC.lines).setData({ type: "FeatureCollection", features: lines });
    this.src(SRC.diff).setData({ type: "FeatureCollection", features: diff });
    if (b) this.map.setGlobalStateProperty("day", b.day);
    if (diff.length) this.pulseDiff();
  }

  setGhosts(fc: GeoJSON.FeatureCollection) {
    this.src(SRC.ghosts).setData(fc);
  }

  setSources(primary: string, compare: string) {
    this.map.setGlobalStateProperty("primary", primary);
    this.map.setGlobalStateProperty("compare", compare);
  }

  setGroups(groups: Record<GroupKey, boolean>) {
    for (const [g, ids] of Object.entries(GROUPS) as [GroupKey, readonly string[]][]) {
      for (const id of ids) {
        if (this.map.getLayer(id)) this.map.setLayoutProperty(id, "visibility", groups[g] ? "visible" : "none");
      }
    }
  }

  setObservations(obs: Observation[], opts: Omit<ObsLayerOpts, "showLeaders">) {
    this.overlay.setProps({
      layers: observationLayers(obs, { ...opts, showLeaders: this.map.getZoom() >= 7.5 }),
    });
  }

  flyTo(lon: number, lat: number, zoom = Math.max(this.map.getZoom(), 9.5)) {
    if (reducedMotion()) this.map.jumpTo({ center: [lon, lat], zoom });
    else this.map.flyTo({ center: [lon, lat], zoom, speed: 1.4 });
  }

  destroy() {
    cancelAnimationFrame(this.pulseRaf);
    this.map.removeControl(this.overlay);
    this.map.remove();
  }

  private src(id: string) {
    return this.map.getSource(id) as maplibregl.GeoJSONSource;
  }

  /** Fresh change flashes bright, then settles — the eye finds today's movement. */
  private pulseDiff() {
    cancelAnimationFrame(this.pulseRaf);
    if (reducedMotion()) return;
    const t0 = performance.now();
    const tick = (t: number) => {
      const k = Math.min(1, (t - t0) / 1400);
      const op = 0.9 - 0.5 * (1 - (1 - k) ** 3);
      for (const id of ["diff-gain", "diff-loss"]) this.map.setPaintProperty(id, "fill-opacity", op);
      if (k < 1) this.pulseRaf = requestAnimationFrame(tick);
    };
    this.pulseRaf = requestAnimationFrame(tick);
  }
}
