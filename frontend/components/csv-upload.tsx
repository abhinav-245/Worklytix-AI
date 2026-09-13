"use client";

import { useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface DroppedRow {
  row_number: number;
  reasons: string[];
}

interface UploadStatistics {
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  total_workouts: number;
  total_exercises: number;
  total_sets: number;
  first_workout_date: string | null;
  last_workout_date: string | null;
  missing_values: Record<string, number>;
  invalid_values: Record<string, number>;
  extra_columns: string[];
  dropped_rows: DroppedRow[];
}

interface UploadResult {
  statistics: UploadStatistics;
  workouts: unknown[];
}

type UploadState =
  | { status: "idle" }
  | { status: "uploading" }
  | { status: "success"; result: UploadResult; fileName: string }
  | { status: "error"; message: string };

function statEntries(stats: UploadStatistics): [string, string | number][] {
  return [
    ["Total rows", stats.total_rows],
    ["Valid rows", stats.valid_rows],
    ["Invalid rows", stats.invalid_rows],
    ["Workouts", stats.total_workouts],
    ["Exercises", stats.total_exercises],
    ["Sets", stats.total_sets],
    ["First workout", stats.first_workout_date ?? "—"],
    ["Last workout", stats.last_workout_date ?? "—"],
  ];
}

export function CsvUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<UploadState>({ status: "idle" });

  const upload = async () => {
    if (!file || state.status === "uploading") return;
    setState({ status: "uploading" });
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_URL}/upload`, {
        method: "POST",
        body: form,
      });
      const body = (await res.json().catch(() => null)) as {
        detail?: string | { message?: string };
        statistics?: UploadStatistics;
      } | null;
      if (!res.ok) {
        const message =
          typeof body?.detail === "string"
            ? body.detail
            : (body?.detail?.message ?? `Upload failed (HTTP ${res.status}).`);
        setState({ status: "error", message });
        return;
      }
      if (!body || !("statistics" in body)) {
        setState({ status: "error", message: "Unexpected response from server." });
        return;
      }
      setState({
        status: "success",
        result: body as UploadResult,
        fileName: file.name,
      });
    } catch (err) {
      setState({
        status: "error",
        message: err instanceof Error ? err.message : "Network request failed.",
      });
    }
  };

  const stats = state.status === "success" ? state.result.statistics : null;

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>Upload workout CSV</CardTitle>
        <CardDescription>
          Sends multipart form data to POST {API_URL}/upload.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          disabled={state.status === "uploading"}
        />
        <Button
          onClick={upload}
          disabled={!file || state.status === "uploading"}
        >
          {state.status === "uploading" ? "Uploading…" : "Upload"}
        </Button>

        {state.status === "error" ? (
          <Alert variant="destructive">
            <AlertTitle>Upload failed</AlertTitle>
            <AlertDescription>{state.message}</AlertDescription>
          </Alert>
        ) : null}

        {stats ? (
          <div className="flex flex-col gap-2">
            <p className="text-sm font-medium">
              {state.status === "success"
                ? `Parsed “${state.fileName}” successfully.`
                : null}
            </p>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
              {statEntries(stats).map(([label, value]) => (
                <div key={label} className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">{label}</dt>
                  <dd className="font-medium break-all text-right">{value}</dd>
                </div>
              ))}
            </dl>
            {stats.dropped_rows.length > 0 ? (
              <p className="text-sm text-muted-foreground">
                Dropped rows (showing {stats.dropped_rows.length}):{" "}
                {stats.dropped_rows
                  .map((d) => `#${d.row_number} (${d.reasons.join("; ")})`)
                  .join(", ")}
              </p>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
