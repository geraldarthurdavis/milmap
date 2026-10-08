// One palette for map + legend + UI. ISW-derived conventions:
// red = Russian control, hatched = advances/claims, blue = Ukrainian actions,
// amber = *claims* (unverified), dashed = less certain than solid.
export const C = {
  ru: "#e0352b",
  ruDeep: "#7f1610", // occupied before 2022-02-24
  ruAdvance: "#ff6b5e",
  ruInfiltration: "#c2185b",
  claim: "#f5a524",
  ua: "#2f7bf5",
  uaLight: "#7fb2ff",
  compare: "#2ec4b6", // second source's front (e.g. DeepState) when comparing
  ghost: "#ff8a80",
  casing: "#0b0f14",
  neutral: "#9aa4b2",
} as const;

export type Rgba = [number, number, number, number];

export function rgba(hex: string, a = 255): Rgba {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255, a];
}

export const STATUS_STYLE = {
  assessed: { label: "Assessed", fill: true, dash: false },
  geolocated: { label: "Geolocated", fill: true, dash: false },
  claimed: { label: "Claimed", fill: false, dash: true },
  reported: { label: "Reported", fill: false, dash: false },
  denied: { label: "Denied", fill: false, dash: true },
} as const;
