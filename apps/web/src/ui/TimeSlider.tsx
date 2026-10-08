import { useEffect, useMemo, useRef, useState } from "react";
import { scaleLinear } from "d3-scale";
import { max } from "d3-array";
import type { Manifest } from "@milmap/schema";
import { dayToIso, formatDay, warDayLabel } from "@milmap/schema";
import { useView, type Speed } from "../state/store";

const H = 64;
const PAD = 12;
const MID = 34;

export function TimeSlider({ manifest }: { manifest: Manifest }) {
  const { day, setDay, playing, togglePlay, speed, setSpeed, ghostOffsets } = useView();
  const wrap = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(800);
  const dragging = useRef(false);

  useEffect(() => {
    const ro = new ResizeObserver(([e]) => setW(Math.max(320, e!.contentRect.width)));
    ro.observe(wrap.current!);
    return () => ro.disconnect();
  }, []);

  const { day_min: d0, day_max: d1, stats } = manifest;
  const x = useMemo(() => scaleLinear().domain([d0, d1 + 1]).range([PAD, w - PAD]), [d0, d1, w]);
  const peak = useMemo(() => (max(stats, (s) => Math.max(s.ru_gain_km2, s.ua_gain_km2)) ?? 0) || 1, [stats]);
  const y = useMemo(() => scaleLinear().domain([0, peak]).range([0, MID - 8]), [peak]);
  const bw = Math.max(1, x(d0 + 1) - x(d0) - 0.5);

  const months = useMemo(() => {
    const out: { day: number; label: string }[] = [];
    for (let d = d0; d <= d1; d++) {
      const iso = dayToIso(d);
      if (iso.endsWith("-01")) {
        out.push({ day: d, label: new Date(iso).toLocaleString("en-GB", { month: "short", timeZone: "UTC" }) });
      }
    }
    return out;
  }, [d0, d1]);

  const today = stats.find((s) => s.day === day);
  const pick = (clientX: number) => {
    const r = wrap.current!.getBoundingClientRect();
    setDay(Math.floor(x.invert(clientX - r.left)));
  };

  return (
    <div className="slider">
      <div className="slider-controls">
        <button className="btn-play" onClick={togglePlay} aria-label={playing ? "Pause" : "Play"}>
          {playing ? "❚❚" : "▶"}
        </button>
        <select value={speed} onChange={(e) => setSpeed(Number(e.target.value) as Speed)} aria-label="Speed">
          {[1, 2, 4, 8].map((s) => (
            <option key={s} value={s}>
              {s} d/s
            </option>
          ))}
        </select>
        <div className="readout">
          <div className="readout-date">{formatDay(day)}</div>
          <div className="readout-sub">
            {warDayLabel(day)}
            {today && (
              <>
                {" · "}
                <span className="ru">+{today.ru_gain_km2.toFixed(1)}</span>
                {" / "}
                <span className="ua">+{today.ua_gain_km2.toFixed(1)}</span> km²
              </>
            )}
          </div>
        </div>
      </div>
      <div
        className="slider-track"
        ref={wrap}
        role="slider"
        tabIndex={0}
        aria-valuemin={d0}
        aria-valuemax={d1}
        aria-valuenow={day}
        aria-valuetext={formatDay(day)}
        onPointerDown={(e) => {
          dragging.current = true;
          e.currentTarget.setPointerCapture(e.pointerId);
          pick(e.clientX);
        }}
        onPointerMove={(e) => dragging.current && pick(e.clientX)}
        onPointerUp={() => (dragging.current = false)}
      >
        <svg width={w} height={H}>
          <line x1={PAD} x2={w - PAD} y1={MID} y2={MID} className="axis" />
          {stats.map((s) => (
            <g key={s.day}>
              {s.ru_gain_km2 > 0 && (
                <rect className="bar-ru" x={x(s.day)} width={bw} y={MID - y(s.ru_gain_km2)} height={y(s.ru_gain_km2)} />
              )}
              {s.ua_gain_km2 > 0 && <rect className="bar-ua" x={x(s.day)} width={bw} y={MID} height={y(s.ua_gain_km2)} />}
              {s.claims > 0 && <circle className="dot-claim" cx={x(s.day) + bw / 2} cy={4} r={1.6} />}
            </g>
          ))}
          {months.map((m) => (
            <g key={m.day} transform={`translate(${x(m.day)},0)`}>
              <line y1={MID + 10} y2={H - 12} className="tick" />
              <text y={H - 2} className="tick-label">
                {m.label}
              </text>
            </g>
          ))}
          {ghostOffsets.map((o) =>
            day - o >= d0 ? <line key={o} className="ghost-mark" x1={x(day - o)} x2={x(day - o)} y1={8} y2={MID + 8} /> : null,
          )}
          <g transform={`translate(${x(day) + bw / 2},0)`} className="playhead">
            <line y1={0} y2={H - 14} />
            <circle cy={MID} r={5} />
          </g>
        </svg>
      </div>
    </div>
  );
}
