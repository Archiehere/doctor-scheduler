"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/format";

const NAV = [
  { href: "/book", label: "Book a call" },
  { href: "/booking", label: "My booking" },
  { href: "/doctor", label: "Doctor portal" },
  { href: "/analytics", label: "Analytics" },
];

function isActive(href: string, pathname: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function NavLinks() {
  return <PlainNavLinks pathname={usePathname()} />;
}

export function PlainNavLinks({ pathname }: { pathname?: string }) {
  return NAV.map((item) => {
    const active = pathname !== undefined && isActive(item.href, pathname);
    return (
      <Link
        key={item.href}
        href={item.href}
        aria-current={active ? "page" : undefined}
        className={cn(
          "rounded-md px-2.5 py-1.5 text-sm whitespace-nowrap transition-colors",
          active ? "bg-sunken font-medium text-ink" : "text-ink-muted hover:text-ink",
        )}
      >
        {item.label}
      </Link>
    );
  });
}
