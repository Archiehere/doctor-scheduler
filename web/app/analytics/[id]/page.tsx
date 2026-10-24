import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { BlockHeatmap } from "@/components/analytics/block-heatmap";
import { KpiRow } from "@/components/analytics/kpi-row";
import { MatchBar } from "@/components/analytics/match-bar";
import { parsePeriod, PeriodPicker } from "@/components/analytics/period";
import { UtilizationChart } from "@/components/analytics/utilization-chart";
import { buttonClass } from "@/components/ui/button";
import { Callout, Card, CardHeader, EmptyState, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { formatDay, minutesLabel, percent } from "@/lib/format";

export const metadata: Metadata = { title: "Doctor analytics" };

const TARGET = 0.8;

export default function DoctorAnalyticsPage({
  params,
  searchParams,
}: PageProps<"/analytics/[id]">) {
  return (
    <Suspense fallback={<DetailSkeleton />}>
      <Detail params={params} searchParams={searchParams} />
    </Suspense>
  );
}

async function Detail({ params, searchParams }: PageProps<"/analytics/[id]">) {
  const { id } = await params;
  const period = parsePeriod((await searchParams).days);
  let data;
  try {
    data = await api.doctorAnalytics(Number(id), period);
  } catch (e) {
    return (
      <EmptyState
        title={
          e instanceof ApiError && e.status === 404 ? "Doctor not found" : "Can't load analytics"
        }
        description={e instanceof ApiError ? e.message : undefined}
        action={
          <Link href="/analytics" className={buttonClass("secondary")}>
            Back to analytics
          </Link>
        }
      />
    );
  }
  const k = data.kpis;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <Link
            href={`/analytics?days=${period}`}
            className="text-[13px] text-ink-muted hover:text-ink"
          >
            ← All doctors
          </Link>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">{k.doctor.name}</h1>
          <p className="text-sm text-ink-muted">
            {k.doctor.specialty} · {formatDay(data.start, "short")} – {formatDay(data.end, "short")}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link href={`/doctor/${k.doctor.id}`} className={buttonClass("secondary", "sm")}>
            Open schedule
          </Link>
          <PeriodPicker value={period} basePath={`/analytics/${k.doctor.id}`} />
        </div>
      </div>

      <KpiRow kpis={k} target={TARGET} />

      {data.hints.length > 0 && (
        <Callout tone="accent" title="Capacity suggestions">
          <ul className="mt-1 list-disc pl-4">
            {data.hints.map((h) => (
              <li key={h}>{h}</li>
            ))}
          </ul>
        </Callout>
      )}

      <Card>
        <CardHeader title="Share of open time booked, by day" />
        <div className="px-2 pt-4 pb-3 sm:px-4">
          <UtilizationChart daily={data.daily} target={TARGET} />
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Card className="pb-5">
          <CardHeader
            title="When the time gets booked"
            description="Share of open hours booked by weekday and part of day."
          />
          <div className="px-5 pt-4">
            <BlockHeatmap blocks={data.blocks} />
          </div>
        </Card>

        <div className="flex flex-col gap-6">
          <Card className="pb-5">
            <CardHeader
              title="Patient preference"
              description="Where calls landed compared to what the patient asked for."
            />
            <div className="px-5 pt-4">
              <MatchBar
                preferred={k.preferred_rate}
                inRange={k.in_range_rate}
                outside={k.outside_rate}
              />
            </div>
          </Card>

          <Card className="pb-5">
            <CardHeader title="Calls" />
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4 px-5 pt-4 text-sm">
              <Fact label="Completed" value={k.calls_completed} />
              <Fact label="No-shows" value={`${k.no_shows} (${percent(k.no_show_rate, 1)})`} />
              <Fact
                label="Average length"
                value={minutesLabel(k.avg_actual_minutes)}
                detail={`${minutesLabel(k.avg_scheduled_minutes)} scheduled`}
              />
              <Fact label="Ran over by 5+ min" value={percent(k.overrun_rate)} />
              <Fact label="Filled from waitlist" value={k.waitlist_fills} />
              <Fact label="Moved by leave changes" value={k.reassigned} />
              <Fact label="Leave taken" value={`${k.leave_hours} h`} />
              <Fact label="Deposits kept" value={k.deposits_forfeited} />
            </dl>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Fact({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail?: string;
}) {
  return (
    <div>
      <dt className="text-[13px] text-ink-muted">{label}</dt>
      <dd className="tabular mt-0.5 font-medium text-ink">
        {value}
        {detail && <span className="block text-xs font-normal text-ink-subtle">{detail}</span>}
      </dd>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true">
      <Skeleton className="h-16 w-72" />
      <Skeleton className="h-28" />
      <Skeleton className="h-80" />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Skeleton className="h-64" />
        <Skeleton className="h-64" />
      </div>
    </div>
  );
}
