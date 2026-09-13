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

/** Mirrors backend PlateauWeekEvidence (analytics/plateau.py). Display only. */
export interface PlateauWeekEvidence {
  week: string;
  date: string;
  weight_kg: number;
  reps: number;
}

/** Mirrors backend ExercisePlateau. Display only. */
export interface ExercisePlateau {
  exercise_name: string;
  label: string;
  plateau_start: string;
  plateau_end: string;
  duration_days: number;
  consecutive_weeks: number;
  heaviest_weight_kg: number;
  reps_at_heaviest_weight: number;
  evidence: PlateauWeekEvidence[];
}

function formatCount(value: number): string {
  return value.toLocaleString("en-US");
}

/** Backend-detected plateaus with structured evidence. No interpretation. */
export function PlateauSection({ plateaus }: { plateaus: ExercisePlateau[] }) {
  if (plateaus.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No possible plateaus detected.
      </p>
    );
  }
  return (
    <div className="grid w-full max-w-3xl grid-cols-1 gap-4">
      {plateaus.map((plateau, index) => (
        <Card key={`${plateau.exercise_name}-${plateau.plateau_start}-${index}`}>
          <CardHeader className="pb-2">
            <CardTitle className="flex flex-wrap items-baseline justify-between gap-2 text-base">
              <span>{plateau.exercise_name}</span>
              <span className="text-sm font-medium text-muted-foreground">
                {plateau.label}
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <p className="text-2xl font-bold">
              {formatCount(plateau.heaviest_weight_kg)} kg ×{" "}
              {formatCount(plateau.reps_at_heaviest_weight)}
            </p>
            <p className="text-sm text-muted-foreground">
              {formatCount(plateau.consecutive_weeks)} consecutive weeks ·{" "}
              {plateau.plateau_start} → {plateau.plateau_end} ·{" "}
              {formatCount(plateau.duration_days)} days
            </p>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Week</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Weight</TableHead>
                  <TableHead>Reps</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {plateau.evidence.map((row) => (
                  <TableRow key={row.week}>
                    <TableCell>{row.week}</TableCell>
                    <TableCell>{row.date}</TableCell>
                    <TableCell>{formatCount(row.weight_kg)} kg</TableCell>
                    <TableCell>{formatCount(row.reps)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
