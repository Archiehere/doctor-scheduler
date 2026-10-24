import type {
  AnalyticsOverview,
  Booking,
  BookingRequestBody,
  DemandProfile,
  DoctorAnalytics,
  DoctorListItem,
  OptionsResponse,
  Reflow,
  Schedule,
  ScheduleBooking,
  TimeOff,
  TimeOffKind,
  WaitlistEntry,
  WorkingHoursItem,
} from "./types";

// Browser calls use the public URL; server components may use an internal one.
const BASE_URL =
  (typeof window === "undefined" ? process.env.API_URL : undefined) ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "network", "Can't reach the scheduling service. Is the API running?");
  }

  if (response.status === 204) return undefined as T;
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw toApiError(response.status, body);
  }
  return body as T;
}

function toApiError(status: number, body: unknown): ApiError {
  if (body && typeof body === "object") {
    if ("error" in body) {
      const err = (body as { error: { code: string; message: string } }).error;
      return new ApiError(status, err.code, err.message);
    }
    if ("detail" in body && Array.isArray((body as { detail: unknown }).detail)) {
      const first = (body as { detail: { msg: string }[] }).detail[0];
      return new ApiError(status, "validation", first?.msg ?? "Please check the form.");
    }
  }
  return new ApiError(status, "unknown", "Something went wrong. Please try again.");
}

const json = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

export const api = {
  baseUrl: BASE_URL,

  // Patients
  requestOptions: (body: BookingRequestBody) =>
    request<OptionsResponse>("/booking-requests", json(body)),
  hold: (body: { request_id: number; doctor_id: number; day: string; start_minute: number }) =>
    request<Booking>("/bookings", json(body)),
  confirm: (code: string, depositPaid: boolean) =>
    request<Booking>(`/bookings/${code}/confirm`, json({ deposit_paid: depositPaid })),
  booking: (code: string) => request<Booking>(`/bookings/${encodeURIComponent(code)}`),
  cancel: (code: string) => request<Booking>(`/bookings/${code}/cancel`, { method: "POST" }),
  rescheduleOptions: (code: string) =>
    request<OptionsResponse>(`/bookings/${code}/reschedule-options`),
  reschedule: (code: string, body: { doctor_id: number; day: string; start_minute: number }) =>
    request<Booking>(`/bookings/${code}/reschedule`, json(body)),
  calendarUrl: (code: string) => `${BASE_URL}/bookings/${code}/calendar.ics`,
  joinWaitlist: (requestId: number, depositAcknowledged: boolean) =>
    request<WaitlistEntry>(
      "/waitlist",
      json({ request_id: requestId, deposit_acknowledged: depositAcknowledged }),
    ),
  waitlist: (code: string) => request<WaitlistEntry>(`/waitlist/${encodeURIComponent(code)}`),
  leaveWaitlist: (code: string) =>
    request<WaitlistEntry>(`/waitlist/${code}/leave`, { method: "POST" }),
  demand: (day: string) => request<DemandProfile>(`/demand?day=${day}`),

  // Doctors
  doctors: () => request<DoctorListItem[]>("/doctors"),
  schedule: (doctorId: number, day: string) =>
    request<Schedule>(`/doctors/${doctorId}/schedule?day=${day}`),
  outcome: (bookingId: number, action: "start" | "complete" | "no_show") =>
    request<ScheduleBooking>(`/doctors/bookings/${bookingId}/outcome`, json({ action })),
  hours: (doctorId: number) => request<WorkingHoursItem[]>(`/doctors/${doctorId}/hours`),
  saveHours: (doctorId: number, hours: WorkingHoursItem[]) =>
    request<Reflow>(`/doctors/${doctorId}/hours`, { method: "PUT", body: JSON.stringify(hours) }),
  timeOff: (doctorId: number) => request<TimeOff[]>(`/doctors/${doctorId}/time-off`),
  addTimeOff: (
    doctorId: number,
    body: {
      day: string;
      kind: TimeOffKind;
      start_minute?: number;
      end_minute?: number;
      reason?: string;
    },
  ) => request<{ time_off: TimeOff; reflow: Reflow }>(`/doctors/${doctorId}/time-off`, json(body)),
  removeTimeOff: (doctorId: number, id: number) =>
    request<void>(`/doctors/${doctorId}/time-off/${id}`, { method: "DELETE" }),

  // Analytics
  overview: (days: number) => request<AnalyticsOverview>(`/analytics/overview?days=${days}`),
  doctorAnalytics: (doctorId: number, days: number) =>
    request<DoctorAnalytics>(`/analytics/doctors/${doctorId}?days=${days}`),
};
