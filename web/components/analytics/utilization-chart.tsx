"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from "recharts";
import { formatDay, parseDay, percent } from "@/lib/format";
import type { DailyPoint } from "@/lib/types";

interface Row {
  day: string;
  utilization: number | null;
  booked: number;
  open: number;
}

/** Daily share of open time booked, one series, with the target as a reference line. */
export function UtilizationChart({ daily, target }: { daily: DailyPoint[]; target: number }) {
  const rows: Row[] = daily.map((d) => ({
    day: d.day,
    utilization: d.utilization,
    booked: d.booked_minutes,
    open: d.open_minutes,
  }));
  const tickEvery = Math.max(1, Math.ceil(rows.length / 8));

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer>
        <LineChart data={rows} margin={{ top: 12, right: 76, bottom: 0, left: -12 }}>
          <CartesianGrid vertical={false} stroke="var(--color-line)" />
          <XAxis
            dataKey="day"
            tickLine={false}
            axisLine={{ stroke: "var(--color-line-strong)" }}
            interval={tickEvery - 1}
            tick={{ fill: "var(--color-ink-subtle)", fontSize: 11 }}
            tickFormatter={(d: string) =>
              parseDay(d).toLocaleDateString("en-GB", { day: "numeric", month: "short" })
            }
          />
          <YAxis
            domain={[0, 1]}
            ticks={[0, 0.25, 0.5, 0.75, 1]}
            tickLine={false}
            axisLine={false}
            tick={{ fill: "var(--color-ink-subtle)", fontSize: 11 }}
            tickFormatter={(v: number) => percent(v)}
          />
          <ReferenceLine
            y={target}
            stroke="var(--color-ink)"
            strokeDasharray="4 4"
            strokeWidth={1}
            label={{
              value: `Target ${percent(target)}`,
              position: "right",
              fill: "var(--color-ink-muted)",
              fontSize: 11,
            }}
          />
          <Tooltip
            cursor={{ stroke: "var(--color-line-strong)", strokeWidth: 1 }}
            content={(props) => <ChartTooltip {...props} />}
          />
          <Line
            type="monotone"
            dataKey="utilization"
            stroke="var(--color-accent)"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, stroke: "var(--color-surface)", strokeWidth: 2 }}
            connectNulls={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function ChartTooltip({ active, payload }: TooltipContentProps) {
  const row = active && payload?.[0] ? (payload[0].payload as Row) : null;
  if (!row) return null;
  return (
    <div className="rounded-md border border-line bg-surface px-3 py-2 text-xs shadow-pop">
      <p className="font-medium text-ink">{formatDay(row.day, "short")}</p>
      {row.open ? (
        <p className="tabular mt-1 text-ink-muted">
          <span className="font-medium text-ink">{percent(row.utilization)}</span> booked ·{" "}
          {(row.booked / 60).toFixed(1)} of {(row.open / 60).toFixed(1)} h
        </p>
      ) : (
        <p className="mt-1 text-ink-muted">No open hours</p>
      )}
    </div>
  );
}
