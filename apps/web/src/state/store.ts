import { create } from "zustand";
import type { Status } from "@milmap/schema";
import type { GroupKey } from "../map/layers";

export type Speed = 1 | 2 | 4 | 8;

export interface ViewState {
  day: number;
  playing: boolean;
  speed: Speed;
  primary: string; // source id whose areas/front are drawn
  compare: string; // second source whose front is overlaid ("" = off)
  groups: Record<GroupKey, boolean>;
  ghostOffsets: number[];
  statusFilter: Record<Status, boolean>;
  selectedObsId: string | null;
  hoveredObsId: string | null;
}

interface Actions {
  setDay: (d: number) => void;
  step: (n: number) => void;
  togglePlay: () => void;
  setSpeed: (s: Speed) => void;
  setPrimary: (s: string) => void;
  setCompare: (s: string) => void;
  toggleGroup: (g: GroupKey) => void;
  toggleStatus: (s: Status) => void;
  select: (id: string | null) => void;
  hover: (id: string | null) => void;
  clamp: (min: number, max: number) => void;
}

export const useView = create<ViewState & Actions & { bounds: [number, number] }>()((set, get) => ({
  day: 0,
  bounds: [0, 0],
  playing: false,
  speed: 2,
  primary: "isw",
  compare: "",
  groups: {
    pre2022: true,
    control: true,
    advance: true,
    infiltration: true,
    claimed: true,
    uaCounter: true,
    diff: true,
    ghosts: true,
    compare: true,
    front: true,
  },
  ghostOffsets: [1, 7, 30],
  statusFilter: { assessed: true, geolocated: true, claimed: true, reported: true, denied: false },
  selectedObsId: null,
  hoveredObsId: null,

  setDay: (d) => {
    const [lo, hi] = get().bounds;
    set({ day: Math.max(lo, Math.min(hi, Math.round(d))), selectedObsId: null });
  },
  step: (n) => get().setDay(get().day + n),
  togglePlay: () => {
    const { playing, day, bounds } = get();
    // pressing play at the end restarts from 90 days back
    if (!playing && day >= bounds[1]) set({ day: Math.max(bounds[0], bounds[1] - 90) });
    set({ playing: !playing });
  },
  setSpeed: (speed) => set({ speed }),
  setPrimary: (primary) => set((s) => ({ primary, compare: s.compare === primary ? "" : s.compare })),
  setCompare: (compare) => set({ compare }),
  toggleGroup: (g) => set((s) => ({ groups: { ...s.groups, [g]: !s.groups[g] } })),
  toggleStatus: (st) => set((s) => ({ statusFilter: { ...s.statusFilter, [st]: !s.statusFilter[st] } })),
  select: (selectedObsId) => set({ selectedObsId }),
  hover: (hoveredObsId) => set({ hoveredObsId }),
  clamp: (min, max) => set((s) => ({ bounds: [min, max], day: s.day ? Math.max(min, Math.min(max, s.day)) : max })),
}));
