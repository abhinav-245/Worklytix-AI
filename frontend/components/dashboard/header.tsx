"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Dumbbell, Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Home", exact: true },
  { href: "/overview", label: "Overview" },
  { href: "/pr", label: "PR" },
  { href: "/progression", label: "Progression" },
  { href: "/volume", label: "Volume" },
  { href: "/plateau", label: "Plateau" },
  { href: "/insights", label: "Insights" },
];

const MORE_ITEMS = [
  { href: "/muscles", label: "Muscles" },
  { href: "/exercises", label: "Exercises" },
  { href: "/profile", label: "Profile" },
];

/** Sticky glass header: brand, route nav with gold active state, CTA. */
export function DashboardHeader({
  datasetLoaded,
  statusLine,
}: {
  datasetLoaded: boolean;
  statusLine: string | null;
}) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);

  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname.startsWith(href);
  const moreActive = MORE_ITEMS.some((item) => isActive(item.href));

  const linkClass = (active: boolean) =>
    cn(
      "rounded-md px-3 py-2 text-sm transition-colors",
      "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
      active
        ? "bg-[var(--gold-soft)] text-[var(--gold)]"
        : "text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"
    );

  return (
    <header className="glass sticky top-0 z-50 border-x-0 border-t-0">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/" className="group flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--gold-soft)] bg-[var(--gold-soft)] transition-colors group-hover:border-[var(--gold)]">
            <Dumbbell className="h-5 w-5 text-[var(--gold)]" aria-hidden />
          </span>
          <span className="text-lg font-bold tracking-tight">
            FIT<span className="metric-gold">-</span>INTEL
          </span>
        </Link>
        <nav
          aria-label="Analytics sections"
          className="hidden items-center gap-1 lg:flex"
        >
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive(item.href, item.exact) ? "page" : undefined}
              className={linkClass(isActive(item.href, item.exact))}
            >
              {item.label}
            </Link>
          ))}
          <div
            className="relative"
            onMouseEnter={() => setMoreOpen(true)}
            onMouseLeave={() => setMoreOpen(false)}
          >
            <button
              type="button"
              aria-expanded={moreOpen}
              aria-haspopup="true"
              onClick={() => setMoreOpen((v) => !v)}
              className={linkClass(moreActive)}
            >
              More
            </button>
            {moreOpen ? (
              <div className="glass absolute top-full right-0 mt-1 flex min-w-40 flex-col gap-1 rounded-lg p-2">
                {MORE_ITEMS.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMoreOpen(false)}
                    aria-current={isActive(item.href) ? "page" : undefined}
                    className={linkClass(isActive(item.href))}
                  >
                    {item.label}
                  </Link>
                ))}
              </div>
            ) : null}
          </div>
        </nav>
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "hidden items-center gap-1.5 rounded-full border px-3 py-1 text-xs sm:inline-flex",
              datasetLoaded
                ? "border-[var(--gold-soft)] text-[var(--gold)]"
                : "border-white/10 text-muted-foreground"
            )}
            role="status"
          >
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                datasetLoaded ? "bg-[var(--gold)]" : "bg-muted-foreground"
              )}
              aria-hidden
            />
            {datasetLoaded ? "Dataset loaded" : "No dataset"}
          </span>
          {statusLine ? (
            <span className="hidden max-w-48 truncate text-xs text-muted-foreground xl:inline">
              {statusLine}
            </span>
          ) : null}
          <Link
            href="/#get-started"
            className="rounded-md bg-[var(--gold)] px-3 py-2 text-sm font-medium text-black transition-transform hover:-translate-y-px focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            Get Started
          </Link>
          <button
            type="button"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((v) => !v)}
            className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring lg:hidden"
          >
            {menuOpen ? (
              <X className="h-5 w-5" aria-hidden />
            ) : (
              <Menu className="h-5 w-5" aria-hidden />
            )}
          </button>
        </div>
      </div>
      {menuOpen ? (
        <nav
          aria-label="Analytics sections mobile"
          className="glass border-x-0 border-b-0 lg:hidden"
        >
          <div className="mx-auto flex w-full max-w-6xl flex-col gap-1 px-4 py-3 sm:px-6">
            {[...NAV_ITEMS, ...MORE_ITEMS].map((item) => {
              const exact = "exact" in item && item.exact === true;
              const active = exact
                ? pathname === item.href
                : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMenuOpen(false)}
                  aria-current={active ? "page" : undefined}
                  className={cn(linkClass(active), "block")}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        </nav>
      ) : null}
    </header>
  );
}
