"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/primitives";
import { cn, formatMinute, formatRange, STATUS_LABEL, VISIT_LABEL } from "@/lib/format";
import type { Schedule, ScheduleBooking } from "@/lib/types";

const PX_PER_MIN = 1.3;

const STATUS_STYLE: Record<ScheduleBooking["status"], string> = {
  held: "border-dashed border-line-strong bg-surface",
  confirmed: "border-accent-line bg-accent-soft",
  in_progress: "border-accent bg-accent-soft ring-1 ring-accent",
  completed: "border-[#c6e2cf] bg-ok-soft",
  no_show: "border-[#efc6c1] bg-danger-soft",
  cancelled: "border-line bg-sunken",
  needs_reschedule: "border-[#efd9a8] bg-warn-soft",
};

export function DayTimeline({
  schedule,
  nowMinute,
  busyId,
  onAction,
}: {
  schedule: Schedule;
  nowMinute: number | null;
  busyId: number | null;
  onAction: (booking: ScheduleBooking, action: "start" | "complete" | "no_show") => void;
}) {
  const points = [
    ...schedule.open.flatMap((r) => [r.start, r.end]),
    ...schedule.bookings.flatMap((b) => [b.start_minute, b.end_minute]),
  ];
  const start = Math.max(0, Math.floor((Math.min(8 * 60, ...points) - 30) / 60) * 60);
  const end = Math.min(24 * 60, Math.ceil((Math.max(18 * 60, ...points) + 30) / 60) * 60);
  const y = (minute: number) => (minute - start) * PX_PER_MIN;
  const hourMarks = Array.from({ length: (end - start) / 60 + 1 }, (_, i) => start + i * 60);

  return (
    <div className="flex" role="region" aria-label="Day schedule">
      <div className="relative w-14 shrink-0" style={{ height: y(end) }} aria-hidden="true">
        {hourMarks.map((m) => (
          <span
            key={m}
            className="tabular absolute right-3 -translate-y-1/2 text-[11px] text-ink-subtle"
            style={{ top: y(m) }}
          >
            {formatMinute(m)}
          </span>
        ))}
      </div>
      <div
        className="hatch relative flex-1 rounded-md border border-line bg-sunken/60"
        style={{ height: y(end) }}
      >
        {hourMarks.slice(1, -1).map((m) => (
          <div
            key={m}
            className="absolute inset-x-0 h-px bg-line"
            style={{ top: y(m) }}
            aria-hidden="true"
          />
        ))}
        {schedule.open.map((r) => (
          <div
            key={`open-${r.start}`}
            className="absolute inset-x-0 border-y border-line bg-surface"
            style={{ top: y(r.start), height: (r.end - r.start) * PX_PER_MIN }}
            aria-hidden="true"
          />
        ))}
        {schedule.time_off
          .filter((t) => t.kind === "block")
          .map((t) => (
            <div
              key={`off-${t.id}`}
              className="hatch absolute inset-x-0 flex items-start border-y border-[#efd9a8] bg-warn-soft/70 px-3 py-1.5"
              style={{
                top: y(t.start_minute),
                height: (t.end_minute - t.start_minute) * PX_PER_MIN,
              }}
            >
              <span className="text-xs font-medium text-warn">
                Blocked {formatRange(t.start_minute, t.end_minute)}
                {t.reason ? ` · ${t.reason}` : ""}
              </span>
            </div>
          ))}

        {schedule.bookings.map((b) => (
          <BookingBlock
            key={b.id}
            booking={b}
            top={y(b.start_minute)}
            height={(b.end_minute - b.start_minute) * PX_PER_MIN}
            nowMinute={nowMinute}
            busy={busyId === b.id}
            onAction={onAction}
          />
        ))}

        {nowMinute !== null && nowMinute >= start && nowMinute <= end && (
          <div
            className="pointer-events-none absolute inset-x-0 z-10 flex items-center"
            style={{ top: y(nowMinute) }}
            aria-label={`Now, ${formatMinute(nowMinute)}`}
          >
            <span className="-ml-1 size-2 rounded-full bg-danger" />
            <span className="h-px flex-1 bg-danger" />
          </div>
        )}
      </div>
    </div>
  );
}

function BookingBlock({
  booking: b,
  top,
  height,
  nowMinute,
  busy,
  onAction,
}: {
  booking: ScheduleBooking;
  top: number;
  height: number;
  nowMinute: number | null;
  busy: boolean;
  onAction: (booking: ScheduleBooking, action: "start" | "complete" | "no_show") => void;
}) {
  // nowMinute is null for future days and 24:00 for past days.
  const started = nowMinute === null ? false : nowMinute >= b.start_minute;
  return (
    <div
      className={cn(
        "absolute inset-x-1.5 z-[1] flex items-center gap-3 overflow-hidden rounded-md border px-3",
        STATUS_STYLE[b.status],
      )}
      style={{ top: top + 1, height: height - 2 }}
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] leading-tight">
          <span className="tabular font-medium text-ink">
            {formatRange(b.start_minute, b.end_minute)}
          </span>
          <span className="ml-2 text-ink">{b.patient_name}</span>
          <span className="ml-2 hidden text-ink-muted sm:inline">{VISIT_LABEL[b.visit_type]}</span>
        </p>
        {height >= 50 && (
          <div className="mt-1 flex flex-wrap gap-1">
            {b.status !== "confirmed" && <Badge className="h-5">{STATUS_LABEL[b.status]}</Badge>}
            {b.deposit_status === "held" && <Badge className="h-5">Deposit</Badge>}
            {b.source === "waitlist" && <Badge className="h-5">Waitlist</Badge>}
            {b.source === "reassigned" && <Badge className="h-5">Reassigned</Badge>}
          </div>
        )}
      </div>
      <div className="flex shrink-0 gap-1.5">
        {height < 50 && b.status !== "confirmed" && (
          <Badge className="h-5">{STATUS_LABEL[b.status]}</Badge>
        )}
        {b.status === "confirmed" && (
          <>
            <Button size="sm" className="h-7" loading={busy} onClick={() => onAction(b, "start")}>
              Start
            </Button>
            {started && (
              <Button
                size="sm"
                variant="ghost"
                className="h-7"
                disabled={busy}
                onClick={() => onAction(b, "no_show")}
              >
                No-show
              </Button>
            )}
          </>
        )}
        {b.status === "in_progress" && (
          <Button size="sm" className="h-7" loading={busy} onClick={() => onAction(b, "complete")}>
            Complete
          </Button>
        )}
      </div>
    </div>
  );
}
