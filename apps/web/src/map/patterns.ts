// Runtime-generated fill patterns and line glyphs (no sprite build step).
// Re-register after any setStyle(): style swaps drop images.
import type { Map as MlMap } from "maplibre-gl";
import { C } from "./palette";

const PR = 2; // render at 2x for crisp hatching on HiDPI

function canvas(w: number, h: number) {
  const c = document.createElement("canvas");
  c.width = w * PR;
  c.height = h * PR;
  const ctx = c.getContext("2d")!;
  ctx.scale(PR, PR);
  return { c, ctx };
}

function hatch(color: string, opts: { gap?: number; width?: number; angle?: 1 | -1; bg?: string } = {}) {
  const { gap = 8, width = 1.6, angle = 1, bg } = opts;
  const { c, ctx } = canvas(gap, gap);
  if (bg) {
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, gap, gap);
  }
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.lineCap = "square";
  ctx.beginPath();
  // three strokes so the diagonal tiles seamlessly
  for (const o of [-gap, 0, gap]) {
    if (angle === 1) {
      ctx.moveTo(o, gap);
      ctx.lineTo(o + gap, 0);
    } else {
      ctx.moveTo(o, 0);
      ctx.lineTo(o + gap, gap);
    }
  }
  ctx.stroke();
  return c;
}

function stipple(color: string, gap = 6, r = 1.1) {
  const { c, ctx } = canvas(gap, gap);
  ctx.fillStyle = color;
  for (const [x, y] of [
    [gap / 4, gap / 4],
    [(3 * gap) / 4, (3 * gap) / 4],
  ] as const) {
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
  }
  return c;
}

/** Front-line tooth: apex points "down" (+y). With symbol-placement=line and a
 * negative y icon-offset the tooth sits on the line's LEFT (controller) side,
 * apex toward the other side. Pipeline guarantees controller-on-left. */
function tooth(color: string) {
  const { c, ctx } = canvas(10, 7);
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(0.5, 0.5);
  ctx.lineTo(9.5, 0.5);
  ctx.lineTo(5, 6.5);
  ctx.closePath();
  ctx.fill();
  return c;
}

function toImage(c: HTMLCanvasElement) {
  return c.getContext("2d")!.getImageData(0, 0, c.width, c.height);
}

export const PATTERN = {
  advance: "pat-advance",
  infiltration: "pat-infiltration",
  claimed: "pat-claimed",
  uaCounter: "pat-ua-counter",
  contested: "pat-contested",
  tooth: "glyph-tooth",
} as const;

export function registerPatterns(map: MlMap) {
  const add = (id: string, c: HTMLCanvasElement) => {
    if (map.hasImage(id)) map.removeImage(id);
    map.addImage(id, toImage(c), { pixelRatio: PR });
  };
  add(PATTERN.advance, hatch(C.ruAdvance, { gap: 7, width: 1.8 }));
  add(PATTERN.infiltration, stipple(C.ruInfiltration));
  add(PATTERN.claimed, hatch(C.claim, { gap: 9, width: 1.4, angle: -1 }));
  add(PATTERN.uaCounter, hatch(C.ua, { gap: 8, width: 1.8 }));
  add(PATTERN.contested, hatch(C.neutral, { gap: 6, width: 1 }));
  add(PATTERN.tooth, tooth(C.ru));
}

/** Same patterns as CSS backgrounds for the legend. */
export function patternDataUrl(kind: keyof typeof PATTERN): string {
  const c =
    kind === "advance" ? hatch(C.ruAdvance, { gap: 7, width: 1.8 })
    : kind === "infiltration" ? stipple(C.ruInfiltration)
    : kind === "claimed" ? hatch(C.claim, { gap: 9, width: 1.4, angle: -1 })
    : kind === "uaCounter" ? hatch(C.ua, { gap: 8, width: 1.8 })
    : kind === "tooth" ? tooth(C.ru)
    : hatch(C.neutral, { gap: 6, width: 1 });
  return c.toDataURL();
}
