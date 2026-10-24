import { Card, Meter, Stat } from "@/components/ui/primitives";
import { hours, percent } from "@/lib/format";
import type { DoctorKpis } from "@/lib/types";

export function KpiRow({ kpis: c, target }: { kpis: DoctorKpis; target: number }) {
  return (
    <Card className="grid grid-cols-2 gap-x-6 gap-y-6 p-5 md:grid-cols-3 lg:grid-cols-6">
      <div>
        <Stat
          label="Time booked"
          value={percent(c.utilization)}
          detail={`${percent(c.realized_utilization)} after no-shows`}
        />
        <Meter
          className="mt-3"
          value={c.utilization}
          target={target}
          label="Time booked vs target"
        />
      </div>
      <Stat
        label="Days at target"
        value={`${c.days_at_target}/${c.working_days}`}
        detail={`Doctor-days at ${percent(target)}+ booked`}
      />
      <Stat
        label="No-show rate"
        value={percent(c.no_show_rate, 1)}
        detail={`${percent(c.late_cancel_rate, 1)} late cancellations`}
      />
      <Stat
        label="At preferred time"
        value={percent(c.preferred_rate)}
        detail={`${percent((c.preferred_rate ?? 0) + (c.in_range_rate ?? 0))} inside the window`}
      />
      <Stat
        label="Median lead time"
        value={hours(c.median_lead_hours)}
        detail={`${percent(c.within_24h_rate)} within 24 h`}
      />
      <Stat label="Next 7 days" value={percent(c.upcoming_utilization)} detail="Already booked" />
    </Card>
  );
}
