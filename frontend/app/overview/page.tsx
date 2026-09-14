"use client";

import { useEffect, useState } from "react";
import { CalendarDays, Gauge, Layers, Scale } from "lucide-react";
import { getOverview, getProfile } from "@/lib/api";
import type { TrainingOverview } from "@/components/overview-grid";
import type { ProfileAnalysis } from "@/components/profile-section";
import { NoDataset } from "@/components/no-dataset";
import {
  SectionSkeleton,
} from "@/components/dashboard/section";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** Presentation-only compact volume formatting (backend value untouched). */
function formatVolumeKg(value: number): string {
  if (value >= 1_000_000) {
    const trimmed = (value / 1_000_000).toFixed(2).replace(/\.?0+$/, "");
    return `${trimmed}M kg`;
  }
  if (value >= 10_000) {
    const trimmed = (value / 1_000).toFixed(1).replace(/\.?0+$/, "");
    return `${trimmed}K kg`;
  }
  return `${value.toLocaleString("en-US")} kg`;
}

/** Presentation-only date formatting (backend value untouched). */
function formatDate(value: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(parsed);
}

const CARDS = [
  { key: "days", label: "Days Trained", icon: CalendarDays },
  { key: "sets", label: "Total Sets", icon: Layers },
  { key: "volume", label: "Weighted Volume", icon: Scale },
  { key: "experience", label: "Experience", icon: Gauge },
] as const;

/** Compact overview: four headline metrics, nothing more. */
export default function OverviewPage() {
  const [overview, setOverview] = useState<TrainingOverview | null>(null);
  const [profile, setProfile] = useState<ProfileAnalysis | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let active = true;
    Promise.all([getOverview(), getProfile()]).then(([ov, pf]) => {
      if (!active) return;
      setOverview(ov);
      setProfile(pf);
      setChecking(false);
    });
    return () => {
      active = false;
    };
  }, []);

  const history = profile?.training_history ?? null;

  const values: Record<(typeof CARDS)[number]["key"], string> = {
    days:
      overview?.training_period_days === null ||
      overview?.training_period_days === undefined
        ? "—"
        : overview.training_period_days.toLocaleString("en-US"),
    sets: overview ? overview.total_sets.toLocaleString("en-US") : "—",
    volume: overview ? formatVolumeKg(overview.total_volume_kg) : "—",
    experience: history ? history.level : "—",
  };

  const subtexts: Record<(typeof CARDS)[number]["key"], string> = {
    days:
      overview?.first_workout_date && overview?.last_workout_date
        ? `${formatDate(overview.first_workout_date)} → ${formatDate(overview.last_workout_date)}`
        : "days",
    sets: "sets",
    volume: "weight × reps",
    experience: history
      ? `Based on ${history.duration_text} of observed training data`
      : "Submit a profile to unlock",
  };

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 px-4 py-10 sm:px-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Overview</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          How your training looks at a glance.
        </p>
      </div>
      {checking ? (
        <Card className="glass w-full">
          <CardContent className="pt-6">
            <SectionSkeleton rows={4} />
          </CardContent>
        </Card>
      ) : !overview ? (
        <NoDataset context="your training overview" />
      ) : (
        <div className="grid w-full grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {CARDS.map((card) => (
            <Card key={card.key} className="glass glass-hover gold-accent-top">
              <CardHeader className="flex flex-row items-center justify-between gap-2 pb-2">
                <CardTitle className="text-xs font-medium tracking-wider text-muted-foreground uppercase">
                  {card.label}
                </CardTitle>
                <card.icon
                  className="h-4 w-4 shrink-0 text-[var(--gold)]"
                  aria-hidden
                />
              </CardHeader>
              <CardContent>
                <p className="metric-gold text-3xl font-bold tracking-tight break-all">
                  {values[card.key]}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {subtexts[card.key]}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </main>
  );
}
