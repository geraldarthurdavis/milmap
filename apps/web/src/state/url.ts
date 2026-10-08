// Shareable URL state in the hash: #d=2026-10-06&m=8.4/48.52/37.66&p=isw&c=deepstate
// Every view a user can reach must be reproducible from a pasted link.
import { dayIndex, dayToIso } from "@milmap/schema";
import { useView } from "./store";

export interface UrlState {
  day?: number;
  camera?: { zoom: number; lat: number; lon: number };
  primary?: string;
  compare?: string;
}

export function readUrl(): UrlState {
  const p = new URLSearchParams(location.hash.slice(1));
  const out: UrlState = {};
  const d = p.get("d");
  if (d && /^\d{4}-\d{2}-\d{2}$/.test(d)) out.day = dayIndex(d);
  const m = p.get("m")?.split("/").map(Number);
  if (m?.length === 3 && m.every(Number.isFinite)) out.camera = { zoom: m[0]!, lat: m[1]!, lon: m[2]! };
  if (p.get("p")) out.primary = p.get("p")!;
  if (p.get("c")) out.compare = p.get("c")!;
  return out;
}

let camera = "";
export function setUrlCamera(zoom: number, lat: number, lon: number) {
  camera = `${zoom.toFixed(2)}/${lat.toFixed(4)}/${lon.toFixed(4)}`;
  schedule();
}

let timer: number | undefined;
function schedule() {
  clearTimeout(timer);
  timer = window.setTimeout(write, 250);
}

function write() {
  const s = useView.getState();
  const p = new URLSearchParams();
  p.set("d", dayToIso(s.day));
  if (camera) p.set("m", camera);
  p.set("p", s.primary);
  if (s.compare) p.set("c", s.compare);
  history.replaceState(null, "", `#${p.toString()}`);
}

export function startUrlSync() {
  return useView.subscribe((s, prev) => {
    if (s.day !== prev.day || s.primary !== prev.primary || s.compare !== prev.compare) schedule();
  });
}
