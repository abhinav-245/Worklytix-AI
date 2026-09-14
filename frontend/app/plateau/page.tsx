"use client";

import { getPlateaus } from "@/lib/api";
import { RouteShell } from "@/components/route-shell";
import { PlateauSection } from "@/components/plateau-section";

/** Dedicated plateau route: rule-based possible plateaus with evidence. */
export default function PlateauPage() {
  return (
    <RouteShell
      title="Plateaus"
      description="Possible plateaus with weekly evidence. No recommendations."
      context="plateau analysis"
      fetcher={getPlateaus}
    >
      {(plateaus) => <PlateauSection plateaus={plateaus} />}
    </RouteShell>
  );
}
