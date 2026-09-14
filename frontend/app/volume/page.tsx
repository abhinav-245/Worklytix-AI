"use client";

import { getVolume } from "@/lib/api";
import { RouteShell } from "@/components/route-shell";
import { VolumeChart } from "@/components/dashboard/volume-chart";

/** Dedicated volume route: total-volume time series with selector. */
export default function VolumePage() {
  return (
    <RouteShell
      title="Volume"
      description="Total exercise volume per workout (weight × reps)."
      context="volume analysis"
      fetcher={getVolume}
    >
      {(exercises) => <VolumeChart exercises={exercises} />}
    </RouteShell>
  );
}
