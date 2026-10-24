import Link from "next/link";
import { Callout } from "@/components/ui/primitives";
import type { Reflow } from "@/lib/types";

/** Explains what happened to calls affected by an availability change. */
export function ReflowSummary({ reflow }: { reflow: Reflow }) {
  const same = reflow.moved_same_time.length;
  const moved = reflow.moved_new_time.length;
  const flagged = reflow.needs_reschedule;
  if (same + moved + flagged.length === 0) {
    return <Callout tone="ok" title="Saved. No booked calls were affected." />;
  }
  const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;
  return (
    <Callout tone={flagged.length ? "warn" : "ok"} title="Saved. Affected calls were handled:">
      <ul className="mt-1 list-disc pl-4">
        {same > 0 && <li>{plural(same, "call")} moved to another doctor at the same time</li>}
        {moved > 0 && (
          <li>{plural(moved, "call")} moved to another time inside the patient&apos;s window</li>
        )}
        {flagged.length > 0 && (
          <li>
            {plural(flagged.length, "patient")} asked to pick a new time:{" "}
            {flagged.map((code, i) => (
              <span key={code}>
                {i > 0 && ", "}
                <Link href={`/booking/${code}`} className="font-mono text-accent hover:underline">
                  {code}
                </Link>
              </span>
            ))}
          </li>
        )}
      </ul>
    </Callout>
  );
}
