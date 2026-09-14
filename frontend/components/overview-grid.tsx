import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** Mirrors backend TrainingOverview (analytics/overview.py). Display only. */
export interface TrainingOverview {
  total_workouts: number;
  training_period_days: number | null;
  first_workout_date: string | null;
  last_workout_date: string | null;
  total_exercises: number;
  total_sets: number;
  working_sets: number;
  warmup_sets: number;
  dropsets: number;
  failure_sets: number;
  other_sets: number;
  average_workout_duration_minutes: number | null;
  workouts_per_week: number | null;
  training_consistency: number | null;
  total_volume_kg: number;
}

function formatCount(value: number): string {
  return value.toLocaleString("en-US");
}

function formatDays(value: number | null): string {
  if (value === null) return "—";
  return `${formatCount(value)} ${value === 1 ? "day" : "days"}`;
}

function formatNullable(value: number | string | null, suffix = ""): string {
  if (value === null) return "—";
  return `${typeof value === "number" ? value.toLocaleString("en-US") : value}${suffix}`;
}

function metricEntries(overview: TrainingOverview): [string, string][] {
  return [
    ["Total Workouts", formatCount(overview.total_workouts)],
    ["Training Period", formatDays(overview.training_period_days)],
    ["First Workout", overview.first_workout_date ?? "—"],
    ["Last Workout", overview.last_workout_date ?? "—"],
    ["Total Exercises", formatCount(overview.total_exercises)],
    ["Total Sets", formatCount(overview.total_sets)],
    ["Working Sets", formatCount(overview.working_sets)],
    ["Warm-up Sets", formatCount(overview.warmup_sets)],
    ["Dropsets", formatCount(overview.dropsets)],
    ["Failure Sets", formatCount(overview.failure_sets)],
    [
      "Average Workout Duration",
      formatNullable(overview.average_workout_duration_minutes, " min"),
    ],
    [
      "Workouts / Week",
      overview.workouts_per_week === null
        ? "—"
        : `${overview.workouts_per_week.toLocaleString("en-US")} /wk`,
    ],
    ["Training Consistency", formatNullable(overview.training_consistency, "%")],
  ];
}

export function OverviewGrid({ overview }: { overview: TrainingOverview }) {
  return (
    <div className="grid w-full max-w-3xl grid-cols-2 gap-4 sm:grid-cols-3">
      {metricEntries(overview).map(([label, value]) => (
        <Card key={label}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {label}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold break-all">{value}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
