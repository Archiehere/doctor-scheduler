import type { Metadata } from "next";
import { LookupForm } from "@/components/booking/lookup-form";
import { PageHeader } from "@/components/ui/primitives";

export const metadata: Metadata = { title: "Find my booking" };

export default function LookupPage() {
  return (
    <div className="mx-auto max-w-md">
      <PageHeader
        title="Find your booking"
        description="Enter the 8-character reference from your confirmation to view, move or cancel your call."
      />
      <LookupForm />
    </div>
  );
}
