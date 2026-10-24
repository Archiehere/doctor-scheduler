import type { Metadata } from "next";
import Link from "next/link";
import { Suspense, type ReactNode } from "react";
import { parsePeriod, PeriodPicker } from "@/components/analytics/period";
import { KpiRow } from "@/components/analytics/kpi-row";
import { UtilizationChart } from "@/components/analytics/utilization-chart";
import {
  Card,
  CardHeader,
  EmptyState,
  Meter,
  PageHeader,
  Skeleton,
} from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { formatDay, hours, percent } from "@/lib/format";
import type { DoctorKpis } from "@/lib/types";

export const metadata: Metadata = { title: "Analytics" };

export default function AnalyticsPage({ searchParams }: PageProps<"/analytics">) {
  return (
    <Suspense fallback={<AnalyticsSkeleton />}>
      <Overview searchParams={searchParams} />
    </Suspense>
  );
}

async function Overview({ searchParams }: Pick<PageProps<"/analytics">, "searchParams">) {
  const period = parsePeriod((await searchParams).days);
  let data;
  try {
    data = await api.overview(period);
  } catch (e) {
    return (
      <EmptyState
        title="Can't load analytics"
        description={e instanceof ApiError ? e.message : "Please try again."}
      />
    );
  }
  const c = data.clinic;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Analytics"
        description={`${formatDay(data.start, "short")} – ${formatDay(data.end, "short")} across ${data.doctors.length} doctors.`}
        action={<PeriodPicker value={period} basePath="/analytics" />}
      />

      <KpiRow kpis={c} target={data.target} />

      <Card>
        <CardHeader
          title="Share of open time booked, by day"
          description="All doctors combined. No-shows count as booked because the slot was used up."
        />
        <div className="px-2 pt-4 pb-3 sm:px-4">
          <UtilizationChart daily={data.daily} target={data.target} />
        </div>
      </Card>

      <Card className="overflow-hidden">
        <CardHeader title="Doctors" description="Select a doctor for the full breakdown." />
        <DoctorTable doctors={data.doctors} target={data.target} />
      </Card>
    </div>
  );
}

function DoctorTable({ doctors, target }: { doctors: DoctorKpis[]; target: number }) {
  return (
    <div className="mt-4 overflow-x-auto">
      <table className="w-full min-w-[820px] text-sm">
        <thead>
          <tr className="border-y border-line bg-sunken/60 text-left text-[12px] text-ink-muted">
            <th scope="col" className="px-5 py-2.5 font-medium">
              Doctor
            </th>
            <th scope="col" className="w-48 px-3 py-2.5 font-medium">
              Time booked
            </th>
            <th scope="col" className="px-3 py-2.5 text-right font-medium">
              Next 7 days
            </th>
            <th scope="col" className="px-3 py-2.5 text-right font-medium">
              No-shows
            </th>
            <th scope="col" className="px-3 py-2.5 text-right font-medium">
              At preferred
            </th>
            <th scope="col" className="px-3 py-2.5 text-right font-medium">
              Median lead
            </th>
            <th scope="col" className="px-3 py-2.5 text-right font-medium">
              Overruns
            </th>
            <th scope="col" className="px-5 py-2.5 text-right font-medium">
              Dead gap / day
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {doctors.map((d) => (
            <tr key={d.doctor.id} className="transition-colors hover:bg-sunken/50">
              <td className="px-5 py-3">
                <Link
                  href={`/analytics/${d.doctor.id}`}
                  className="font-medium text-ink hover:text-accent"
                >
                  {d.doctor.name}
                </Link>
                <span className="block text-[12px] text-ink-muted">{d.doctor.specialty}</span>
              </td>
              <td className="px-3 py-3">
                <div className="flex items-center gap-3">
                  <Meter
                    className="flex-1"
                    value={d.utilization}
                    target={target}
                    label={`${d.doctor.name} time booked`}
                  />
                  <span className="tabular w-10 text-right font-medium">
                    {percent(d.utilization)}
                  </span>
                </div>
              </td>
              <Num>{percent(d.upcoming_utilization)}</Num>
              <Num>{percent(d.no_show_rate, 1)}</Num>
              <Num>{percent(d.preferred_rate)}</Num>
              <Num>{hours(d.median_lead_hours)}</Num>
              <Num>{percent(d.overrun_rate)}</Num>
              <Num last>
                {d.working_days ? `${Math.round(d.dead_gap_minutes / d.working_days)} min` : "—"}
              </Num>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Num({ children, last }: { children: ReactNode; last?: boolean }) {
  return (
    <td className={`tabular py-3 text-right text-ink ${last ? "px-5" : "px-3"}`}>{children}</td>
  );
}

function AnalyticsSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true">
      <Skeleton className="h-14 w-72" />
      <Skeleton className="h-28" />
      <Skeleton className="h-80" />
      <Skeleton className="h-96" />
    </div>
  );
}
