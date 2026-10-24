import Link from "next/link";
import { ButtonLink } from "@/components/ui/button";

const ENTRY_POINTS = [
  {
    href: "/book",
    title: "Book a call",
    body: "Tell us when you're free and when you'd prefer. You get three confirmed options right away.",
  },
  {
    href: "/doctor",
    title: "Doctor portal",
    body: "See the day's calls, record outcomes, take leave or block time. Affected calls move automatically.",
  },
  {
    href: "/analytics",
    title: "Analytics",
    body: "Utilisation against the 80% target, no-shows, preference match and lead time for every doctor.",
  },
];

const STEPS = [
  {
    title: "You share a window, not a slot",
    body: "A range like 10:00–17:00 with a preferred time gives the scheduler room to find you a time quickly.",
  },
  {
    title: "Every free slot is scored",
    body: "Closeness to your preferred time, how compact the doctor's day stays, how busy the hour is and how loaded each doctor is.",
  },
  {
    title: "You pick, it's confirmed",
    body: "The slot is held while you confirm. If a doctor later becomes unavailable, we move the call inside your window.",
  },
];

export default function Home() {
  return (
    <div className="flex flex-col gap-14">
      <section className="max-w-2xl pt-4">
        <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-[40px] sm:leading-[1.1]">
          Doctor video calls, scheduled in seconds.
        </h1>
        <p className="mt-4 text-[15px] leading-relaxed text-ink-muted">
          Patients share when they&apos;re available. Rounds instantly places each 30 or 45 minute
          call where it fits best, keeping doctors around 80% booked without pushing everyone into
          the same afternoon hours.
        </p>
        <div className="mt-7 flex flex-wrap gap-3">
          <ButtonLink href="/book" size="lg">
            Book a call
          </ButtonLink>
          <ButtonLink href="/booking" variant="secondary" size="lg">
            Find my booking
          </ButtonLink>
        </div>
      </section>

      <section aria-labelledby="entry-heading">
        <h2 id="entry-heading" className="sr-only">
          Areas
        </h2>
        <div className="grid gap-4 md:grid-cols-3">
          {ENTRY_POINTS.map((entry) => (
            <Link
              key={entry.href}
              href={entry.href}
              className="group rounded-lg border border-line bg-surface p-5 shadow-card transition-colors hover:border-accent-line"
            >
              <div className="flex items-center justify-between">
                <h3 className="text-[15px] font-semibold text-ink">{entry.title}</h3>
                <span
                  className="text-ink-subtle transition-transform group-hover:translate-x-0.5 group-hover:text-accent"
                  aria-hidden="true"
                >
                  →
                </span>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-ink-muted">{entry.body}</p>
            </Link>
          ))}
        </div>
      </section>

      <section aria-labelledby="how-heading" className="border-t border-line pt-10">
        <h2 id="how-heading" className="text-[13px] font-medium text-ink-subtle">
          How scheduling works
        </h2>
        <ol className="mt-5 grid gap-8 md:grid-cols-3">
          {STEPS.map((step, i) => (
            <li key={step.title} className="flex gap-4">
              <span className="tabular flex size-7 shrink-0 items-center justify-center rounded-full border border-line-strong text-[13px] font-medium text-ink-muted">
                {i + 1}
              </span>
              <div>
                <h3 className="text-sm font-semibold text-ink">{step.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
