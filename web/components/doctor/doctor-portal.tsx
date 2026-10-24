"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { DayTimeline } from "@/components/doctor/day-timeline";
import { HoursEditor } from "@/components/doctor/hours-editor";
import { TimeOffPanel } from "@/components/doctor/time-off-panel";
import { Button, buttonClass } from "@/components/ui/button";
import { Callout, Card, EmptyState, Meter, Skeleton, Stat } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { addDays, cn, formatDay, percent, relativeDay, todayIso } from "@/lib/format";
import type { ScheduleBooking } from "@/lib/types";

type Tab = "schedule" | "availability";

function currentMinute(day: string, timestamp: number): number | null {
  const today = todayIso();
  if (day < today) return 24 * 60;
  if (day > today) return null;
  const now = new Date(timestamp);
  return now.getHours() * 60 + now.getMinutes();
}

export function DoctorPortal({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const doctorId = Number(use(params).id);
  const requestedDay = use(searchParams).day;
  const [tab, setTab] = useState<Tab>("schedule");
  const [day, setDay] = useState(() =>
    typeof requestedDay === "string" && /^\d{4}-\d{2}-\d{2}$/.test(requestedDay)
      ? requestedDay
      : todayIso(),
  );
  const scheduleRes = useApi(() => api.schedule(doctorId, day), `${doctorId}-${day}`);
  const schedule = scheduleRes.data ?? null;
  const error = scheduleRes.error;
  const [busyId, setBusyId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [tick, setTick] = useState(() => Date.now());
  const nowMinute = currentMinute(day, tick);

  useEffect(() => {
    const timer = window.setInterval(() => setTick(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  async function act(booking: ScheduleBooking, action: "start" | "complete" | "no_show") {
    setBusyId(booking.id);
    setActionError(null);
    try {
      await api.outcome(booking.id, action);
      scheduleRes.reload();
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Couldn't update the call.");
    } finally {
      setBusyId(null);
    }
  }

  if (error) {
    return (
      <EmptyState
        title={error.status === 404 ? "Doctor not found" : "Can't load the schedule"}
        description={error.message}
        action={
          <Link href="/doctor" className={buttonClass("secondary")}>
            All doctors
          </Link>
        }
      />
    );
  }

  const stats = schedule?.stats;
  const dayLabel = relativeDay(day);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <Link href="/doctor" className="text-[13px] text-ink-muted hover:text-ink">
            ← All doctors
          </Link>
          {schedule ? (
            <>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight">{schedule.doctor.name}</h1>
              <p className="text-sm text-ink-muted">{schedule.doctor.specialty}</p>
            </>
          ) : (
            <>
              <Skeleton className="mt-2 h-8 w-56" />
              <Skeleton className="mt-2 h-4 w-32" />
            </>
          )}
        </div>
        <div role="tablist" aria-label="Portal sections" className="flex rounded-md bg-sunken p-1">
          {(["schedule", "availability"] as const).map((t) => (
            <button
              key={t}
              role="tab"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
              className={cn(
                "rounded px-3.5 py-1.5 text-sm capitalize transition-colors",
                tab === t
                  ? "bg-surface font-medium text-ink shadow-card"
                  : "text-ink-muted hover:text-ink",
              )}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {tab === "availability" ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <TimeOffPanel doctorId={doctorId} onChanged={scheduleRes.reload} />
          <HoursEditor doctorId={doctorId} onChanged={scheduleRes.reload} />
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              aria-label="Previous day"
              onClick={() => setDay((d) => addDays(d, -1))}
            >
              ←
            </Button>
            <Button
              variant="secondary"
              size="sm"
              aria-label="Next day"
              onClick={() => setDay((d) => addDays(d, 1))}
            >
              →
            </Button>
            {day !== todayIso() && (
              <Button variant="ghost" size="sm" onClick={() => setDay(todayIso())}>
                Today
              </Button>
            )}
            <h2 className="ml-2 text-[15px] font-semibold">
              {dayLabel ? `${dayLabel} · ` : ""}
              {formatDay(day)}
            </h2>
          </div>

          <Card className="grid grid-cols-2 gap-6 p-5 md:grid-cols-4">
            <div>
              <Stat
                label="Booked"
                value={stats ? percent(stats.utilization) : "—"}
                detail="Target 80%"
              />
              <Meter
                className="mt-3"
                value={stats?.utilization ?? null}
                target={0.8}
                label="Share of open time booked"
              />
            </div>
            <Stat
              label="Calls"
              value={schedule ? schedule.bookings.length : "—"}
              detail={
                stats
                  ? `${(stats.booked_minutes / 60).toFixed(1)} h of ${(stats.open_minutes / 60).toFixed(1)} h`
                  : undefined
              }
            />
            <Stat
              label="Still bookable"
              value={stats ? `${(stats.bookable_minutes / 60).toFixed(1)} h` : "—"}
              detail="Gaps of 30 min or more"
            />
            <Stat
              label="Dead gaps"
              value={stats ? `${stats.dead_gap_minutes} min` : "—"}
              detail="Free time too short to book"
            />
          </Card>

          {actionError && <Callout tone="danger" title={actionError} />}

          {!schedule ? (
            <Skeleton className="h-[640px]" />
          ) : schedule.open.length === 0 && schedule.bookings.length === 0 ? (
            <EmptyState
              title={schedule.time_off.length ? "On leave" : "Not working this day"}
              description={
                schedule.time_off.length
                  ? (schedule.time_off[0].reason ?? "Leave is booked for this day.")
                  : "No working hours are set for this weekday."
              }
              action={
                <Button variant="secondary" onClick={() => setTab("availability")}>
                  Manage availability
                </Button>
              }
            />
          ) : (
            <Card className="p-4 sm:p-5">
              <DayTimeline
                schedule={schedule}
                nowMinute={nowMinute}
                busyId={busyId}
                onAction={(b, a) => void act(b, a)}
              />
            </Card>
          )}
        </>
      )}
    </div>
  );
}
