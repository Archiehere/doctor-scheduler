"use client";

import { addDays, cn, parseDay, relativeDay } from "@/lib/format";

export function DayPicker({
  value,
  onChange,
  from,
  count = 14,
}: {
  value: string;
  onChange: (day: string) => void;
  from: string;
  count?: number;
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
        return (
          <button
            key={day}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(day)}
            className={cn(
              "flex w-[68px] shrink-0 snap-start flex-col items-center rounded-md border py-2 transition-colors",
              selected
                ? "border-accent bg-accent-soft text-accent-strong"
                : "border-line-strong bg-surface text-ink hover:border-ink-subtle",
            )}
          >
            <span className="text-[11px] font-medium tracking-wide text-current uppercase opacity-70">
              {relativeDay(day) ?? date.toLocaleDateString("en-GB", { weekday: "short" })}
            </span>
            <span className="tabular mt-0.5 text-lg leading-6 font-semibold">{date.getDate()}</span>
            <span className="text-[11px] opacity-70">
              {date.toLocaleDateString("en-GB", { month: "short" })}
            </span>
          </button>
        );
      })}
    </div>
  );
}
