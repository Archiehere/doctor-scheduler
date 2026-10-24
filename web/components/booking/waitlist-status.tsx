"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { Button, buttonClass } from "@/components/ui/button";
import { Badge, Callout, Card, EmptyState, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { formatDay, formatMinute, formatRange } from "@/lib/format";
import type { WaitlistEntry } from "@/lib/types";

const POLL_MS = 15_000;

export function WaitlistStatusView({ params }: { params: Promise<{ code: string }> }) {
  const { code } = use(params);
  const [entry, setEntry] = useState<WaitlistEntry | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    let active = true;
    const load = () =>
      api
        .waitlist(code)
        .then((e) => active && setEntry(e))
        .catch((e) => active && setError(e instanceof ApiError ? e.message : "Couldn't load."));
    void load();
    // No notifications in this MVP, so the page checks back while it's open.
    const timer = window.setInterval(load, POLL_MS);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [code]);

  if (error) return <EmptyState title="Waitlist entry not found" description={error} />;
  if (!entry) return <Skeleton className="h-48" />;

  return (
    <div className="flex flex-col gap-5">
      {entry.status === "filled" && entry.booking_code && (
        <Callout
          tone="ok"
          title="A slot opened up and you're booked"
          action={
            <Link href={`/booking/${entry.booking_code}`} className={buttonClass("primary", "sm")}>
              View booking
            </Link>
          }
        />
      )}
      <Card className="p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <Badge tone={entry.status === "waiting" ? "accent" : "neutral"}>
              {entry.status === "waiting" ? "Waiting for a slot" : entry.status}
            </Badge>
            <p className="mt-4 text-sm text-ink-muted">
              We&apos;ll book you automatically as soon as a doctor is free inside your window. Keep
              this page or your reference to check back.
            </p>
          </div>
          <div className="text-right">
            <p className="text-[13px] text-ink-subtle">Reference</p>
            <p className="font-mono font-medium tracking-wider">{entry.code}</p>
          </div>
        </div>
        <dl className="mt-6 grid gap-4 border-t border-line pt-5 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-[13px] text-ink-subtle">Days</dt>
            <dd className="mt-1">{entry.days.map((d) => formatDay(d, "short")).join(", ")}</dd>
          </div>
          <div>
            <dt className="text-[13px] text-ink-subtle">Window</dt>
            <dd className="tabular mt-1">
              {entry.ranges.map((r) => formatRange(r.start, r.end)).join(", ")}
            </dd>
          </div>
          <div>
            <dt className="text-[13px] text-ink-subtle">Preferred</dt>
            <dd className="tabular mt-1">{formatMinute(entry.preferred_minute)}</dd>
          </div>
        </dl>
        {entry.status === "waiting" && (
          <div className="mt-6 flex justify-end">
            <Button
              variant="ghost"
              size="sm"
              loading={leaving}
              onClick={async () => {
                setLeaving(true);
                setEntry(await api.leaveWaitlist(code));
                setLeaving(false);
              }}
            >
              Leave waitlist
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
