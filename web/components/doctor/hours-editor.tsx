"use client";

import { useEffect, useState } from "react";
import { ReflowSummary } from "@/components/doctor/reflow-summary";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/form";
import { Callout, Card, CardHeader, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { formatMinute, timeSteps, WEEKDAYS_LONG } from "@/lib/format";
import type { Reflow, WorkingHoursItem } from "@/lib/types";

export function HoursEditor({ doctorId, onChanged }: { doctorId: number; onChanged: () => void }) {
  const [saved, setSaved] = useState<WorkingHoursItem[] | null>(null);
  const [hours, setHours] = useState<WorkingHoursItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<Reflow | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api.hours(doctorId).then((h) => {
      setSaved(h);
      setHours(h);
    });
  }, [doctorId]);

  const dirty = JSON.stringify(saved) !== JSON.stringify(hours);
  const invalid = WEEKDAYS_LONG.some((_, wd) => {
    const day = hours.filter((h) => h.weekday === wd).sort((a, b) => a.start - b.start);
    return day.some((h, i) => h.end <= h.start || (i > 0 && h.start < day[i - 1].end));
  });

  const set = (index: number, patch: Partial<WorkingHoursItem>) =>
    setHours((all) => all.map((h, i) => (i === index ? { ...h, ...patch } : h)));

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const sorted = [...hours].sort((a, b) => a.weekday - b.weekday || a.start - b.start);
      setResult(await api.saveHours(doctorId, sorted));
      setSaved(sorted);
      setHours(sorted);
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't save.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader
        title="Weekly hours"
        description="Add more than one block per day for breaks. Calls outside new hours are moved."
      />
      {saved === null ? (
        <div className="p-5">
          <Skeleton className="h-64" />
        </div>
      ) : (
        <div className="divide-y divide-line px-5 pt-3">
          {WEEKDAYS_LONG.map((name, wd) => {
            const rows = hours
              .map((h, index) => ({ h, index }))
              .filter(({ h }) => h.weekday === wd);
            return (
              <div key={name} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-start">
                <p className="w-28 shrink-0 pt-2 text-sm font-medium text-ink">{name}</p>
                <div className="flex flex-1 flex-col gap-2">
                  {rows.length === 0 && <p className="pt-2 text-sm text-ink-subtle">Not working</p>}
                  {rows.map(({ h, index }) => (
                    <div key={index} className="flex items-center gap-2">
                      <HourSelect
                        label={`${name} block start`}
                        value={h.start}
                        onChange={(start) => set(index, { start })}
                      />
                      <span className="text-[13px] text-ink-muted">to</span>
                      <HourSelect
                        label={`${name} block end`}
                        value={h.end}
                        onChange={(end) => set(index, { end })}
                      />
                      <button
                        type="button"
                        aria-label={`Remove ${name} block`}
                        title="Remove"
                        className="flex size-8 items-center justify-center rounded-md text-ink-subtle hover:bg-sunken hover:text-danger"
                        onClick={() => setHours((all) => all.filter((_, i) => i !== index))}
                      >
                        <svg viewBox="0 0 16 16" className="size-4" fill="none" aria-hidden="true">
                          <path
                            d="m4.5 4.5 7 7m0-7-7 7"
                            stroke="currentColor"
                            strokeWidth="1.5"
                            strokeLinecap="round"
                          />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  className="self-start pt-2 text-[13px] font-medium text-accent hover:text-accent-strong"
                  onClick={() => {
                    const last = rows.at(-1)?.h.end;
                    const start = last ? Math.min(last + 60, 20 * 60) : 9 * 60;
                    setHours((all) => [
                      ...all,
                      { weekday: wd, start, end: Math.min(start + 4 * 60, 22 * 60) },
                    ]);
                  }}
                >
                  + Add block
                </button>
              </div>
            );
          })}
        </div>
      )}
      <div className="flex flex-col gap-3 border-t border-line px-5 py-4">
        {invalid && (
          <Callout tone="warn" title="Blocks on the same day overlap or end before they start." />
        )}
        {error && <Callout tone="danger" title={error} />}
        {result && !dirty && <ReflowSummary reflow={result} />}
        <div className="flex justify-end gap-2">
          <Button
            variant="ghost"
            disabled={!dirty || saving}
            onClick={() => saved && setHours(saved)}
          >
            Discard
          </Button>
          <Button disabled={!dirty || invalid} loading={saving} onClick={() => void save()}>
            Save hours
          </Button>
        </div>
      </div>
    </Card>
  );
}

function HourSelect({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (minute: number) => void;
}) {
  return (
    <div className="w-[104px]">
      <Select
        aria-label={label}
        className="h-9"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      >
        {timeSteps(6 * 60, 22 * 60, 30).map((m) => (
          <option key={m} value={m}>
            {formatMinute(m)}
          </option>
        ))}
      </Select>
    </div>
  );
}
