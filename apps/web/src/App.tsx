import { useEffect } from "react";
import { useBundleCache, useDayBundle, useGhostFronts, useManifest } from "./data/hooks";
import { useView } from "./state/store";
import { readUrl, startUrlSync } from "./state/url";
import { FeedPanel } from "./ui/FeedPanel";
import { LayerPanel } from "./ui/LayerPanel";
import { MapView } from "./ui/MapView";
import { TimeSlider } from "./ui/TimeSlider";
import { useKeyboard, usePlayback } from "./ui/usePlayback";

export function App() {
  const { data: manifest, error } = useManifest();
  const cache = useBundleCache(manifest);
  const { day, primary, ghostOffsets, groups } = useView();

  useEffect(() => {
    if (!manifest) return;
    const u = readUrl();
    useView.getState().clamp(manifest.day_min, manifest.day_max);
    useView.setState((s) => ({
      day: Math.min(manifest.day_max, Math.max(manifest.day_min, u.day ?? manifest.day_max)),
      primary: u.primary ?? s.primary,
      compare: u.compare ?? s.compare,
    }));
    return startUrlSync();
  }, [manifest]);

  const bundle = useDayBundle(cache, day, manifest);
  const ghosts = useGhostFronts(cache, day, groups.ghosts ? ghostOffsets : [], primary);
  usePlayback(cache);
  useKeyboard();

  if (error) return <div className="fatal">{String(error)}</div>;
  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">MILMAP</span>
        <span className="muted">Russia–Ukraine · assessed vs claimed, by day</span>
        {manifest?.synthetic && <span className="banner-synthetic">SYNTHETIC DEMO DATA — NOT REAL</span>}
      </header>
      <MapView bundle={bundle} ghosts={ghosts} />
      {manifest && <LayerPanel manifest={manifest} />}
      {manifest && <FeedPanel bundle={bundle} manifest={manifest} />}
      {manifest && <TimeSlider manifest={manifest} />}
      <footer className="attribution">
        {manifest?.sources.map((s) => s.name).join(" · ")} · Basemap © OpenStreetMap contributors
      </footer>
    </div>
  );
}
