import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

/** Mirrors backend ExercisePR (analytics/prs.py). Display only. */
export interface ExercisePR {
  exercise_name: string;
  weight_pr: { value: number; unit: string; date: string | null } | null;
  rep_pr: { value: number; unit: string; date: string | null } | null;
  volume_pr: {
    value: number;
    unit: string;
    weight: number;
    reps: number;
    date: string | null;
  } | null;
  estimated_1rm_pr: {
    value: number;
    unit: string;
    weight: number;
    reps: number;
    date: string | null;
  } | null;
}

function formatKg(pr: { value: number } | null): string {
  if (pr === null) return "—";
  return `${pr.value.toLocaleString("en-US")} kg`;
}

function formatReps(pr: { value: number } | null): string {
  if (pr === null) return "—";
  return `${pr.value.toLocaleString("en-US")}`;
}

/** Backend-calculated PR facts, rendered as a table. No calculations here. */
export function PrTable({ prs }: { prs: ExercisePR[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Exercise</TableHead>
          <TableHead>Weight PR</TableHead>
          <TableHead>Rep PR</TableHead>
          <TableHead>Volume PR</TableHead>
          <TableHead>Est. 1RM PR</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {prs.map((pr) => (
          <TableRow key={pr.exercise_name}>
            <TableCell className="font-medium">{pr.exercise_name}</TableCell>
            <TableCell>{formatKg(pr.weight_pr)}</TableCell>
            <TableCell>{formatReps(pr.rep_pr)}</TableCell>
            <TableCell>{formatKg(pr.volume_pr)}</TableCell>
            <TableCell>{formatKg(pr.estimated_1rm_pr)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
