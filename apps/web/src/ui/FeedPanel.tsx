import { useMemo } from "react";
import type { DayBundle, Manifest, Observation } from "@milmap/schema";
import { useView } from "../state/store";

/** The day's reports grouped by operational direction, linked to map markers. */
export function FeedPanel({ bundle, manifest }: { bundle: DayBundle | null; manifest: Manifest }) {
  const { statusFilter, selectedObsId, hoveredObsId, select, hover } = useView();
  const sources = useMemo(() => new Map(manifest.sources.map((s) => [s.id, s])), [manifest]);
  const groups = useMemo(() => {
    const m = new Map<string, Observation[]>();
    for (const o of bundle?.observations ?? []) {
      if (!statusFilter[o.status]) continue;
      const k = o.axis ?? "Other";
      m.set(k, [...(m.get(k) ?? []), o]);
    }
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [bundle, statusFilter]);

  return (
    <aside className="panel panel-feed" aria-label="Reports for the selected day">
      <h2>Reports · {bundle?.date ?? "—"}</h2>
      {groups.length === 0 && <p className="muted">No reports for this day.</p>}
      {groups.map(([axis, items]) => (
        <section key={axis}>
          <h3>{axis}</h3>
          <ul>
            {items.map((o) => {
              const src = sources.get(o.source_id);
              const grade = `${src?.reliability ?? "F"}${o.credibility}`;
              return (
                <li
                  key={o.id}
                  className={`obs ${o.id === selectedObsId ? "sel" : ""} ${o.id === hoveredObsId ? "hov" : ""}`}
                  onClick={() => select(o.id)}
                  onMouseEnter={() => hover(o.id)}
                  onMouseLeave={() => hover(null)}
                >
                  <div className="obs-head">
                    <span className={`chip st-${o.status} on`}>{o.status}</span>
                    <span className={`actor actor-${o.actor}`}>{o.actor}</span>
                    <b>{o.place.canonical_name ?? o.place.name}</b>
                    <span className="muted">{o.kind}</span>
                    {o.conflicts_with_assessment && <span className="flag" title="Claim lies outside the assessed-control area">≠ assessed</span>}
                  </div>
                  <p>{o.summary}</p>
                  <div className="obs-foot">
                    <span title="Admiralty grade: source reliability + information credibility">{grade}</span>
                    {o.corroboration > 1 && <span>×{o.corroboration} sources</span>}
                    <span>{src?.name ?? o.source_id}</span>
                    {o.citations[0] && (
                      <a href={o.citations[0].url} target="_blank" rel="noreferrer noopener" onClick={(e) => e.stopPropagation()}>
                        source ↗
                      </a>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </aside>
  );
}
