import { useEffect } from "react";
import { useView } from "../state/store";
import type { BundleCache } from "../data/source";

/** RAF-driven playback that never outruns the network: it only advances when
 * the next day's bundle is already cached (prefetch keeps it ahead). */
export function usePlayback(cache: BundleCache | undefined) {
  const playing = useView((s) => s.playing);
  useEffect(() => {
    if (!playing || !cache) return;
    let raf = 0;
    let last = performance.now();
    let acc = 0;
    const tick = (t: number) => {
      const s = useView.getState();
      acc += ((t - last) / 1000) * s.speed;
      last = t;
      if (acc >= 1) {
        acc = Math.min(acc - 1, 1); // carry remainder, never burst more than one step
        if (s.day >= s.bounds[1]) {
          useView.setState({ playing: false });
          return;
        }
        if (cache.peek(s.day + 1) !== undefined) s.step(1);
        else void cache.get(s.day + 1);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, cache]);
}

export function useKeyboard() {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest("input, select, textarea")) return;
      const s = useView.getState();
      const big = e.shiftKey ? 7 : 1;
      switch (e.key) {
        case "ArrowLeft": s.step(-big); break;
        case "ArrowRight": s.step(big); break;
        case "Home": s.setDay(s.bounds[0]); break;
        case "End": s.setDay(s.bounds[1]); break;
        case " ": s.togglePlay(); break;
        case "Escape": s.select(null); break;
        default: return;
      }
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
