import { percent, WEEKDAYS } from "@/lib/format";
import type { BlockPoint } from "@/lib/types";

const PARTS = [
  { key: "morning", label: "Morning", hint: "before 12:00" },
  { key: "afternoon", label: "Afternoon", hint: "12:00–17:00" },
  { key: "evening", label: "Evening", hint: "after 17:00" },
] as const;

// Sequential single-hue ramp (light -> dark teal) for "share booked", validated
// for monotone lightness and >= 2:1 light-end contrast against the surface.
const RAMP = ["#7fbfb8", "#5eaaa2", "#3f958d", "#2a7f78", "#1a6762", "#0b4f4b"];

function cellColor(u: number) {
  const i = Math.min(RAMP.length - 1, Math.floor(u * RAMP.length));
  return { background: RAMP[i], color: i >= 3 ? "#ffffff" : "var(--color-ink)" };
}

/** Weekday × part-of-day utilisation. Shows where open hours are under- or over-used. */
export function BlockHeatmap({ blocks }: { blocks: BlockPoint[] }) {
  const lookup = new Map(blocks.map((b) => [`${b.weekday}-${b.daypart}`, b]));
  const weekdays = WEEKDAYS.map((label, wd) => ({ label, wd })).filter(({ wd }) =>
    PARTS.some((p) => lookup.has(`${wd}-${p.key}`)),
  );
  const parts = PARTS.filter((p) => weekdays.some(({ wd }) => lookup.has(`${wd}-${p.key}`)));

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[420px] border-separate border-spacing-0.5 text-xs">
          <caption className="sr-only">
            Share of open time booked by weekday and part of day
          </caption>
          <thead>
            <tr>
              <th className="w-24" />
              {weekdays.map(({ label, wd }) => (
                <th key={wd} scope="col" className="pb-1 text-center font-medium text-ink-subtle">
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {parts.map((part) => (
              <tr key={part.key}>
                <th scope="row" className="pr-3 text-left font-normal">
                  <span className="text-ink">{part.label}</span>
                  <span className="block text-[11px] text-ink-subtle">{part.hint}</span>
                </th>
                {weekdays.map(({ wd }) => {
                  const b = lookup.get(`${wd}-${part.key}`);
                  if (!b || b.utilization === null) {
                    return (
                      <td
                        key={wd}
                        className="hatch h-11 rounded-sm bg-sunken text-center text-ink-subtle"
                      >
                        <span className="sr-only">Closed</span>
                      </td>
                    );
                  }
                  return (
                    <td
                      key={wd}
                      className="tabular h-11 rounded-sm text-center font-medium"
                      style={cellColor(b.utilization)}
                      title={`${WEEKDAYS[wd]} ${part.label.toLowerCase()}: ${percent(b.utilization)} booked (${Math.round(b.booked_minutes / 60)} of ${Math.round(b.open_minutes / 60)} h)`}
                    >
                      {percent(b.utilization)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex items-center gap-2 text-[11px] text-ink-subtle" aria-hidden="true">
        <span>0%</span>
        <div className="flex">
          {RAMP.map((c) => (
            <span
              key={c}
              className="h-2 w-6 first:rounded-l-sm last:rounded-r-sm"
              style={{ background: c }}
            />
          ))}
        </div>
        <span>100% booked</span>
        <span className="hatch ml-3 inline-block h-2 w-4 rounded-sm bg-sunken" />
        <span>Closed</span>
      </div>
    </div>
  );
}
