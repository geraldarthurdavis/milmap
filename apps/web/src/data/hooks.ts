import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import type { DayBundle, Manifest } from "@milmap/schema";
import { BundleCache, fetchManifest } from "./source";

export function useManifest() {
  return useQuery({ queryKey: ["manifest"], queryFn: fetchManifest, staleTime: 5 * 60_000 });
}

export function useBundleCache(manifest: Manifest | undefined) {
  return useMemo(
    () => (manifest ? new BundleCache(manifest.bundle_url_template) : undefined),
    [manifest],
  );
}

/** Latest bundle for `day`. Keeps showing the previous one while loading (no flash). */
export function useDayBundle(cache: BundleCache | undefined, day: number, manifest?: Manifest) {
  const [bundle, setBundle] = useState<DayBundle | null>(null);
  const prevDay = useRef(day);
  useEffect(() => {
    if (!cache || !manifest) return;
    const dir = Math.sign(day - prevDay.current) as -1 | 0 | 1;
    prevDay.current = day;
    const hit = cache.peek(day);
    if (hit !== undefined) setBundle(hit);
    let live = true;
    void cache.get(day).then((b) => live && setBundle(b));
    cache.prefetch(day, dir, manifest.day_min, manifest.day_max);
    return () => {
      live = false;
    };
  }, [cache, day, manifest]);
  return bundle;
}

/** Front lines from `day - offset` for each offset, tagged with `age` for styling. */
export function useGhostFronts(
  cache: BundleCache | undefined,
  day: number,
  offsets: number[],
  primary: string,
): GeoJSON.FeatureCollection {
  const [fc, setFc] = useState<GeoJSON.FeatureCollection>({ type: "FeatureCollection", features: [] });
  useEffect(() => {
    if (!cache) return;
    let live = true;
    void Promise.all(offsets.map((o) => cache.get(day - o).then((b) => [o, b] as const))).then((pairs) => {
      if (!live) return;
      const features: GeoJSON.Feature[] = [];
      for (const [age, b] of pairs) {
        for (const f of b?.layers[`${primary}.front`]?.features ?? []) {
          features.push({
            type: "Feature",
            geometry: f.geometry as unknown as GeoJSON.Geometry,
            properties: { age },
          });
        }
      }
      setFc({ type: "FeatureCollection", features });
    });
    return () => {
      live = false;
    };
  }, [cache, day, offsets, primary]);
  return fc;
}
