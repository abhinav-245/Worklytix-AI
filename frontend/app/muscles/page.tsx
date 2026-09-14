"use client";

import { getMuscles } from "@/lib/api";
import { RouteShell } from "@/components/route-shell";
import { MuscleSection } from "@/components/muscle-section";

/** Dedicated muscle route: full muscle analysis. */
export default function MusclesPage() {
  return (
    <RouteShell
      title="Muscles"
      description="Sets, sessions and variety per muscle."
      context="muscle analysis"
      fetcher={getMuscles}
    >
      {(analysis) => (
        <div className="w-full overflow-x-auto">
          <MuscleSection analysis={analysis} />
        </div>
      )}
    </RouteShell>
  );
}
