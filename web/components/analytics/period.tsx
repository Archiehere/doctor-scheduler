import Link from "next/link";
import { cn } from "@/lib/format";

export const PERIODS = [7, 28, 90] as const;
export type Period = (typeof PERIODS)[number];

export function parsePeriod(value: string | string[] | undefined): Period {
  const n = Number(Array.isArray(value) ? value[0] : value);
  return (PERIODS as readonly number[]).includes(n) ? (n as Period) : 28;
}

export function PeriodPicker({ value, basePath }: { value: Period; basePath: string }) {
  return (
    <nav aria-label="Period" className="flex rounded-md bg-sunken p-1">
      {PERIODS.map((p) => (
        <Link
          key={p}
          href={`${basePath}?days=${p}`}
          aria-current={p === value ? "page" : undefined}
          className={cn(
            "tabular rounded px-3 py-1.5 text-sm transition-colors",
            p === value
              ? "bg-surface font-medium text-ink shadow-card"
              : "text-ink-muted hover:text-ink",
          )}
        >
          {p} days
        </Link>
      ))}
    </nav>
  );
}
