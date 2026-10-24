"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/primitives";
import { cn, formatDay, formatMinute, money, OPTION_LABEL, relativeDay } from "@/lib/format";
import type { Policy, SlotOption } from "@/lib/types";

export function OptionCard({
  option,
  policy,
  featured,
  loading,
  disabled,
  onChoose,
  actionLabel = "Choose this time",
}: {
  option: SlotOption;
  policy: Policy;
  featured: boolean;
  loading: boolean;
  disabled: boolean;
  onChoose: () => void;
  actionLabel?: string;
}) {
  const minutes = option.end_minute - option.start_minute;
  const dayLabel = relativeDay(option.day);
  return (
    <article
      className={cn(
        "flex flex-col rounded-lg border bg-surface p-5 shadow-card",
        featured ? "border-accent ring-1 ring-accent" : "border-line",
      )}
    >
      <div className="flex min-h-6 flex-wrap gap-1.5">
        {option.labels.map((label) => (
          <Badge key={label} tone={label === "recommended" ? "accent" : "neutral"}>
            {OPTION_LABEL[label]}
          </Badge>
        ))}
        {!option.in_range && <Badge tone="warn">Outside your window</Badge>}
      </div>

      <p className="tabular mt-4 text-[32px] leading-none font-semibold tracking-tight text-ink">
        {formatMinute(option.start_minute)}
      </p>
      <p className="tabular mt-1.5 text-sm text-ink-muted">
        until {formatMinute(option.end_minute)} · {minutes} min
      </p>
      <p className="mt-0.5 text-sm text-ink-muted">
        {dayLabel ? `${dayLabel}, ` : ""}
        {formatDay(option.day)}
      </p>

      <div className="mt-4 border-t border-line pt-4">
        <p className="text-sm font-medium text-ink">{option.doctor.name}</p>
        <p className="text-[13px] text-ink-muted">{option.doctor.specialty}</p>
      </div>

      <ul className="mt-4 flex flex-col gap-1.5 text-[13px] text-ink-muted">
        <li className="flex items-center gap-2">
          <Dot className={option.peak ? "bg-warn" : "bg-ok"} />
          {option.peak ? "Busy hour" : "Quieter hour"}
        </li>
        <li className="flex items-center gap-2">
          <Dot className={option.deposit_required ? "bg-warn" : "bg-ok"} />
          {option.deposit_required
            ? `${money(policy.deposit_amount, policy.currency)} refundable deposit`
            : "No deposit needed"}
        </li>
      </ul>

      <Button
        className="mt-5 w-full"
        variant={featured ? "primary" : "secondary"}
        onClick={onChoose}
        loading={loading}
        disabled={disabled}
      >
        {actionLabel}
      </Button>
    </article>
  );
}

function Dot({ className }: { className: string }) {
  return <span className={cn("size-1.5 shrink-0 rounded-full", className)} aria-hidden="true" />;
}
