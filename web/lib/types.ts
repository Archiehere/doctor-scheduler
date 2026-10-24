// Mirrors api/app/schemas.py. Keep in sync when the API changes.

export type VisitType = "follow_up" | "new_consult";
export type BookingStatus =
  "held" | "confirmed" | "in_progress" | "completed" | "no_show" | "cancelled" | "needs_reschedule";
export type DepositStatus = "none" | "pending" | "held" | "refunded" | "forfeited";
export type PreferenceMatch = "preferred" | "in_range" | "outside";
export type BookingSource = "direct" | "waitlist" | "reassigned";
export type DepositTier = "none" | "peak_only" | "all" | "restricted";
export type OptionLabel = "recommended" | "closest_to_preference" | "soonest" | "alternative";
export type TimeOffKind = "leave" | "block";
export type WaitlistStatus = "waiting" | "filled" | "expired" | "cancelled";

export interface TimeRange {
  start: number;
  end: number;
}

export interface DoctorSummary {
  id: number;
  name: string;
  specialty: string;
}

export interface Score {
  total: number;
  preference: number;
  fragmentation: number;
  demand: number;
  load: number;
  lead_time: number;
  outside_range: number;
}

export interface SlotOption {
  doctor: DoctorSummary;
  day: string;
  start_minute: number;
  end_minute: number;
  labels: OptionLabel[];
  in_range: boolean;
  peak: boolean;
  deposit_required: boolean;
  score: Score;
}

export interface Policy {
  strikes: number;
  tier: DepositTier;
  deposit_amount: number;
  currency: string;
}

export interface OptionsResponse {
  request_id: number;
  in_range: boolean;
  options: SlotOption[];
  policy: Policy;
}

export interface BookingRequestBody {
  name: string;
  email: string;
  phone?: string;
  visit_type: VisitType;
  day: string;
  search_ahead_days: number;
  ranges: TimeRange[];
  preferred_minute: number;
}

export interface Booking {
  code: string;
  status: BookingStatus;
  doctor: DoctorSummary;
  patient_name: string;
  patient_email: string;
  day: string;
  start_minute: number;
  end_minute: number;
  visit_type: VisitType;
  match: PreferenceMatch;
  source: BookingSource;
  deposit_status: DepositStatus;
  deposit_amount: number;
  currency: string;
  hold_expires_at: string | null;
  notice: string | null;
  late_cancel: boolean;
  ranges: TimeRange[];
  preferred_minute: number;
  can_cancel: boolean;
  cancel_is_late: boolean;
  can_reschedule: boolean;
}

export interface WaitlistEntry {
  code: string;
  status: WaitlistStatus;
  days: string[];
  ranges: TimeRange[];
  preferred_minute: number;
  booking_code: string | null;
}

export interface DemandProfile {
  day: string;
  peak_threshold: number;
  points: { minute: number; index: number }[];
}

export interface DayStats {
  open_minutes: number;
  booked_minutes: number;
  utilization: number | null;
  dead_gap_minutes: number;
  bookable_minutes: number;
}

export interface DoctorListItem extends DoctorSummary {
  today: DayStats;
}

export interface TimeOff {
  id: number;
  day: string;
  kind: TimeOffKind;
  start_minute: number;
  end_minute: number;
  reason: string | null;
}

export interface Reflow {
  moved_same_time: string[];
  moved_new_time: string[];
  needs_reschedule: string[];
}

export interface ScheduleBooking {
  id: number;
  code: string;
  patient_name: string;
  start_minute: number;
  end_minute: number;
  visit_type: VisitType;
  status: BookingStatus;
  match: PreferenceMatch;
  source: BookingSource;
  deposit_status: DepositStatus;
  started_at: string | null;
  ended_at: string | null;
}

export interface Schedule {
  doctor: DoctorSummary;
  day: string;
  open: TimeRange[];
  time_off: TimeOff[];
  bookings: ScheduleBooking[];
  stats: DayStats;
}

export interface WorkingHoursItem {
  weekday: number;
  start: number;
  end: number;
}

export interface DoctorKpis {
  doctor: DoctorSummary;
  utilization: number | null;
  realized_utilization: number | null;
  upcoming_utilization: number | null;
  days_at_target: number;
  working_days: number;
  calls_completed: number;
  no_shows: number;
  no_show_rate: number | null;
  late_cancel_rate: number | null;
  preferred_rate: number | null;
  in_range_rate: number | null;
  outside_rate: number | null;
  median_lead_hours: number | null;
  within_24h_rate: number | null;
  avg_scheduled_minutes: number | null;
  avg_actual_minutes: number | null;
  overrun_rate: number | null;
  dead_gap_minutes: number;
  leave_hours: number;
  waitlist_fills: number;
  reassigned: number;
  deposits_forfeited: number;
}

export interface DailyPoint {
  day: string;
  open_minutes: number;
  booked_minutes: number;
  utilization: number | null;
  dead_gap_minutes: number;
}

export interface BlockPoint {
  weekday: number;
  daypart: "morning" | "afternoon" | "evening";
  open_minutes: number;
  booked_minutes: number;
  utilization: number | null;
}

export interface AnalyticsOverview {
  start: string;
  end: string;
  target: number;
  clinic: DoctorKpis;
  daily: DailyPoint[];
  doctors: DoctorKpis[];
}

export interface DoctorAnalytics {
  start: string;
  end: string;
  kpis: DoctorKpis;
  daily: DailyPoint[];
  blocks: BlockPoint[];
  hints: string[];
}
