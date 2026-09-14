"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  CHART_GOLD,
  CHART_GRID,
  CHART_TICK,
  CHART_TOOLTIP_STYLE,
} from "@/lib/chart-theme";
import type { MuscleAnalysis } from "@/components/muscle-section";

/**
 * Horizontal sets-per-muscle distribution from backend muscle facts.
 * Neglected (zero-set) muscles are listed, not charted, to keep the
 * chart readable.
 */
export function MuscleDistributionChart({
  analysis,
}: {
  analysis: MuscleAnalysis;
}) {
  const trained = analysis.muscles
    .filter((m) => !m.potentially_neglected)
    .map((m) => ({ muscle: m.muscle, sets: m.total_sets }))
    .sort((a, b) => b.sets - a.sets);

  if (trained.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No mapped muscle data available.
      </p>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={Math.max(220, trained.length * 32)}>
      <BarChart
        data={trained}
        layout="vertical"
        margin={{ top: 4, right: 16, bottom: 0, left: 8 }}
      >
        <CartesianGrid stroke={CHART_GRID} strokeDasharray="3 3" />
        <XAxis
          type="number"
          tick={{ fontSize: 11, fill: CHART_TICK }}
        />
        <YAxis
          type="category"
          dataKey="muscle"
          tick={{ fontSize: 11, fill: CHART_TICK }}
          width={92}
        />
        <Tooltip
          contentStyle={CHART_TOOLTIP_STYLE}
          formatter={(value) => [`${value} sets`, "Total sets"]}
        />
        <Bar dataKey="sets" radius={[0, 4, 4, 0]}>
          {trained.map((entry) => (
            <Cell key={entry.muscle} fill={CHART_GOLD} fillOpacity={0.85} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
