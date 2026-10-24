"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { DayPicker } from "@/components/booking/day-picker";
import { OptionCard } from "@/components/booking/option-card";
import { RangePicker } from "@/components/booking/range-picker";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Checkbox, Field, Input, Segmented } from "@/components/ui/form";
import { Callout, Card, EmptyState } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import {
  formatDay,
  formatMinute,
  formatRange,
  money,
  todayIso,
  VISIT_LABEL,
  VISIT_MINUTES,
} from "@/lib/format";
import type {
  Booking,
  CalendarDay,
  DemandProfile,
  OptionsResponse,
  SlotOption,
  TimeRange,
  VisitType,
} from "@/lib/types";

interface FormState {
  visitType: VisitType;
  day: string;
  flexibleDay: boolean;
  ranges: TimeRange[];
  preferred: number | null;
  name: string;
  email: string;
  phone: string;
}

const optionKey = (o: SlotOption) => `${o.doctor.id}-${o.day}-${o.start_minute}`;

export function BookingFlow() {
  const router = useRouter();
  const [today] = useState(todayIso);
  const [form, setForm] = useState<FormState>({
    visitType: "follow_up",
    day: today,
    flexibleDay: false,
    ranges: [{ start: 12 * 60, end: 17 * 60 }],
    preferred: 15 * 60,
    name: "",
    email: "",
    phone: "",
  });
  const [demand, setDemand] = useState<DemandProfile | null>(null);
  const [availability, setAvailability] = useState<Map<string, CalendarDay>>();
  const dayTouched = useRef(false);
  const [result, setResult] = useState<OptionsResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [choosing, setChoosing] = useState<string | null>(null);
  const [held, setHeld] = useState<Booking | null>(null);
  const [joiningWaitlist, setJoiningWaitlist] = useState(false);

  const duration = VISIT_MINUTES[form.visitType];
  // The clinic's calendar starts on the clinic's today, which can differ from the browser's.
  const clinicToday = availability?.keys().next().value ?? today;
  const update = (patch: Partial<FormState>) => setForm((f) => ({ ...f, ...patch }));

  // Start on the first day that still has room, unless the patient already picked one.
  useEffect(() => {
    let cancelled = false;
    api
      .calendar()
      .then((days) => {
        if (cancelled) return;
        setAvailability(new Map(days.map((d) => [d.day, d])));
        const first = days.find((d) => d.bookable_minutes >= VISIT_MINUTES.follow_up);
        if (first && !dayTouched.current) setForm((f) => ({ ...f, day: first.day }));
      })
      .catch(() => undefined); // the picker still works without availability hints
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    api
      .demand(form.day)
      .then((d) => !cancelled && setDemand(d))
      .catch(() => !cancelled && setDemand(null));
    return () => {
      cancelled = true;
    };
  }, [form.day]);

  const formError = (() => {
    if (!form.ranges.some((r) => r.end - r.start >= duration))
      return `Add a window of at least ${duration} minutes.`;
    if (form.preferred === null) return "Choose a preferred time.";
    if (!form.name.trim()) return "Enter your name.";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email)) return "Enter a valid email address.";
    return null;
  })();

  async function findTimes() {
    if (formError) {
      setError(formError);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const data = await api.requestOptions({
        name: form.name.trim(),
        email: form.email.trim(),
        phone: form.phone.trim() || undefined,
        visit_type: form.visitType,
        day: form.day,
        search_ahead_days: form.flexibleDay ? 2 : 0,
        ranges: form.ranges,
        preferred_minute: form.preferred!,
      });
      setResult(data);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  async function choose(option: SlotOption) {
    if (!result) return;
    setChoosing(optionKey(option));
    setError(null);
    try {
      const booking = await api.hold({
        request_id: result.request_id,
        doctor_id: option.doctor.id,
        day: option.day,
        start_minute: option.start_minute,
      });
      if (booking.deposit_status === "pending") {
        setHeld(booking);
      } else {
        await confirm(booking, false);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't hold that time.");
      if (e instanceof ApiError && e.code === "slot_unavailable") await refreshOptions();
    } finally {
      setChoosing(null);
    }
  }

  async function confirm(booking: Booking, depositPaid: boolean) {
    const confirmed = await api.confirm(booking.code, depositPaid);
    router.push(`/booking/${confirmed.code}?new=1`);
  }

  async function refreshOptions() {
    try {
      setResult(
        await api.requestOptions({
          name: form.name.trim(),
          email: form.email.trim(),
          visit_type: form.visitType,
          day: form.day,
          search_ahead_days: form.flexibleDay ? 2 : 0,
          ranges: form.ranges,
          preferred_minute: form.preferred!,
        }),
      );
    } catch {
      /* keep the existing options on screen */
    }
  }

  async function joinWaitlist() {
    if (!result) return;
    setJoiningWaitlist(true);
    try {
      const entry = await api.joinWaitlist(result.request_id, result.policy.tier !== "none");
      router.push(`/waitlist/${entry.code}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't join the waitlist.");
      setJoiningWaitlist(false);
    }
  }

  if (result) {
    return (
      <OptionsStep
        result={result}
        form={form}
        error={error}
        choosing={choosing}
        joiningWaitlist={joiningWaitlist}
        onBack={() => {
          setResult(null);
          setError(null);
        }}
        onChoose={choose}
        onJoinWaitlist={joinWaitlist}
        deposit={
          <DepositDialog
            booking={held}
            onCancel={() => setHeld(null)}
            onPay={async () => {
              if (!held) return;
              try {
                await confirm(held, true);
              } catch (e) {
                setHeld(null);
                setError(e instanceof ApiError ? e.message : "Couldn't confirm.");
              }
            }}
          />
        }
      />
    );
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <form
        className="flex flex-col gap-6"
        onSubmit={(e) => {
          e.preventDefault();
          void findTimes();
        }}
        noValidate
      >
        <Section number={1} title="Type of visit">
          <Segmented
            label="Type of visit"
            value={form.visitType}
            onChange={(visitType) => update({ visitType })}
            options={[
              { value: "follow_up", label: "Follow-up", description: "30 minutes" },
              { value: "new_consult", label: "New consultation", description: "45 minutes" },
            ]}
          />
        </Section>

        <Section number={2} title="Day">
          <DayPicker
            value={form.day}
            onChange={(day) => {
              dayTouched.current = true;
              update({ day });
            }}
            from={clinicToday}
            availability={availability}
            minMinutes={duration}
          />
          <div className="mt-4">
            <Checkbox
              checked={form.flexibleDay}
              onChange={(flexibleDay) => update({ flexibleDay })}
            >
              I&apos;m flexible on the day
              <span className="block text-xs text-ink-muted">
                Also look at the two days after, if that gets you a better time.
              </span>
            </Checkbox>
          </div>
        </Section>

        <Section
          number={3}
          title="When are you free?"
          description="A wider window gets you a time faster. Quieter hours never need a deposit."
        >
          <RangePicker
            ranges={form.ranges}
            preferred={form.preferred}
            duration={duration}
            demand={demand}
            onChange={(ranges, preferred) => update({ ranges, preferred })}
          />
        </Section>

        <Section number={4} title="Your details">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Full name">
              {(id) => (
                <Input
                  id={id}
                  autoComplete="name"
                  value={form.name}
                  onChange={(e) => update({ name: e.target.value })}
                />
              )}
            </Field>
            <Field label="Email" hint="Your booking reference is tied to this email.">
              {(id) => (
                <Input
                  id={id}
                  type="email"
                  autoComplete="email"
                  value={form.email}
                  onChange={(e) => update({ email: e.target.value })}
                />
              )}
            </Field>
            <Field label="Phone" hint="Optional">
              {(id) => (
                <Input
                  id={id}
                  type="tel"
                  autoComplete="tel"
                  value={form.phone}
                  onChange={(e) => update({ phone: e.target.value })}
                />
              )}
            </Field>
          </div>
        </Section>

        {error && <Callout tone="danger" title={error} />}

        <div className="flex items-center justify-end gap-3">
          <Button type="submit" size="lg" loading={submitting}>
            Find times
          </Button>
        </div>
      </form>

      <aside className="lg:sticky lg:top-20 lg:self-start">
        <Card className="p-5">
          <h2 className="text-[13px] font-medium text-ink-subtle">Your request</h2>
          <dl className="mt-3 flex flex-col gap-3 text-sm">
            <SummaryRow label="Visit">
              {VISIT_LABEL[form.visitType]} · {duration} min
            </SummaryRow>
            <SummaryRow label="Day">
              {formatDay(form.day)}
              {form.flexibleDay && <span className="text-ink-muted"> (or 2 days after)</span>}
            </SummaryRow>
            <SummaryRow label="Free">
              {form.ranges.length
                ? form.ranges.map((r) => formatRange(r.start, r.end)).join(", ")
                : "—"}
            </SummaryRow>
            <SummaryRow label="Prefer">
              {form.preferred !== null ? formatMinute(form.preferred) : "—"}
            </SummaryRow>
          </dl>
          <p className="mt-5 border-t border-line pt-4 text-xs leading-relaxed text-ink-muted">
            We look at every free slot in your window and suggest the one that fits best, alongside
            the closest to your preferred time and the soonest. Nothing is booked until you pick
            one.
          </p>
        </Card>
      </aside>
    </div>
  );
}

function Section({
  number,
  title,
  description,
  children,
}: {
  number: number;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <Card className="p-5 sm:p-6">
      <div className="mb-4 flex gap-3">
        <span className="tabular flex size-6 shrink-0 items-center justify-center rounded-full bg-sunken text-xs font-semibold text-ink-muted">
          {number}
        </span>
        <div>
          <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
          {description && <p className="mt-0.5 text-sm text-ink-muted">{description}</p>}
        </div>
      </div>
      {children}
    </Card>
  );
}

function SummaryRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[64px_1fr] gap-2">
      <dt className="text-ink-subtle">{label}</dt>
      <dd className="tabular text-ink">{children}</dd>
    </div>
  );
}

function OptionsStep({
  result,
  form,
  error,
  choosing,
  joiningWaitlist,
  onBack,
  onChoose,
  onJoinWaitlist,
  deposit,
}: {
  result: OptionsResponse;
  form: FormState;
  error: string | null;
  choosing: string | null;
  joiningWaitlist: boolean;
  onBack: () => void;
  onChoose: (option: SlotOption) => void;
  onJoinWaitlist: () => void;
  deposit: ReactNode;
}) {
  const { policy } = result;
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <button
            type="button"
            onClick={onBack}
            className="mb-2 text-[13px] text-ink-muted hover:text-ink"
          >
            ← Edit request
          </button>
          <h1 className="text-2xl font-semibold tracking-tight">Choose a time</h1>
          <p className="mt-1 text-sm text-ink-muted">
            {VISIT_LABEL[form.visitType]} on {formatDay(form.day)}
            {form.flexibleDay && " or the two days after"}, free{" "}
            {form.ranges.map((r) => formatRange(r.start, r.end)).join(", ")}.
          </p>
        </div>
      </div>

      {policy.tier !== "none" && (
        <Callout tone="warn" title={TIER_COPY[policy.tier].title}>
          {TIER_COPY[policy.tier].body(money(policy.deposit_amount, policy.currency))}
        </Callout>
      )}

      {!result.in_range && result.options.length > 0 && (
        <Callout
          tone="warn"
          title="Nothing is free inside your window"
          action={
            <Button
              variant="secondary"
              size="sm"
              onClick={onJoinWaitlist}
              loading={joiningWaitlist}
            >
              Join the waitlist instead
            </Button>
          }
        >
          These are the nearest times we have. Or join the waitlist and we&apos;ll book you
          automatically if a slot opens inside your window.
        </Callout>
      )}

      {error && <Callout tone="danger" title={error} />}

      {result.options.length === 0 ? (
        <EmptyState
          title="No times available"
          description="Every doctor is fully booked around your window. Join the waitlist and we'll book you automatically as soon as a slot opens."
          action={
            <div className="flex gap-2">
              <Button onClick={onJoinWaitlist} loading={joiningWaitlist}>
                Join the waitlist
              </Button>
              <Button variant="secondary" onClick={onBack}>
                Try another day
              </Button>
            </div>
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          {result.options.map((option, i) => (
            <OptionCard
              key={optionKey(option)}
              option={option}
              policy={policy}
              featured={i === 0}
              loading={choosing === optionKey(option)}
              disabled={choosing !== null}
              onChoose={() => onChoose(option)}
            />
          ))}
        </div>
      )}

      {result.in_range && result.options.length > 0 && (
        <p className="text-[13px] text-ink-muted">
          None of these work?{" "}
          <button
            type="button"
            onClick={onJoinWaitlist}
            className="font-medium text-accent hover:text-accent-strong"
          >
            Join the waitlist
          </button>{" "}
          for an earlier time, or{" "}
          <button
            type="button"
            onClick={onBack}
            className="font-medium text-accent hover:text-accent-strong"
          >
            widen your window
          </button>
          .
        </p>
      )}
      {deposit}
    </div>
  );
}

const TIER_COPY = {
  peak_only: {
    title: "A deposit applies to busy hours",
    body: (amount: string) =>
      `Because of a recent missed call, busy-hour slots need a refundable ${amount} deposit. Quieter hours don't.`,
  },
  all: {
    title: "A refundable deposit is needed",
    body: (amount: string) =>
      `After missed calls in the last 90 days, bookings need a ${amount} deposit. It's returned once your call happens.`,
  },
  restricted: {
    title: "Only same-day quieter slots are available",
    body: (amount: string) =>
      `After several missed calls you can book same-day slots in quieter hours, with a ${amount} deposit.`,
  },
} as const;

function DepositDialog({
  booking,
  onCancel,
  onPay,
}: {
  booking: Booking | null;
  onCancel: () => void;
  onPay: () => Promise<void>;
}) {
  const [paying, setPaying] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(0);

  useEffect(() => {
    if (!booking) return;
    const deadline = Date.now() + 5 * 60_000;
    const tick = () => setSecondsLeft(Math.max(0, Math.round((deadline - Date.now()) / 1000)));
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [booking]);

  if (!booking) return null;
  const amount = money(booking.deposit_amount, booking.currency);
  return (
    <Dialog
      open
      onClose={onCancel}
      title={`Confirm with a ${amount} deposit`}
      description={
        <>
          We&apos;re holding {formatMinute(booking.start_minute)} on {formatDay(booking.day)} with{" "}
          {booking.doctor.name} for{" "}
          <span className="tabular font-medium text-ink">
            {Math.floor(secondsLeft / 60)}:{String(secondsLeft % 60).padStart(2, "0")}
          </span>
          .
        </>
      }
      footer={
        <>
          <Button variant="ghost" onClick={onCancel}>
            Back
          </Button>
          <Button
            loading={paying}
            disabled={secondsLeft === 0}
            onClick={async () => {
              setPaying(true);
              await onPay();
              setPaying(false);
            }}
          >
            Pay {amount} and confirm
          </Button>
        </>
      }
    >
      <ul className="flex flex-col gap-2 rounded-md bg-sunken p-4 text-[13px] text-ink-muted">
        <li>Refunded in full after your call.</li>
        <li>Refunded if you cancel more than 2 hours before.</li>
        <li>Kept if you miss the call or cancel later than that.</li>
      </ul>
      <p className="mt-3 text-xs text-ink-subtle">This is a demo. No payment is taken.</p>
    </Dialog>
  );
}
