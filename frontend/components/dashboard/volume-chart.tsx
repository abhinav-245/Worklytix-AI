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
  CHART_GOLD,
  CHART_GRID,
  CHART_TICK,
  CHART_TOOLTIP_STYLE,
} from "@/lib/chart-theme";

/** Mirrors backend VolumePoint (analytics/volume.py). Display only. */
export interface VolumePoint {
  date: string;
  workout_start: string;
  volume_kg: number;
}

/** Mirrors backend ExerciseVolume. Display only. */
export interface ExerciseVolume {
  exercise_name: string;
  history: VolumePoint[];
}

/**
 * Total-volume time series for one selected exercise, from the backend
 * volume API (workout-level sums, same definition as progression volume).
 */
export function VolumeChart({ exercises }: { exercises: ExerciseVolume[] }) {
  const withHistory = exercises.filter((e) => e.history.length > 0);
  const [selected, setSelected] = useState(
    withHistory[0]?.exercise_name ?? ""
  );
  const current =
    exercises.find((e) => e.exercise_name === selected) ?? null;

  return (
    <div className="flex w-full flex-col gap-4">
      <label
        htmlFor="volume-exercise-select"
        className="flex w-full max-w-md flex-col gap-2 text-sm font-medium"
      >
        Exercise
        <select
          id="volume-exercise-select"
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
          No volume data available for this exercise.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <LineChart
            data={current.history}
            margin={{ top: 4, right: 8, bottom: 0, left: -8 }}
          >
            <CartesianGrid stroke={CHART_GRID} strokeDasharray="3 3" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: CHART_TICK }}
              minTickGap={48}
            />
            <YAxis tick={{ fontSize: 11, fill: CHART_TICK }} width={52} />
            <Tooltip
              contentStyle={CHART_TOOLTIP_STYLE}
              labelFormatter={(label) => `Date: ${label}`}
              formatter={(value) => [`${value} kg`, "Volume"]}
            />
            <Line
              type="monotone"
              dataKey="volume_kg"
              stroke={CHART_GOLD}
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
      <p className="text-xs text-muted-foreground">
        Volume (kg) is the workout-level sum of valid set volumes for the
        selected exercise.
      </p>
    </div>
  );
}
