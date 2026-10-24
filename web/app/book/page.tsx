import type { Metadata } from "next";
import { Suspense } from "react";
import { BookingFlow } from "@/components/booking/booking-flow";
import { PageHeader, Skeleton } from "@/components/ui/primitives";

export const metadata: Metadata = { title: "Book a call" };

export default function BookPage() {
  return (
    <>
      <PageHeader
        title="Book a video call"
        description="Tell us when you're free. We'll show you the best confirmed times straight away."
      />
      {/* The flow depends on today's date, so it renders per request rather than at build. */}
      <Suspense fallback={<FlowSkeleton />}>
        <BookingFlow />
      </Suspense>
    </>
  );
}

function FlowSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]" aria-busy="true">
      <div className="flex flex-col gap-6">
        <Skeleton className="h-36" />
        <Skeleton className="h-44" />
        <Skeleton className="h-72" />
      </div>
      <Skeleton className="h-64" />
    </div>
  );
}
