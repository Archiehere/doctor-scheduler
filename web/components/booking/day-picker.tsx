"use client";

import { addDays, cn, parseDay, relativeDay } from "@/lib/format";
import type { CalendarDay } from "@/lib/types";

type DayState = "open" | "full" | "closed";

function dayState(info: CalendarDay | undefined, minMinutes: number): DayState {
  if (!info) return "open"; // availability not loaded yet: don't block the choice
  if (info.open_minutes === 0) return "closed";
  return info.bookable_minutes >= minMinutes ? "open" : "full";
}

export function DayPicker({
  value,
  onChange,
  from,
  count = 14,
  availability,
  minMinutes = 30,
}: {
  value: string;
  onChange: (day: string) => void;
  from: string;
  count?: number;
  availability?: Map<string, CalendarDay>;
  minMinutes?: number;
}) {
  const days = Array.from({ length: count }, (_, i) => addDays(from, i));
  return (
    <div
      role="radiogroup"
      aria-label="Day"
      className="-mx-1 flex snap-x gap-2 overflow-x-auto px-1 pb-1"
    >
      {days.map((day) => {
        const date = parseDay(day);
        const selected = day === value;
        const state = dayState(availability?.get(day), minMinutes);
        // "Tomorrow" does not fit the tile, so only today gets a relative label.
        const weekday =
          relativeDay(day) === "Today"
            ? "Today"
            : date.toLocaleDateString("en-GB", { weekday: "short" });
        return (
          <button
            key={day}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-label={`${formatLabel(date)}${state === "open" ? "" : `, ${state}`}`}
            disabled={state === "closed"}
            title={state === "full" ? "Fully booked: you can still join the waitlist" : undefined}
            onClick={() => onChange(day)}
            className={cn(
              "flex w-[68px] shrink-0 snap-start flex-col items-center rounded-md border py-2 transition-colors",
              selected
                ? "border-accent bg-accent-soft text-accent-strong"
                : "border-line-strong bg-surface text-ink hover:border-ink-subtle",
              state === "closed" &&
                "hatch cursor-not-allowed border-line text-ink-subtle hover:border-line",
              state === "full" && !selected && "text-ink-subtle",
            )}
          >
            <span className="text-[11px] font-medium tracking-wide text-current uppercase opacity-70">
              {weekday}
            </span>
            <span className="tabular mt-0.5 text-lg leading-6 font-semibold">{date.getDate()}</span>
            <span className="text-[11px] opacity-70">
              {state === "closed"
                ? "Closed"
                : state === "full"
                  ? "Full"
                  : date.toLocaleDateString("en-GB", { month: "short" })}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function formatLabel(date: Date): string {
  return date.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" });
}
