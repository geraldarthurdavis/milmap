// Mirror of pipeline/milmap/timeutil.py — day 0 = 2022-02-24 (UTC calendar dates).
export const EPOCH_ISO = "2022-02-24";
const EPOCH_MS = Date.UTC(2022, 1, 24);
const DAY_MS = 86_400_000;

export function dayIndex(isoDate: string): number {
  const [y, m, d] = isoDate.split("-").map(Number);
  return Math.round((Date.UTC(y!, m! - 1, d!) - EPOCH_MS) / DAY_MS);
}

export function dayToIso(day: number): string {
  return new Date(EPOCH_MS + day * DAY_MS).toISOString().slice(0, 10);
}

export function formatDay(day: number, locale = "en-GB"): string {
  return new Date(EPOCH_MS + day * DAY_MS).toLocaleDateString(locale, {
    timeZone: "UTC",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** "Day 1,685 of the full-scale invasion" — ISW/OSINT readers think in war-days too. */
export function warDayLabel(day: number): string {
  return `Day ${(day + 1).toLocaleString("en-US")}`;
}
