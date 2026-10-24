import Link from "next/link";
import { Suspense } from "react";
import { NavLinks, PlainNavLinks } from "@/components/nav-links";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-surface/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 text-[15px] font-semibold text-ink">
          <Logo />
          Rounds
        </Link>
        <nav aria-label="Main" className="-mx-2 flex min-w-0 flex-1 gap-1 overflow-x-auto">
          {/* The active state depends on the URL, so it streams in; links work without it. */}
          <Suspense fallback={<PlainNavLinks />}>
            <NavLinks />
          </Suspense>
        </nav>
      </div>
    </header>
  );
}

function Logo() {
  return (
    <svg viewBox="0 0 24 24" className="size-6" aria-hidden="true">
      <rect width="24" height="24" rx="6" fill="var(--color-accent)" />
      <circle cx="12" cy="12" r="6" fill="none" stroke="white" strokeWidth="2" />
      <path
        d="M12 8.5V12l2.25 1.5"
        stroke="white"
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  );
}
