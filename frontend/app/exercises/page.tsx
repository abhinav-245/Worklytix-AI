"use client";

import { getExerciseVariety } from "@/lib/api";
import { RouteShell } from "@/components/route-shell";
import { VarietySection } from "@/components/variety-section";

/** Dedicated exercise-variety route: full selection analysis. */
export default function ExercisesPage() {
  return (
    <RouteShell
      title="Exercise Variety"
      description="Selection breadth and week-to-week changes."
      context="exercise variety analysis"
      fetcher={getExerciseVariety}
    >
      {(variety) => (
        <div className="w-full overflow-x-auto">
          <VarietySection variety={variety} />
        </div>
      )}
    </RouteShell>
  );
}
