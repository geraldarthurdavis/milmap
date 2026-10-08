import { describe, expect, it } from "vitest";
import { dayIndex, dayToIso } from "./time";

describe("day index", () => {
  it("matches the pipeline epoch", () => {
    expect(dayIndex("2022-02-24")).toBe(0);
    expect(dayIndex("2026-10-06")).toBe(1685); // same value make_fixtures.py writes
  });
  it("round-trips across DST and leap years", () => {
    for (const d of [0, 371, 1000, 1685, 2000]) expect(dayIndex(dayToIso(d))).toBe(d);
  });
});
