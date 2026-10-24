import type { Metadata } from "next";
import { Suspense } from "react";
import { DoctorPortal } from "@/components/doctor/doctor-portal";
import { Skeleton } from "@/components/ui/primitives";

export const metadata: Metadata = { title: "Doctor portal" };

export default function DoctorPage({ params, searchParams }: PageProps<"/doctor/[id]">) {
  return (
    <Suspense fallback={<Skeleton className="h-[720px]" />}>
      <DoctorPortal params={params} searchParams={searchParams} />
    </Suspense>
  );
}
