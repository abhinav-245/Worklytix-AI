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

/** Mirrors backend AIResponseData (ai/models.py). Display only. */
export interface AIObservation {
  statement: string;
  fact_ids: string[];
}

export interface AIAssumption {
  statement: string;
  reason: string;
}

export interface AIAnswer {
  answer: string;
  observations: AIObservation[];
  assumptions: AIAssumption[];
  limitations: string[];
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export type AskAIErrorCode =
  | "no_dataset"
  | "no_profile"
  | "ai_not_configured"
  | "ai_provider_error"
  | "invalid_request"
  | "network_error";

export class AskAIError extends Error {
  code: AskAIErrorCode;
  constructor(code: AskAIErrorCode, message: string) {
    super(message);
    this.code = code;
  }
}

/**
 * Shared error mapping for the AI endpoints. Throws AskAIError with a
 * safe message; never exposes backend stack traces.
 */
function throwAIError(
  res: Response,
  body: {
    success?: boolean;
    detail?: string | { error?: string; message?: string };
  } | null,
  invalidMessage: string
): never {
  const detail = body?.detail;
  const code =
    typeof detail === "object" && detail?.error ? detail.error : undefined;
  if (res.status === 404 || code === "no_dataset") {
    throw new AskAIError(
      "no_dataset",
      "Upload a workout CSV first, then ask about your training."
    );
  }
  if (res.status === 404 || code === "no_profile") {
    throw new AskAIError(
      "no_profile",
      "Add your age, body weight and goal during onboarding first."
    );
  }
  if (res.status === 503 || code === "ai_not_configured") {
    throw new AskAIError("ai_not_configured", "AI is not configured yet.");
  }
  if (res.status === 422) {
    throw new AskAIError("invalid_request", invalidMessage);
  }
  throw new AskAIError(
    "ai_provider_error",
    "I couldn't get an answer right now. Please try again."
  );
}

/**
 * POST /ai/ask. Throws AskAIError with a safe message; never exposes
 * backend stack traces. Conversation is bounded client-side.
 */
export async function askAI(
  question: string,
  conversation: ChatTurn[]
): Promise<AIAnswer> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/ai/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        conversation: conversation.slice(-20),
      }),
      cache: "no-store",
    });
  } catch {
    throw new AskAIError(
      "network_error",
      "I couldn't reach the analysis service. Please try again."
    );
  }
  const body = (await res.json().catch(() => null)) as {
    success?: boolean;
    data?: AIAnswer;
    detail?: string | { error?: string; message?: string };
  } | null;
  if (res.ok && body?.success === true && body.data) {
    return body.data;
  }
  throwAIError(
    res,
    body,
    "Please ask a question using up to 2000 characters."
  );
}

/**
 * POST /ai/analyze. Generates the comprehensive initial analysis.
 * No question needed. Throws AskAIError with a safe message.
 */
export async function analyzeTraining(): Promise<AIAnswer> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/ai/analyze`, {
      method: "POST",
      cache: "no-store",
    });
  } catch {
    throw new AskAIError(
      "network_error",
      "I couldn't reach the analysis service. Please try again."
    );
  }
  const body = (await res.json().catch(() => null)) as {
    success?: boolean;
    data?: AIAnswer;
    detail?: string | { error?: string; message?: string };
  } | null;
  if (res.ok && body?.success === true && body.data) {
    return body.data;
  }
  throwAIError(
    res,
    body,
    "Analysis is currently unavailable. Please try again."
  );
}

/** Mirrors backend AIRecommendation (ai/models.py). Display only. */
export interface AIRecommendation {
  recommendation: string;
  reason: string;
  fact_ids: string[];
}

export interface AIRecommendations {
  recommendations: AIRecommendation[];
  observations: AIObservation[];
  assumptions: AIAssumption[];
  limitations: string[];
}

/**
 * POST /ai/recommend (v2 engine). Sends back the analysis text shown
 * to the user as conversational context only; profile, analytics and
 * knowledge stay backend-authoritative. Throws AskAIError otherwise.
 */
export async function recommendTraining(
  analysis: string
): Promise<AIRecommendations> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/ai/recommend`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ analysis }),
      cache: "no-store",
    });
  } catch {
    throw new AskAIError(
      "network_error",
      "I couldn't reach the analysis service. Please try again."
    );
  }
  const body = (await res.json().catch(() => null)) as {
    success?: boolean;
    data?: AIRecommendations;
    detail?: string | { error?: string; message?: string };
  } | null;
  if (res.ok && body?.success === true && body.data) {
    return body.data;
  }
  throwAIError(
    res,
    body,
    "Recommendations are currently unavailable. Please try again."
  );
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
