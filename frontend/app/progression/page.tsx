"use client";

import { getProgression } from "@/lib/api";
import { RouteShell } from "@/components/route-shell";
import { ProgressionSection } from "@/components/progression-charts";

/** Dedicated progression route: four charts with exercise selector. */
export default function ProgressionPage() {
  return (
    <RouteShell
      title="Progression"
      description="Weight, reps, volume and estimated 1RM over time."
      context="progression charts"
      fetcher={getProgression}
    >
      {(exercises) => <ProgressionSection exercises={exercises} />}
    </RouteShell>
  );
}
