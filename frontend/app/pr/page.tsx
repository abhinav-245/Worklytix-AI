"use client";

import { getPRs } from "@/lib/api";
import { RouteShell } from "@/components/route-shell";
import { PrTable } from "@/components/pr-table";

/** Dedicated PR route: all PR columns including bodyweight ratios. */
export default function PRPage() {
  return (
    <RouteShell
      title="Personal Records"
      description="Heaviest, most and highest-volume performances per exercise."
      context="your personal records"
      fetcher={getPRs}
    >
      {(prs) => (
        <div className="w-full overflow-x-auto">
          <PrTable prs={prs} />
        </div>
      )}
    </RouteShell>
  );
}
