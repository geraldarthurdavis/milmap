// Basemap selection.
//  * Production: self-hosted Protomaps extract (OSM-derived, one PMTiles file on R2/S3):
//      pmtiles extract https://build.protomaps.com/<date>.pmtiles ua.pmtiles --bbox=21.5,43.5,41.5,53.5
//    styled by @protomaps/basemaps with English labels.
//  * Dev fallback (no key, no setup): OpenFreeMap "dark" (OpenMapTiles schema).
// Plus keyless hillshade from AWS Terrain Tiles (Terrarium encoding, open data).
import type { StyleSpecification } from "maplibre-gl";
import { layers, namedFlavor } from "@protomaps/basemaps";

/** Used when the basemap can't be reached (offline dev, CI screenshots): overlays still render. */
const OFFLINE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "background", type: "background", paint: { "background-color": "#11161d" } }],
};

const TERRAIN ="https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";

export async function basemapStyle(): Promise<StyleSpecification> {
  const pm = import.meta.env.VITE_PMTILES_URL;
  const style: StyleSpecification = pm
    ? {
        version: 8,
        glyphs: "https://protomaps.github.io/basemaps-assets/fonts/{fontstack}/{range}.pbf",
        sprite: `https://protomaps.github.io/basemaps-assets/sprites/v4/${flavor()}`,
        sources: {
          protomaps: {
            type: "vector",
            url: `pmtiles://${pm}`,
            attribution: '<a href="https://openstreetmap.org/copyright">© OpenStreetMap</a>',
          },
        },
        layers: layers("protomaps", namedFlavor(flavor()), { lang: "en" }),
      }
    : await fetch("https://tiles.openfreemap.org/styles/dark")
        .then((r) => (r.ok ? (r.json() as Promise<StyleSpecification>) : structuredClone(OFFLINE)))
        .catch(() => structuredClone(OFFLINE));

  style.sources["terrain-dem"] = {
    type: "raster-dem",
    tiles: [TERRAIN],
    encoding: "terrarium",
    tileSize: 256,
    maxzoom: 13,
    attribution: "Terrain: Mapzen / AWS Open Data",
  };
  // Hillshade under everything but the background — the Donbas ridges and river
  // valleys explain a lot of the front's shape.
  const bgIdx = style.layers.findIndex((l) => l.type === "background");
  style.layers.splice(bgIdx + 1, 0, {
    id: "hillshade",
    type: "hillshade",
    source: "terrain-dem",
    paint: {
      "hillshade-exaggeration": 0.35,
      "hillshade-shadow-color": "#000000",
      "hillshade-highlight-color": "#ffffff",
    },
  });
  return style;
}

function flavor(): string {
  return import.meta.env.VITE_BASEMAP_FLAVOR ?? "dark";
}

/** First symbol layer: our overlays go beneath it so place names stay legible. */
export function firstLabelLayerId(style: StyleSpecification): string | undefined {
  return style.layers.find((l) => l.type === "symbol")?.id;
}
