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
