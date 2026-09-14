"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Menu, X } from "lucide-react";
import { BrandMark, BrandWordmark } from "@/components/brand";
import { cn } from "@/lib/utils";

const MENU_ITEMS = [
  { href: "/ai-analysis", label: "AI Analysis" },
  { href: "/", label: "Home", exact: true },
  { href: "/overview", label: "Overview" },
  { href: "/pr", label: "PR" },
  { href: "/progression", label: "Progression" },
  { href: "/volume", label: "Volume" },
  { href: "/plateau", label: "Plateau" },
  { href: "/muscles", label: "Muscles" },
  { href: "/exercises", label: "Exercises" },
];

/**
 * Minimal floating Obsidian Glow navbar: brand left, Menu + Try Out
 * right. The pill floats with clear breathing room on both viewport
 * sides. The Menu control opens a glass panel with every section
 * (Profile intentionally absent). One control serves desktop + mobile.
 */
export function DashboardHeader() {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname.startsWith(href);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMenuOpen(false);
        buttonRef.current?.focus();
      }
    };
    const onPointer = (e: PointerEvent) => {
      if (
        panelRef.current &&
        !panelRef.current.contains(e.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [menuOpen]);

  return (
    <header className="sticky top-0 z-50 px-4 pt-3 sm:px-6 sm:pt-4">
      <div className="glass mx-auto flex h-16 w-full max-w-4xl items-center justify-between gap-2 rounded-2xl px-2.5 shadow-[0_16px_48px_rgba(0,0,0,0.55),0_0_32px_rgba(212,164,58,0.08)] sm:gap-4 sm:rounded-full sm:px-4">
        <Link
          href="/"
          className="flex min-w-0 items-center gap-2 rounded-full focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring sm:gap-2.5"
          aria-label="WorkLytix AI home"
        >
          <BrandMark size={32} />
          <BrandWordmark />
        </Link>
        <div className="relative flex shrink-0 items-center gap-1.5 sm:gap-3">
          <button
            ref={buttonRef}
            type="button"
            aria-expanded={menuOpen}
            aria-haspopup="true"
            aria-controls="site-menu"
            onClick={() => setMenuOpen((v) => !v)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-2.5 py-2 text-sm font-medium whitespace-nowrap transition-colors sm:gap-2 sm:px-3",
              "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
              menuOpen
                ? "bg-white/[0.08] text-foreground"
                : "text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"
            )}
          >
            {menuOpen ? (
              <X className="h-4 w-4" aria-hidden />
            ) : (
              <Menu className="h-4 w-4" aria-hidden />
            )}
            Menu
          </button>
          <Link
            href="/ai-analysis"
            className="rounded-full bg-gradient-to-b from-[#F0C75E] to-[#B47A1B] px-3.5 py-2 text-[13px] font-semibold whitespace-nowrap text-[#171207] shadow-[0_0_20px_rgba(212,164,58,0.30)] transition-all hover:brightness-110 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring sm:px-4 sm:text-sm"
          >
            AI Analysis
          </Link>
          {menuOpen ? (
            <div
              ref={panelRef}
              id="site-menu"
              role="menu"
              aria-label="Site sections"
              className="glass absolute top-full right-0 mt-2 flex w-56 flex-col gap-1 rounded-xl p-2"
            >
              {MENU_ITEMS.map((item) => {
                const active = isActive(item.href, item.exact);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    role="menuitem"
                    aria-current={active ? "page" : undefined}
                    onClick={() => setMenuOpen(false)}
                    className={cn(
                      "rounded-md px-3 py-2 text-sm transition-colors",
                      "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                      active
                        ? "bg-[var(--gold-soft)] text-[var(--gold-bright)]"
                        : "text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"
                    )}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}
