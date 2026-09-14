"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
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
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

/** Mirrors backend ExerciseFrequency. Display only. */
export interface ExerciseFrequency {
  exercise_name: string;
  muscle: string | null;
  workout_occurrences: number;
  frequency_percent: number;
  rarely_performed: boolean;
  frequently_performed: boolean;
}

/** Mirrors backend ExerciseSelectionEvent. Display only. */
export interface ExerciseSelectionEvent {
  exercise_name: string;
  event_type: "introduced" | "disappeared" | "reappeared";
  week: string;
  date: string;
}

/** Mirrors backend ExerciseVarietyAnalysis. Display only. */
export interface ExerciseVariety {
  total_workouts: number;
  distinct_exercises: number;
  exercises: string[];
  frequencies: ExerciseFrequency[];
  exercises_per_muscle: { muscle: string; exercise_count: number }[];
  selection_events: ExerciseSelectionEvent[];
  selection_summary: {
    total_selection_events: number;
    introductions: number;
    disappearances: number;
    reappearances: number;
  };
}

const TOP_CHART_COUNT = 15;

function formatCount(value: number): string {
  return value.toLocaleString("en-US");
}

function formatEvent(event: ExerciseSelectionEvent["event_type"]): string {
  return event.charAt(0).toUpperCase() + event.slice(1);
}

/** Backend-calculated variety facts, visualized. No calculations here. */
export function VarietySection({ variety }: { variety: ExerciseVariety }) {
  const rare = variety.frequencies.filter((f) => f.rarely_performed);
  const frequent = variety.frequencies.filter((f) => f.frequently_performed);
  const top = [...variety.frequencies]
    .sort((a, b) => b.workout_occurrences - a.workout_occurrences)
    .slice(0, TOP_CHART_COUNT);

  return (
    <div className="flex w-full max-w-3xl flex-col items-center gap-4">
      <p className="text-sm text-muted-foreground">
        {formatCount(variety.distinct_exercises)} distinct exercises across{" "}
        {formatCount(variety.total_workouts)} workouts ·{" "}
        {formatCount(variety.selection_summary.total_selection_events)}{" "}
        selection events
      </p>

      <Card className="w-full">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Exercises per muscle
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Muscle</TableHead>
                <TableHead>Exercises</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {variety.exercises_per_muscle.map((row) => (
                <TableRow key={row.muscle}>
                  <TableCell className="font-medium">{row.muscle}</TableCell>
                  <TableCell>{formatCount(row.exercise_count)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card className="w-full">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Most frequent exercises (top {TOP_CHART_COUNT})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart
              data={top}
              layout="vertical"
              margin={{ top: 4, right: 8, bottom: 0, left: 8 }}
            >
              <CartesianGrid stroke={CHART_GRID} strokeDasharray="3 3" />
              <XAxis type="number" tick={{ fontSize: 11, fill: CHART_TICK }} />
              <YAxis
                type="category"
                dataKey="exercise_name"
                tick={{ fontSize: 11, fill: CHART_TICK }}
                width={160}
              />
              <Tooltip
                contentStyle={CHART_TOOLTIP_STYLE}
                formatter={(value) => [`${value} workouts`, "Workouts"]}
              />
              <Bar dataKey="workout_occurrences" fill={CHART_GOLD} fillOpacity={0.85} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card className="w-full">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Exercise frequency
          </CardTitle>
        </CardHeader>
        <CardContent className="max-h-96 overflow-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Exercise</TableHead>
                <TableHead>Muscle</TableHead>
                <TableHead>Workouts</TableHead>
                <TableHead>Frequency %</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {variety.frequencies.map((f) => (
                <TableRow key={f.exercise_name}>
                  <TableCell className="font-medium">
                    {f.exercise_name}
                  </TableCell>
                  <TableCell>{f.muscle ?? "—"}</TableCell>
                  <TableCell>{formatCount(f.workout_occurrences)}</TableCell>
                  <TableCell>
                    {f.frequency_percent.toLocaleString("en-US")}%
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="grid w-full grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Rarely Performed (≤10%)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {rare.length === 0 ? (
              <p className="text-sm text-muted-foreground">None</p>
            ) : (
              <ul className="list-disc pl-5 text-sm">
                {rare.map((f) => (
                  <li key={f.exercise_name}>
                    {f.exercise_name} (
                    {f.frequency_percent.toLocaleString("en-US")}%)
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Frequently Performed (≥50%)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {frequent.length === 0 ? (
              <p className="text-sm text-muted-foreground">None</p>
            ) : (
              <ul className="list-disc pl-5 text-sm">
                {frequent.map((f) => (
                  <li key={f.exercise_name}>
                    {f.exercise_name} (
                    {f.frequency_percent.toLocaleString("en-US")}%)
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="w-full">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Selection changes
          </CardTitle>
        </CardHeader>
        <CardContent className="max-h-96 overflow-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Exercise</TableHead>
                <TableHead>Event</TableHead>
                <TableHead>Week</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {variety.selection_events.map((e, index) => (
                <TableRow key={`${e.exercise_name}-${e.week}-${e.event_type}-${index}`}>
                  <TableCell className="font-medium">
                    {e.exercise_name}
                  </TableCell>
                  <TableCell>{formatEvent(e.event_type)}</TableCell>
                  <TableCell>{e.week}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
