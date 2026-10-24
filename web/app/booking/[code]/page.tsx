import type { Metadata } from "next";
import { Suspense } from "react";
import { BookingSkeleton, BookingStatusView } from "@/components/booking/booking-status";
import { PageHeader } from "@/components/ui/primitives";

export const metadata: Metadata = { title: "Your booking" };

export default function BookingPage({ params, searchParams }: PageProps<"/booking/[code]">) {
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow="Booking" title="Your call" />
      <Suspense fallback={<BookingSkeleton />}>
        <BookingStatusView params={params} searchParams={searchParams} />
      </Suspense>
    </div>
  );
}
