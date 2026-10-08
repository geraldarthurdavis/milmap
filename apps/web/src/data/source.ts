// Data access: manifest + day bundles with an LRU cache and directional prefetch.
// Scrubbing must never wait on the network for a day we've seen; playback must
// stay ahead of the playhead.
import type { DayBundle, Manifest } from "@milmap/schema";
import { dayToIso } from "@milmap/schema";

export const DATA_BASE = (import.meta.env.VITE_DATA_BASE_URL ?? "/data").replace(/\/$/, "");

export async function fetchManifest(): Promise<Manifest> {
  const r = await fetch(`${DATA_BASE}/manifest.json`, { cache: "no-cache" });
  if (!r.ok) throw new Error(`manifest: HTTP ${r.status} — run \`pnpm fixtures\` or the pipeline export`);
  return r.json();
}

type Entry = { promise: Promise<DayBundle | null>; value?: DayBundle | null };

export class BundleCache {
  private entries = new Map<number, Entry>();
  private listeners = new Set<() => void>();

  constructor(
    private template: string,
    private max = 90,
  ) {}

  url(day: number) {
    return `${DATA_BASE}/${this.template.replace("{date}", dayToIso(day))}`;
  }

  /** Synchronous hit (undefined = not loaded yet, null = no bundle for that day). */
  peek(day: number): DayBundle | null | undefined {
    return this.entries.get(day)?.value;
  }

  get(day: number): Promise<DayBundle | null> {
    const hit = this.entries.get(day);
    if (hit) {
      this.entries.delete(day); // refresh LRU position
      this.entries.set(day, hit);
      return hit.promise;
    }
    const entry: Entry = {
      promise: fetch(this.url(day))
        .then((r) => (r.ok ? (r.json() as Promise<DayBundle>) : null))
        .catch(() => null)
        .then((v) => {
          entry.value = v;
          this.listeners.forEach((l) => l());
          return v;
        }),
    };
    this.entries.set(day, entry);
    while (this.entries.size > this.max) {
      const oldest = this.entries.keys().next().value!;
      this.entries.delete(oldest);
    }
    return entry.promise;
  }

  /** Prefetch around `day`, biased toward the direction of travel. */
  prefetch(day: number, dir: -1 | 0 | 1, min: number, max: number, ahead = 8, behind = 3) {
    const order: number[] = [];
    for (let i = 1; i <= ahead; i++) order.push(day + (dir === 0 ? i : dir * i));
    for (let i = 1; i <= behind; i++) order.push(day - (dir === 0 ? i : dir * i));
    for (const d of order) if (d >= min && d <= max && !this.entries.has(d)) void this.get(d);
  }

  subscribe(fn: () => void) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }
}
