import type { Metadata } from "next";
import { Suspense } from "react";
import { WaitlistStatusView } from "@/components/booking/waitlist-status";
import { PageHeader, Skeleton } from "@/components/ui/primitives";

export const metadata: Metadata = { title: "Waitlist" };

export default function WaitlistPage({ params }: PageProps<"/waitlist/[code]">) {
  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader eyebrow="Waitlist" title="You're on the waitlist" />
      <Suspense fallback={<Skeleton className="h-48" />}>
        <WaitlistStatusView params={params} />
      </Suspense>
    </div>
  );
}
