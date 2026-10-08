import { useEffect, useRef, useState } from "react";
import type { DayBundle } from "@milmap/schema";
import { MilMap } from "../map/milmap";
import { useView } from "../state/store";
import { readUrl, setUrlCamera } from "../state/url";

interface Props {
  bundle: DayBundle | null;
  ghosts: GeoJSON.FeatureCollection;
}

export function MapView({ bundle, ghosts }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const [mm, setMm] = useState<MilMap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { primary, compare, groups, statusFilter, selectedObsId, hoveredObsId, select, hover } = useView();

  useEffect(() => {
    let inst: MilMap | null = null;
    let cancelled = false;
    const cam = readUrl().camera;
    MilMap.create(el.current!, {
      center: cam ? [cam.lon, cam.lat] : [37.4, 48.6],
      zoom: cam?.zoom ?? 6.6,
    })
      .then((m) => {
        if (cancelled) return m.destroy();
        inst = m;
        m.map.on("moveend", () => {
          const c = m.map.getCenter();
          setUrlCamera(m.map.getZoom(), c.lat, c.lng);
        });
        setMm(m);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
    return () => {
      cancelled = true;
      inst?.destroy();
    };
  }, []);

  useEffect(() => void mm?.setBundle(bundle), [mm, bundle]);
  useEffect(() => void mm?.setGhosts(ghosts), [mm, ghosts]);
  useEffect(() => void mm?.setSources(primary, groups.compare ? compare : ""), [mm, primary, compare, groups.compare]);
  useEffect(() => void mm?.setGroups(groups), [mm, groups]);

  useEffect(() => {
    if (!mm) return;
    const obs = (bundle?.observations ?? []).filter((o) => statusFilter[o.status]);
    const render = () =>
      mm.setObservations(obs, {
        selectedId: selectedObsId,
        hoveredId: hoveredObsId,
        onClick: (o) => select(o?.id ?? null),
        onHover: (o) => hover(o?.id ?? null),
      });
    render();
    mm.map.on("zoomend", render);
    return () => void mm.map.off("zoomend", render);
  }, [mm, bundle, statusFilter, selectedObsId, hoveredObsId, select, hover]);

  // Fly to a newly selected observation.
  useEffect(() => {
    const o = bundle?.observations.find((x) => x.id === selectedObsId);
    const c = o?.geometry?.coordinates;
    if (mm && c) mm.flyTo(c[0]!, c[1]!);
  }, [mm, selectedObsId]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="map" ref={el} aria-label="War map">
      {error && <div className="map-error">Map failed to load: {error}</div>}
    </div>
  );
}
