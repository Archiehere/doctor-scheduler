"use client";

import { useState } from "react";
import { ReflowSummary } from "@/components/doctor/reflow-summary";
import { Button } from "@/components/ui/button";
import { Field, Input, Segmented, Select } from "@/components/ui/form";
import { Callout, Card, CardHeader, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { formatDay, formatMinute, formatRange, timeSteps, todayIso } from "@/lib/format";
import type { Reflow, TimeOff, TimeOffKind } from "@/lib/types";

export function TimeOffPanel({ doctorId, onChanged }: { doctorId: number; onChanged: () => void }) {
  const itemsRes = useApi(() => api.timeOff(doctorId), String(doctorId));
  const items = itemsRes.data ?? null;
  const [kind, setKind] = useState<TimeOffKind>("leave");
  const [day, setDay] = useState(todayIso);
  const [start, setStart] = useState(12 * 60);
  const [end, setEnd] = useState(14 * 60);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState<number | null>(null);
  const [result, setResult] = useState<Reflow | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setSaving(true);
    setError(null);
    setResult(null);
    try {
      const created = await api.addTimeOff(doctorId, {
        day,
        kind,
        reason: reason.trim() || undefined,
        ...(kind === "block" ? { start_minute: start, end_minute: end } : {}),
      });
      setResult(created.reflow);
      setReason("");
      itemsRes.reload();
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't save.");
    } finally {
      setSaving(false);
    }
  }

  async function remove(item: TimeOff) {
    setRemoving(item.id);
    try {
      await api.removeTimeOff(doctorId, item.id);
      itemsRes.reload();
      onChanged();
    } finally {
      setRemoving(null);
    }
  }

  return (
    <Card>
      <CardHeader
        title="Leave and blocked time"
        description="Booked calls that clash are moved automatically: first to another doctor at the same time, then to another time in the patient's window."
      />
      <form
        className="grid gap-4 px-5 pt-5 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <Segmented
          className="sm:col-span-2"
          label="Type of time off"
          value={kind}
          onChange={setKind}
          options={[
            { value: "leave", label: "Leave", description: "The whole day" },
            { value: "block", label: "Block time", description: "Part of a day" },
          ]}
        />
        <Field label="Date">
          {(id) => (
            <Input
              id={id}
              type="date"
              min={todayIso()}
              value={day}
              onChange={(e) => setDay(e.target.value)}
              required
            />
          )}
        </Field>
        <Field label="Reason" hint="Optional, only you see this">
          {(id) => (
            <Input
              id={id}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={kind === "leave" ? "Annual leave" : "Ward round"}
            />
          )}
        </Field>
        {kind === "block" && (
          <>
            <Field label="From">
              {(id) => (
                <Select id={id} value={start} onChange={(e) => setStart(Number(e.target.value))}>
                  {timeSteps(6 * 60, 22 * 60 - 15).map((m) => (
                    <option key={m} value={m}>
                      {formatMinute(m)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Until" error={end <= start ? "Must be after the start" : undefined}>
              {(id) => (
                <Select id={id} value={end} onChange={(e) => setEnd(Number(e.target.value))}>
                  {timeSteps(6 * 60 + 15, 22 * 60).map((m) => (
                    <option key={m} value={m}>
                      {formatMinute(m)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </>
        )}
        <div className="flex justify-end sm:col-span-2">
          <Button type="submit" loading={saving} disabled={kind === "block" && end <= start}>
            {kind === "leave" ? "Add leave" : "Block time"}
          </Button>
        </div>
      </form>

      <div className="flex flex-col gap-3 px-5 pt-4">
        {error && <Callout tone="danger" title={error} />}
        {result && <ReflowSummary reflow={result} />}
      </div>

      <div className="mt-5 border-t border-line px-5 py-4">
        <h3 className="text-[13px] font-medium text-ink-subtle">Upcoming</h3>
        {items === null ? (
          <Skeleton className="mt-3 h-10" />
        ) : items.length === 0 ? (
          <p className="mt-2 text-sm text-ink-muted">No leave or blocked time planned.</p>
        ) : (
          <ul className="mt-2 divide-y divide-line">
            {items.map((item) => (
              <li key={item.id} className="flex items-center justify-between gap-4 py-2.5">
                <div className="text-sm">
                  <span className="font-medium text-ink">{formatDay(item.day)}</span>
                  <span className="ml-2 text-ink-muted">
                    {item.kind === "leave"
                      ? "Leave"
                      : formatRange(item.start_minute, item.end_minute)}
                    {item.reason ? ` · ${item.reason}` : ""}
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  loading={removing === item.id}
                  onClick={() => void remove(item)}
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
