"use client";

import { useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { Select } from "@/components/ui/form";
import { cn, formatMinute, formatRange, timeSteps } from "@/lib/format";
import type { DemandProfile, TimeRange } from "@/lib/types";

const DAY_START = 7 * 60;
const DAY_END = 21 * 60;
const SPAN = DAY_END - DAY_START;
const STEP = 15;

const PRESETS: { label: string; range: TimeRange }[] = [
  { label: "Morning", range: { start: 8 * 60, end: 12 * 60 } },
  { label: "Afternoon", range: { start: 12 * 60, end: 17 * 60 } },
  { label: "Evening", range: { start: 17 * 60, end: 21 * 60 } },
  { label: "Any time", range: { start: 8 * 60, end: 21 * 60 } },
];

export function mergeRanges(ranges: TimeRange[]): TimeRange[] {
  const sorted = [...ranges].filter((r) => r.end > r.start).sort((a, b) => a.start - b.start);
  const out: TimeRange[] = [];
  for (const r of sorted) {
    const last = out.at(-1);
    if (last && r.start <= last.end) last.end = Math.max(last.end, r.end);
    else out.push({ ...r });
  }
  return out;
}

const pct = (minute: number) => `${((minute - DAY_START) / SPAN) * 100}%`;

/**
 * Availability input drawn as a day timeline. Drag across the track to add a window,
 * tap inside a window to set the preferred time. Every action also has a keyboard
 * equivalent in the controls below the track.
 */
export function RangePicker({
  ranges,
  preferred,
  duration,
  demand,
  onChange,
}: {
  ranges: TimeRange[];
  preferred: number | null;
  duration: number;
  demand: DemandProfile | null;
  onChange: (ranges: TimeRange[], preferred: number | null) => void;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<{ anchor: number; current: number } | null>(null);

  const minuteAt = (clientX: number) => {
    const rect = trackRef.current!.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    return DAY_START + Math.round((ratio * SPAN) / STEP) * STEP;
  };

  const commit = (next: TimeRange[], nextPreferred: number | null = preferred) => {
    const merged = mergeRanges(next);
    const inside = (m: number | null) =>
      m !== null && merged.some((r) => m >= r.start && m <= r.end - duration);
    const fallback = merged.find((r) => r.end - r.start >= duration)?.start ?? null;
    onChange(merged, inside(nextPreferred) ? nextPreferred : fallback);
  };

  const onPointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    const m = minuteAt(e.clientX);
    setDrag({ anchor: m, current: m });
  };

  const onPointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (drag) setDrag({ ...drag, current: minuteAt(e.clientX) });
  };

  const onPointerUp = () => {
    if (!drag) return;
    const start = Math.min(drag.anchor, drag.current);
    const end = Math.max(drag.anchor, drag.current);
    setDrag(null);
    if (end - start >= STEP * 2) {
      commit([...ranges, { start, end: Math.max(end, start + duration) }]);
      return;
    }
    // A tap: inside a window sets the preferred time, outside adds a one-hour window.
    const tapped = Math.floor(drag.anchor / STEP) * STEP;
    const hit = ranges.find((r) => tapped >= r.start && tapped < r.end);
    if (hit) {
      commit(ranges, Math.min(tapped, hit.end - duration));
    } else {
      const s = Math.min(tapped, DAY_END - 60);
      commit([...ranges, { start: s, end: s + 60 }], s);
    }
  };

  const draft = drag && {
    start: Math.min(drag.anchor, drag.current),
    end: Math.max(drag.anchor, drag.current),
  };
  const preferredOptions = ranges.flatMap((r) =>
    r.end - r.start >= duration ? timeSteps(r.start, r.end - duration) : [],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-2">
        {PRESETS.map((p) => (
          <button
            key={p.label}
            type="button"
            onClick={() => commit([p.range], preferred)}
            className="h-8 rounded-md border border-line-strong bg-surface px-3 text-[13px] text-ink transition-colors hover:bg-sunken"
          >
            {p.label}
            <span className="tabular ml-1.5 text-ink-subtle">
              {formatMinute(p.range.start)}–{formatMinute(p.range.end)}
            </span>
          </button>
        ))}
        {ranges.length > 0 && (
          <button
            type="button"
            onClick={() => onChange([], null)}
            className="h-8 rounded-md px-3 text-[13px] text-ink-muted hover:bg-sunken hover:text-ink"
          >
            Clear
          </button>
        )}
      </div>

      <div>
        <div
          ref={trackRef}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={() => setDrag(null)}
          className="relative h-16 cursor-crosshair touch-none overflow-hidden rounded-md border border-line-strong bg-surface select-none"
          aria-hidden="true"
        >
          {demand?.points.map((p) =>
            p.minute >= DAY_START && p.minute < DAY_END ? (
              <div
                key={p.minute}
                className="absolute inset-y-0 bg-accent"
                style={{
                  left: pct(p.minute),
                  width: `${(STEP / SPAN) * 100}%`,
                  opacity: 0.03 + p.index * 0.14,
                }}
              />
            ) : null,
          )}
          {timeSteps(DAY_START + 60, DAY_END - 60, 60).map((m) => (
            <div key={m} className="absolute inset-y-0 w-px bg-line" style={{ left: pct(m) }} />
          ))}
          {ranges.map((r) => (
            <div
              key={`${r.start}-${r.end}`}
              className="absolute inset-y-1.5 rounded-sm border border-accent bg-accent/15"
              style={{ left: pct(r.start), width: `${((r.end - r.start) / SPAN) * 100}%` }}
            >
              <span className="tabular absolute top-1 left-1.5 truncate text-[11px] font-medium text-accent-strong">
                {formatRange(r.start, r.end)}
              </span>
            </div>
          ))}
          {draft && draft.end > draft.start && (
            <div
              className="absolute inset-y-1.5 rounded-sm border border-dashed border-accent bg-accent/10"
              style={{
                left: pct(draft.start),
                width: `${((draft.end - draft.start) / SPAN) * 100}%`,
              }}
            />
          )}
          {preferred !== null && (
            <div className="absolute inset-y-0" style={{ left: pct(preferred) }}>
              <div className="absolute inset-y-0 -ml-px w-0.5 bg-ink" />
              <div className="absolute bottom-1.5 -ml-1 size-2 rounded-full bg-ink" />
            </div>
          )}
        </div>
        <div className="tabular relative mt-1.5 h-4 text-[11px] text-ink-subtle">
          {timeSteps(DAY_START, DAY_END, 120).map((m, i) => (
            <span
              key={m}
              className={cn(
                "absolute",
                m === DAY_START ? "" : m === DAY_END ? "-translate-x-full" : "-translate-x-1/2",
                i % 2 === 1 && "max-sm:hidden", // every 4 h on phones so labels don't collide
              )}
              style={{ left: pct(m) }}
            >
              {formatMinute(m)}
            </span>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-ink-muted">
          <span>Drag to add a window. Tap inside it to set your preferred time.</span>
          {demand && (
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-6 rounded-sm bg-gradient-to-r from-accent/5 to-accent/20" />
              Darker = busier hours
            </span>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-2">
        {ranges.map((r, i) => (
          <RangeRow
            key={`${r.start}-${r.end}-${i}`}
            range={r}
            duration={duration}
            onChange={(next) => commit(ranges.map((x, j) => (j === i ? next : x)))}
            onRemove={() => commit(ranges.filter((_, j) => j !== i))}
          />
        ))}
        {ranges.length < 4 && (
          <button
            type="button"
            onClick={() => {
              const last = ranges.at(-1)?.end ?? 9 * 60;
              const start = Math.min(last + 60, DAY_END - 120);
              commit([...ranges, { start, end: start + 120 }]);
            }}
            className="self-start text-[13px] font-medium text-accent hover:text-accent-strong"
          >
            + Add a time window
          </button>
        )}
      </div>

      {preferredOptions.length > 0 && (
        <div className="flex max-w-xs flex-col gap-1.5">
          <label htmlFor="preferred-time" className="text-[13px] font-medium text-ink">
            Preferred start time
          </label>
          <Select
            id="preferred-time"
            value={preferred ?? ""}
            onChange={(e) => commit(ranges, Number(e.target.value))}
          >
            {preferredOptions.map((m) => (
              <option key={m} value={m}>
                {formatMinute(m)}
              </option>
            ))}
          </Select>
        </div>
      )}
    </div>
  );
}

function RangeRow({
  range,
  duration,
  onChange,
  onRemove,
}: {
  range: TimeRange;
  duration: number;
  onChange: (range: TimeRange) => void;
  onRemove: () => void;
}) {
  const tooShort = range.end - range.start < duration;
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="w-16 text-[13px] text-ink-muted">Free from</span>
      <TimeSelect
        label="Window start"
        value={range.start}
        options={timeSteps(DAY_START, range.end - STEP)}
        onChange={(start) => onChange({ ...range, start })}
      />
      <span className="text-[13px] text-ink-muted">to</span>
      <TimeSelect
        label="Window end"
        value={range.end}
        options={timeSteps(range.start + STEP, DAY_END)}
        onChange={(end) => onChange({ ...range, end })}
      />
      <button
        type="button"
        onClick={onRemove}
        className="rounded-md px-2 py-1 text-[13px] text-ink-muted hover:bg-sunken hover:text-danger"
      >
        Remove
      </button>
      {tooShort && <span className="text-xs text-warn">Too short for a {duration} min call</span>}
    </div>
  );
}

function TimeSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: number;
  options: number[];
  onChange: (minute: number) => void;
}) {
  return (
    <div className="w-[104px]">
      <Select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-9"
      >
        {options.map((m) => (
          <option key={m} value={m}>
            {formatMinute(m)}
          </option>
        ))}
      </Select>
    </div>
  );
}
