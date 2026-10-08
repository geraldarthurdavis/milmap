import type { Manifest, Status } from "@milmap/schema";
import type { GroupKey } from "../map/layers";
import { C } from "../map/palette";
import { patternDataUrl } from "../map/patterns";
import { useView } from "../state/store";

type Swatch = { kind: "fill"; color: string; alpha?: number } | { kind: "pattern"; p: Parameters<typeof patternDataUrl>[0] }
  | { kind: "line"; color: string; dash?: boolean; dotted?: boolean };

const ROWS: { group: GroupKey; label: string; swatch: Swatch }[] = [
  { group: "front", label: "Front line (assessed)", swatch: { kind: "line", color: C.ru } },
  { group: "control", label: "Assessed Russian control", swatch: { kind: "fill", color: C.ru, alpha: 0.45 } },
  { group: "pre2022", label: "Occupied before 24 Feb 2022", swatch: { kind: "fill", color: C.ruDeep, alpha: 0.8 } },
  { group: "advance", label: "Assessed Russian advances", swatch: { kind: "pattern", p: "advance" } },
  { group: "infiltration", label: "Assessed infiltration areas", swatch: { kind: "pattern", p: "infiltration" } },
  { group: "claimed", label: "Claimed Russian control", swatch: { kind: "pattern", p: "claimed" } },
  { group: "uaCounter", label: "Claimed UA counteroffensives", swatch: { kind: "pattern", p: "uaCounter" } },
  { group: "diff", label: "Change since previous day", swatch: { kind: "fill", color: C.ru, alpha: 0.7 } },
  { group: "ghosts", label: "Front 1 / 7 / 30 days ago", swatch: { kind: "line", color: C.ghost, dash: true } },
  { group: "compare", label: "Comparison source front", swatch: { kind: "line", color: C.compare, dash: true } },
];

const STATUSES: Status[] = ["assessed", "geolocated", "claimed", "reported", "denied"];

function SwatchEl({ s }: { s: Swatch }) {
  if (s.kind === "fill") return <span className="sw" style={{ background: s.color, opacity: s.alpha ?? 1 }} />;
  if (s.kind === "pattern") return <span className="sw" style={{ backgroundImage: `url(${patternDataUrl(s.p)})`, backgroundSize: "8px" }} />;
  return <span className="sw sw-line" style={{ borderTop: `3px ${s.dash ? "dashed" : "solid"} ${s.color}` }} />;
}

export function LayerPanel({ manifest }: { manifest: Manifest }) {
  const { groups, toggleGroup, primary, setPrimary, compare, setCompare, statusFilter, toggleStatus } = useView();
  const mapSources = manifest.sources.filter((s) => manifest.layers.some((l) => l.source_id === s.id && l.geom !== "point"));

  return (
    <aside className="panel panel-layers" aria-label="Layers">
      <h2>Sources</h2>
      <label className="row">
        <span>Primary</span>
        <select value={primary} onChange={(e) => setPrimary(e.target.value)}>
          {mapSources.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
      </label>
      <label className="row">
        <span>Compare</span>
        <select value={compare} onChange={(e) => setCompare(e.target.value)}>
          <option value="">— none —</option>
          {mapSources.filter((s) => s.id !== primary).map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
      </label>

      <h2>Layers</h2>
      {ROWS.map((r) => (
        <label key={r.group} className="row toggle">
          <input type="checkbox" checked={groups[r.group]} onChange={() => toggleGroup(r.group)} />
          <SwatchEl s={r.swatch} />
          <span>{r.label}</span>
        </label>
      ))}

      <h2>Reports</h2>
      <div className="chips">
        {STATUSES.map((s) => (
          <button key={s} className={`chip st-${s} ${statusFilter[s] ? "on" : ""}`} onClick={() => toggleStatus(s)}>
            {s}
          </button>
        ))}
      </div>
    </aside>
  );
}
