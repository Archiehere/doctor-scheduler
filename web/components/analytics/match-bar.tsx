import { percent } from "@/lib/format";

const SEGMENTS = [
  { key: "preferred", label: "At preferred time", color: "var(--color-match-preferred)" },
  { key: "in_range", label: "Elsewhere in window", color: "var(--color-match-range)" },
  { key: "outside", label: "Outside window", color: "var(--color-match-outside)" },
] as const;

/** Part-to-whole bar for where calls landed relative to what the patient asked for. */
export function MatchBar({
  preferred,
  inRange,
  outside,
}: {
  preferred: number | null;
  inRange: number | null;
  outside: number | null;
}) {
  const values = { preferred: preferred ?? 0, in_range: inRange ?? 0, outside: outside ?? 0 };
  return (
    <div>
      <div
        className="flex h-3 w-full gap-0.5 overflow-hidden rounded-sm"
        role="img"
        aria-label={SEGMENTS.map((s) => `${s.label} ${percent(values[s.key])}`).join(", ")}
      >
        {SEGMENTS.map((s) =>
          values[s.key] > 0 ? (
            <div
              key={s.key}
              className="h-full first:rounded-l-sm last:rounded-r-sm"
              style={{ width: `${values[s.key] * 100}%`, background: s.color }}
              title={`${s.label}: ${percent(values[s.key], 1)}`}
            />
          ) : null,
        )}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-[13px]">
        {SEGMENTS.map((s) => (
          <li key={s.key} className="flex items-center gap-2">
            <span
              className="size-2.5 rounded-sm"
              style={{ background: s.color }}
              aria-hidden="true"
            />
            <span className="text-ink-muted">{s.label}</span>
            <span className="tabular font-medium text-ink">{percent(values[s.key])}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
