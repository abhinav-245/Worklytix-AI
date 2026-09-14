/** Centralized typed API client (Phase 10).

All analytics endpoints share the ``{ success, data, meta }`` envelope.
These helpers unwrap ``data`` and return ``null`` when the backend has no
result (missing dataset/profile) or is unreachable. Presentation-only:
no analytics are calculated here.
*/

import type { TrainingOverview } from "@/components/overview-grid";
import type { ExercisePR } from "@/components/pr-table";
import type { MuscleAnalysis } from "@/components/muscle-section";
import type { ExerciseVariety } from "@/components/variety-section";
import type { ExercisePlateau } from "@/components/plateau-section";
import type { ExerciseProgression } from "@/components/progression-charts";
import type { ProfileAnalysis } from "@/components/profile-section";
import type { ExerciseVolume } from "@/components/dashboard/volume-chart";

/** Mirrors backend FrequencyWeek (analytics/frequency.py). Display only. */
export interface FrequencyWeek {
  week: string;
  week_start: string;
  workouts: number;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Envelope<T> {
  success: boolean;
  data: T;
  meta: { analysis_version: string };
}

async function getEnvelope<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
    if (!res.ok) return null;
    const body = (await res.json()) as Envelope<T>;
    if (!body || body.success !== true) return null;
    return body.data;
  } catch {
    return null;
  }
}

export function getOverview(): Promise<TrainingOverview | null> {
  return getEnvelope<TrainingOverview>("/analysis/overview");
}

export async function getPRs(): Promise<ExercisePR[] | null> {
  const data = await getEnvelope<{ exercises: ExercisePR[] }>(
    "/analysis/prs"
  );
  return data ? data.exercises : null;
}

export async function getProgression(): Promise<
  ExerciseProgression[] | null
> {
  const data = await getEnvelope<{ exercises: ExerciseProgression[] }>(
    "/analysis/progression"
  );
  return data ? data.exercises : null;
}

export async function getPlateaus(): Promise<ExercisePlateau[] | null> {
  const data = await getEnvelope<{ plateaus: ExercisePlateau[] }>(
    "/analysis/plateaus"
  );
  return data ? data.plateaus : null;
}

export function getMuscles(): Promise<MuscleAnalysis | null> {
  return getEnvelope<MuscleAnalysis>("/analysis/muscles");
}

export function getExerciseVariety(): Promise<ExerciseVariety | null> {
  return getEnvelope<ExerciseVariety>("/analysis/exercise-variety");
}

export async function getVolume(): Promise<ExerciseVolume[] | null> {
  const data = await getEnvelope<{ exercises: ExerciseVolume[] }>(
    "/analysis/volume"
  );
  return data ? data.exercises : null;
}

export async function getFrequency(): Promise<FrequencyWeek[] | null> {
  const data = await getEnvelope<{ weeks: FrequencyWeek[] }>(
    "/analysis/frequency"
  );
  return data ? data.weeks : null;
}

export function getProfile(): Promise<ProfileAnalysis | null> {
  return getEnvelope<ProfileAnalysis>("/analysis/profile");
}

export interface UploadResult {
  statistics: {
    total_rows: number;
    valid_rows: number;
    invalid_rows: number;
    total_workouts: number;
    total_exercises: number;
    total_sets: number;
    first_workout_date: string | null;
    last_workout_date: string | null;
  };
  overview: TrainingOverview | null;
}

export interface ProfileInput {
  age: number | null;
  body_weight_kg: number | null;
  goal: string;
}

/** POST /upload with multipart CSV. Throws Error with backend message. */
export async function uploadWorkoutCSV(file: File): Promise<UploadResult> {
  let res: Response;
  try {
    const form = new FormData();
    form.append("file", file);
    res = await fetch(`${API_URL}/upload`, { method: "POST", body: form });
  } catch (err) {
    throw new Error(
      err instanceof Error ? err.message : "Network request failed."
    );
  }
  const body = (await res.json().catch(() => null)) as {
    detail?: string | { message?: string };
    statistics?: UploadResult["statistics"];
    overview?: TrainingOverview | null;
  } | null;
  if (!res.ok) {
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : (body?.detail?.message ?? `Upload failed (HTTP ${res.status}).`)
    );
  }
  if (!body || !("statistics" in body)) {
    throw new Error("Unexpected response from server.");
  }
  return body as UploadResult;
}

/** POST /profile with validated input. Throws Error with backend message. */
export async function saveProfile(input: ProfileInput): Promise<ProfileAnalysis> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/profile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
  } catch (err) {
    throw new Error(
      err instanceof Error ? err.message : "Network request failed."
    );
  }
  const body = (await res.json().catch(() => null)) as unknown;
  if (!res.ok) {
    throw new Error(extractApiError(body, `Save failed (HTTP ${res.status}).`));
  }
  return body as ProfileAnalysis;
}

function extractApiError(body: unknown, fallback: string): string {
  if (
    body !== null &&
    typeof body === "object" &&
    "detail" in body &&
    Array.isArray((body as { detail: unknown }).detail)
  ) {
    const first = (body as { detail: Array<{ msg?: unknown }> }).detail[0];
    if (first && typeof first.msg === "string") return first.msg;
  }
  if (
    body !== null &&
    typeof body === "object" &&
    "detail" in body &&
    typeof (body as { detail: unknown }).detail === "string"
  ) {
    return (body as { detail: string }).detail;
  }
  return fallback;
}
