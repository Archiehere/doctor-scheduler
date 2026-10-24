import type { BookingStatus, OptionLabel, VisitType } from "./types";

export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

/** 870 -> "14:30" */
export function formatMinute(minute: number): string {
  const h = Math.floor(minute / 60);
  const m = minute % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

export function formatRange(start: number, end: number): string {
  return `${formatMinute(start)} – ${formatMinute(end)}`;
}

/** Parse an ISO date (YYYY-MM-DD) as a local calendar date, without timezone drift. */
export function parseDay(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function toIsoDay(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function addDays(iso: string, days: number): string {
  const date = parseDay(iso);
  date.setDate(date.getDate() + days);
  return toIsoDay(date);
}

export function todayIso(): string {
  return toIsoDay(new Date());
}

export function formatDay(iso: string, style: "short" | "long" = "long"): string {
  const date = parseDay(iso);
  return date.toLocaleDateString("en-GB", {
    weekday: style === "long" ? "long" : "short",
    day: "numeric",
    month: style === "long" ? "long" : "short",
  });
}

export function relativeDay(iso: string): string | null {
  const diff = Math.round((parseDay(iso).getTime() - parseDay(todayIso()).getTime()) / 86_400_000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Tomorrow";
  return null;
}

export function percent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function hours(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (value < 1) return `${Math.round(value * 60)} min`;
  if (value < 48) return `${value.toFixed(value < 10 ? 1 : 0)} h`;
  return `${(value / 24).toFixed(1)} days`;
}

export function minutesLabel(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value)} min`;
}

export function money(minor: number, currency: string): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(minor / 100);
}

export const VISIT_LABEL: Record<VisitType, string> = {
  follow_up: "Follow-up",
  new_consult: "New consultation",
};

export const VISIT_MINUTES: Record<VisitType, number> = {
  follow_up: 30,
  new_consult: 45,
};

export const OPTION_LABEL: Record<OptionLabel, string> = {
  recommended: "Recommended",
  closest_to_preference: "Closest to your time",
  soonest: "Soonest",
  alternative: "Alternative",
};

export const STATUS_LABEL: Record<BookingStatus, string> = {
  held: "Held",
  confirmed: "Confirmed",
  in_progress: "In progress",
  completed: "Completed",
  no_show: "No-show",
  cancelled: "Cancelled",
  needs_reschedule: "Needs a new time",
};

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
export const WEEKDAYS_LONG = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

/** Times on a 15-minute grid between start and end (inclusive). */
export function timeSteps(start: number, end: number, step = 15): number[] {
  const out: number[] = [];
  for (let m = start; m <= end; m += step) out.push(m);
  return out;
}
