"use client";

import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

/** Mirrors backend ProgressionPoint (analytics/progression.py). Display only. */
export interface ProgressionPoint {
  date: string;
  workout_start: string;
  weight_kg: number;
  reps: number;
  volume_kg: number;
  estimated_1rm_kg: number;
}

/** Mirrors backend ExerciseProgression. Display only. */
export interface ExerciseProgression {
  exercise_name: string;
  history: ProgressionPoint[];
}

interface ChartSpec {
  title: string;
  dataKey: "weight_kg" | "reps" | "volume_kg" | "estimated_1rm_kg";
  unit: string;
}

const CHARTS: ChartSpec[] = [
  { title: "Weight progression", dataKey: "weight_kg", unit: "kg" },
  { title: "Rep progression", dataKey: "reps", unit: "reps" },
  { title: "Volume progression", dataKey: "volume_kg", unit: "kg" },
  { title: "Estimated 1RM progression", dataKey: "estimated_1rm_kg", unit: "kg" },
];

function ProgressionChart({
  title,
  dataKey,
  unit,
  history,
}: ChartSpec & { history: ProgressionPoint[] }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title} ({unit})
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={history} margin={{ top: 4, right: 8, bottom: 0, left: -8 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              minTickGap={48}
            />
            <YAxis tick={{ fontSize: 11 }} width={48} />
            <Tooltip
              labelFormatter={(label) => `Date: ${label}`}
              formatter={(value) => [`${value} ${unit}`, title]}
            />
            <Line
              type="monotone"
              dataKey={dataKey}
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

/**
 * Backend-calculated progression, visualized. The selector is populated
 * from the API response; no values are calculated here.
 */
export function ProgressionSection({
  exercises,
}: {
  exercises: ExerciseProgression[];
}) {
  const [selected, setSelected] = useState(exercises[0]?.exercise_name ?? "");
  const current = exercises.find((e) => e.exercise_name === selected);

  return (
    <div className="flex w-full max-w-3xl flex-col items-center gap-4">
      <label
        htmlFor="exercise-select"
        className="flex w-full max-w-md flex-col gap-2 text-sm font-medium"
      >
        Exercise
        <select
          id="exercise-select"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          {exercises.map((e) => (
            <option key={e.exercise_name} value={e.exercise_name}>
              {e.exercise_name}
            </option>
          ))}
        </select>
      </label>
      {!current || current.history.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No progression data available.
        </p>
      ) : (
        <div className="grid w-full grid-cols-1 gap-4 lg:grid-cols-2">
          {CHARTS.map((spec) => (
            <ProgressionChart
              key={spec.dataKey}
              {...spec}
              history={current.history}
            />
          ))}
        </div>
      )}
    </div>
  );
}
