import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { Card, EmptyState, Meter, PageHeader, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { percent } from "@/lib/format";

export const metadata: Metadata = { title: "Doctor portal" };

export default function DoctorsPage() {
  return (
    <>
      <PageHeader
        title="Doctor portal"
        description="Choose a doctor to see their day, record call outcomes and manage availability."
      />
      <Suspense fallback={<DoctorGridSkeleton />}>
        <DoctorGrid />
      </Suspense>
    </>
  );
}

async function DoctorGrid() {
  let doctors;
  try {
    doctors = await api.doctors();
  } catch (e) {
    return (
      <EmptyState
        title="Can't load doctors"
        description={e instanceof ApiError ? e.message : "Please try again."}
      />
    );
  }
  if (doctors.length === 0) {
    return (
      <EmptyState
        title="No doctors yet"
        description="Run the seed script to add doctors and sample history."
      />
    );
  }
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {doctors.map((d) => {
        const t = d.today;
        return (
          <Link key={d.id} href={`/doctor/${d.id}`} className="group">
            <Card className="h-full p-5 transition-colors group-hover:border-accent-line">
              <p className="text-[15px] font-semibold text-ink">{d.name}</p>
              <p className="text-[13px] text-ink-muted">{d.specialty}</p>
              <div className="mt-5 flex items-baseline justify-between text-[13px]">
                <span className="text-ink-muted">Today</span>
                <span className="tabular font-medium text-ink">
                  {t.open_minutes ? `${percent(t.utilization)} booked` : "Not working"}
                </span>
              </div>
              <Meter
                className="mt-2"
                value={t.utilization}
                target={0.8}
                label={`${d.name} booked today`}
              />
              <p className="tabular mt-2 text-xs text-ink-subtle">
                {Math.round((t.booked_minutes / 60) * 10) / 10} of {t.open_minutes / 60} h booked
              </p>
            </Card>
          </Link>
        );
      })}
    </div>
  );
}

function DoctorGridSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }, (_, i) => (
        <Skeleton key={i} className="h-36" />
      ))}
    </div>
  );
}
