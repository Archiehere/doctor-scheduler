"use client";

import Link from "next/link";
import { use, useState, type ReactNode } from "react";
import { OptionCard } from "@/components/booking/option-card";
import { Button, buttonClass } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Badge, Callout, Card, EmptyState, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import {
  formatDay,
  formatMinute,
  formatRange,
  money,
  relativeDay,
  STATUS_LABEL,
  VISIT_LABEL,
} from "@/lib/format";
import type { Booking, BookingStatus, OptionsResponse, SlotOption } from "@/lib/types";

const STATUS_TONE: Record<BookingStatus, "neutral" | "accent" | "ok" | "warn" | "danger"> = {
  held: "neutral",
  confirmed: "accent",
  in_progress: "accent",
  completed: "ok",
  no_show: "danger",
  cancelled: "neutral",
  needs_reschedule: "warn",
};

const DEPOSIT_COPY: Record<Booking["deposit_status"], string | null> = {
  none: null,
  pending: "Deposit pending",
  held: "Deposit held, refunded after your call",
  refunded: "Deposit refunded",
  forfeited: "Deposit kept (missed or late-cancelled call)",
};

export function BookingStatusView({
  params,
  searchParams,
}: {
  params: Promise<{ code: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { code } = use(params);
  const isNew = use(searchParams).new === "1";
  const bookingRes = useApi(() => api.booking(code), code);
  const booking = bookingRes.data;
  const error = bookingRes.error;
  const [cancelOpen, setCancelOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [wantsNewTime, setWantsNewTime] = useState(false);
  const [choosing, setChoosing] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // A booking flagged by a leave change shows new times straight away.
  const showOptions = wantsNewTime || booking?.status === "needs_reschedule";
  const optionsRes = useApi(
    () => api.rescheduleOptions(code),
    showOptions && booking ? `${code}-${booking.status}` : null,
  );
  const options: OptionsResponse | undefined = optionsRes.data;

  if (error) {
    return (
      <EmptyState
        title={error.status === 404 ? "We couldn't find that booking" : "Something went wrong"}
        description={
          error.status === 404
            ? "Check the reference code from your confirmation and try again."
            : error.message
        }
        action={
          <Link href="/booking" className={buttonClass("secondary")}>
            Look up a booking
          </Link>
        }
      />
    );
  }
  if (!booking) return <BookingSkeleton />;

  const upcoming = booking.status === "confirmed" || booking.status === "needs_reschedule";
  const dayLabel = relativeDay(booking.day);

  async function cancel() {
    setBusy(true);
    try {
      bookingRes.setData(await api.cancel(code));
      setWantsNewTime(false);
      setCancelOpen(false);
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Couldn't cancel.");
    } finally {
      setBusy(false);
    }
  }

  async function reschedule(option: SlotOption) {
    setChoosing(`${option.doctor.id}-${option.day}-${option.start_minute}`);
    setActionError(null);
    try {
      bookingRes.setData(
        await api.reschedule(code, {
          doctor_id: option.doctor.id,
          day: option.day,
          start_minute: option.start_minute,
        }),
      );
      setWantsNewTime(false);
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Couldn't move the call.");
      optionsRes.reload();
    } finally {
      setChoosing(null);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {isNew && booking.status === "confirmed" && (
        <Callout tone="ok" title="You're booked">
          Keep your reference <span className="font-mono font-medium text-ink">{booking.code}</span>{" "}
          to view or change this call.
        </Callout>
      )}
      {booking.notice && (
        <Callout tone={booking.status === "needs_reschedule" ? "warn" : "accent"}>
          {booking.notice}
        </Callout>
      )}
      {actionError && <Callout tone="danger" title={actionError} />}

      <Card className="overflow-hidden">
        <div className="flex flex-col gap-6 p-6 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={STATUS_TONE[booking.status]}>{STATUS_LABEL[booking.status]}</Badge>
              {booking.source === "waitlist" && <Badge>From waitlist</Badge>}
            </div>
            <p className="tabular mt-4 text-[34px] leading-none font-semibold tracking-tight">
              {formatRange(booking.start_minute, booking.end_minute)}
            </p>
            <p className="mt-2 text-[15px] text-ink-muted">
              {dayLabel ? `${dayLabel}, ` : ""}
              {formatDay(booking.day)}
            </p>
          </div>
          <div className="text-left sm:text-right">
            <p className="text-[13px] text-ink-subtle">Reference</p>
            <p className="mt-0.5 font-mono text-lg font-medium tracking-wider">{booking.code}</p>
          </div>
        </div>

        <dl className="grid gap-x-6 gap-y-4 border-t border-line px-6 py-5 text-sm sm:grid-cols-3">
          <Detail label="Doctor">
            {booking.doctor.name}
            <span className="block text-[13px] text-ink-muted">{booking.doctor.specialty}</span>
          </Detail>
          <Detail label="Visit">
            {VISIT_LABEL[booking.visit_type]}
            <span className="block text-[13px] text-ink-muted">
              {booking.end_minute - booking.start_minute} minute video call
            </span>
          </Detail>
          <Detail label="Your availability">
            {booking.ranges.map((r) => formatRange(r.start, r.end)).join(", ")}
            <span className="block text-[13px] text-ink-muted">
              Preferred {formatMinute(booking.preferred_minute)}
            </span>
          </Detail>
          {DEPOSIT_COPY[booking.deposit_status] && (
            <Detail label="Deposit">
              {money(booking.deposit_amount, booking.currency)}
              <span className="block text-[13px] text-ink-muted">
                {DEPOSIT_COPY[booking.deposit_status]}
              </span>
            </Detail>
          )}
        </dl>

        {upcoming && (
          <div className="flex flex-wrap gap-2 border-t border-line bg-sunken/50 px-6 py-4">
            {booking.status === "confirmed" && (
              <a href={api.calendarUrl(booking.code)} className={buttonClass("secondary", "sm")}>
                Add to calendar
              </a>
            )}
            {booking.status === "confirmed" && booking.can_reschedule && !showOptions && (
              <Button variant="secondary" size="sm" onClick={() => setWantsNewTime(true)}>
                Change time
              </Button>
            )}
            {booking.can_cancel && (
              <Button variant="danger" size="sm" onClick={() => setCancelOpen(true)}>
                Cancel call
              </Button>
            )}
          </div>
        )}
      </Card>

      {showOptions && optionsRes.loading && <Skeleton className="h-64" />}
      {optionsRes.error && <Callout tone="danger" title={optionsRes.error.message} />}
      {showOptions && options && (
        <section aria-labelledby="reschedule-heading" className="flex flex-col gap-4">
          <div>
            <h2 id="reschedule-heading" className="text-lg font-semibold">
              {booking.status === "needs_reschedule" ? "Pick a new time" : "Available times"}
            </h2>
            <p className="mt-0.5 text-sm text-ink-muted">
              Based on the window you gave us. Your deposit, if any, carries over.
            </p>
          </div>
          {options.options.length === 0 ? (
            <EmptyState
              title="No times in the next week"
              description="Cancel this call and book again with a wider window."
            />
          ) : (
            <div className="grid gap-4 md:grid-cols-3">
              {options.options.map((option, i) => {
                const key = `${option.doctor.id}-${option.day}-${option.start_minute}`;
                return (
                  <OptionCard
                    key={key}
                    option={option}
                    policy={options.policy}
                    featured={i === 0}
                    loading={choosing === key}
                    disabled={choosing !== null}
                    onChoose={() => void reschedule(option)}
                    actionLabel="Move to this time"
                  />
                );
              })}
            </div>
          )}
        </section>
      )}

      <Dialog
        open={cancelOpen}
        onClose={() => setCancelOpen(false)}
        title="Cancel this call?"
        description={
          booking.cancel_is_late
            ? "This call starts within 2 hours. Cancelling now counts as a late cancellation" +
              (booking.deposit_status === "held" ? " and the deposit is kept." : ".")
            : "The time will be offered to someone on the waitlist." +
              (booking.deposit_status === "held" ? " Your deposit will be refunded." : "")
        }
        footer={
          <>
            <Button variant="ghost" onClick={() => setCancelOpen(false)}>
              Keep call
            </Button>
            <Button variant="danger" loading={busy} onClick={() => void cancel()}>
              Cancel call
            </Button>
          </>
        }
      />
    </div>
  );
}

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-[13px] text-ink-subtle">{label}</dt>
      <dd className="mt-1 text-ink">{children}</dd>
    </div>
  );
}

export function BookingSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading booking">
      <Card className="p-6">
        <Skeleton className="h-6 w-24" />
        <Skeleton className="mt-5 h-9 w-56" />
        <Skeleton className="mt-3 h-4 w-40" />
        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
        </div>
      </Card>
    </div>
  );
}
