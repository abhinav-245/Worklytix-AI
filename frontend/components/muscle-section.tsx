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
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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

/** Mirrors backend MuscleSummary (analytics/muscles.py). Display only. */
export interface MuscleSummary {
  muscle: string;
  total_sets: number;
  training_sessions: number;
  exercise_variety: number;
  average_sessions_per_week: number | null;
  potentially_neglected: boolean;
}

/** Mirrors backend MuscleAnalysisResponse. Display only. */
export interface MuscleAnalysis {
  muscles: MuscleSummary[];
  mapping: {
    total_exercises: number;
    mapped_exercises: number;
    unmapped_exercises: number;
    coverage_percent: number;
  };
  unmapped_exercises: string[];
}

function formatCount(value: number): string {
  return value.toLocaleString("en-US");
}

/** Backend-calculated muscle facts, rendered as table + chart. No math here. */
export function MuscleSection({ analysis }: { analysis: MuscleAnalysis }) {
  const neglected = analysis.muscles.filter((m) => m.potentially_neglected);
  const trained = analysis.muscles.filter((m) => !m.potentially_neglected);

  return (
    <div className="flex w-full max-w-3xl flex-col items-center gap-4">
      <p className="text-sm text-muted-foreground">
        Exercise mapping coverage:{" "}
        {formatCount(analysis.mapping.mapped_exercises)} /{" "}
        {formatCount(analysis.mapping.total_exercises)} exercises (
        {analysis.mapping.coverage_percent.toLocaleString("en-US")}%)
      </p>

      <Card className="w-full">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Total sets per muscle
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart
              data={trained}
              margin={{ top: 4, right: 8, bottom: 0, left: -8 }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="muscle" tick={{ fontSize: 11 }} interval={0} angle={-35} dy={12} height={64} />
              <YAxis tick={{ fontSize: 11 }} width={48} />
              <Tooltip formatter={(value) => [`${value} sets`, "Total sets"]} />
              <Bar dataKey="total_sets" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Muscle</TableHead>
            <TableHead>Total Sets</TableHead>
            <TableHead>Training Sessions</TableHead>
            <TableHead>Exercise Variety</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {analysis.muscles.map((m) => (
            <TableRow key={m.muscle}>
              <TableCell className="font-medium">{m.muscle}</TableCell>
              <TableCell>{formatCount(m.total_sets)}</TableCell>
              <TableCell>{formatCount(m.training_sessions)}</TableCell>
              <TableCell>{formatCount(m.exercise_variety)}</TableCell>
              <TableCell>
                {m.potentially_neglected ? "Potentially Neglected" : "—"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {neglected.length > 0 ? (
        <Alert className="w-full">
          <AlertTitle>Potentially Neglected</AlertTitle>
          <AlertDescription>
            No mapped training sets recorded for:{" "}
            {neglected.map((m) => m.muscle).join(", ")}
          </AlertDescription>
        </Alert>
      ) : null}

      {analysis.unmapped_exercises.length > 0 ? (
        <p className="text-sm text-muted-foreground">
          Unmapped exercises ({formatCount(analysis.unmapped_exercises.length)}
          ): {analysis.unmapped_exercises.join(", ")}
        </p>
      ) : null}
    </div>
  );
}
