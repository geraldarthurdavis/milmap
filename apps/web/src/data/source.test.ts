import { afterEach, describe, expect, it, vi } from "vitest";
import { BundleCache } from "./source";
import { GROUPS, overlayLayers } from "../map/layers";

afterEach(() => vi.unstubAllGlobals());

describe("BundleCache", () => {
  it("dedupes requests, evicts LRU, and returns null for missing days", async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.includes("2026-10-06")
        ? new Response("not found", { status: 404 })
        : new Response(JSON.stringify({ day: 1, date: "x", layers: {}, observations: [] })),
    );
    vi.stubGlobal("fetch", fetchMock);
    const c = new BundleCache("days/{date}.json", 2);
    await Promise.all([c.get(1684), c.get(1684)]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(await c.get(1685)).toBeNull(); // 2026-10-06 -> 404
    await c.get(1683); // evicts 1684 (oldest)
    expect(c.peek(1684)).toBeUndefined();
    expect(c.peek(1683)).not.toBeUndefined();
  });

  it("prefetches ahead in the direction of travel within bounds", () => {
    const fetchMock = vi.fn(async (_url: string) => new Response("{}"));
    vi.stubGlobal("fetch", fetchMock);
    const c = new BundleCache("days/{date}.json", 100);
    c.prefetch(100, 1, 0, 103, 8, 2);
    const days = fetchMock.mock.calls.map((call) => String(call[0]));
    expect(days).toHaveLength(5); // 101..103 ahead (bounded) + 99, 98 behind
  });
});

describe("layer groups", () => {
  it("reference only layers that exist", () => {
    const ids = new Set(overlayLayers().map((l) => l.id));
    for (const group of Object.values(GROUPS)) for (const id of group) expect(ids.has(id)).toBe(true);
  });
});
